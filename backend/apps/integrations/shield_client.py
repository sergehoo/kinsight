"""Client HTTP Kaydan Shield : transport, erreurs, pagination, cache.

Séparé de la normalisation métier (`shield.py`) pour une raison précise : la
distinction entre « la source a dit non » et « la source n'a pas répondu »
détermine l'état affiché à l'écran. Un 403 n'est pas une panne, un timeout n'est
pas une absence de donnée, et confondre les deux produit des tableaux de bord qui
mentent.

Auth : Bearer JWT, conformément au Swagger Shield (`jwtAuth` sur tous les
endpoints métier lus ici). Le canal HMAC `X-KShield-*` est réservé aux terminaux
et n'est pas utilisé pour ces lectures.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 8
MAX_ATTEMPTS = 3          # 1 essai + 2 reprises, bornées
BACKOFF_SECONDS = (0.4, 1.2)
CACHE_TTL_SECONDS = 45    # court : on veut du frais, pas une rafale d'appels
MAX_PAGES = 10            # garde-fou : jamais de pagination sans fin


class ShieldError(Exception):
    """Échec d'appel qualifié par sa CAUSE, pas seulement par son message.

    `kind` pilote directement l'état gouverné rendu à l'UI :
      auth     → la source refuse (jeton absent/expiré/insuffisant) : `error`
      timeout  → la source n'a pas répondu à temps : `error`
      network  → hôte injoignable : `error`
      http     → réponse d'erreur explicite : `error`
      payload  → réponse illisible ou de forme inattendue : `error`
    """

    def __init__(self, kind: str, message: str, status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.status = status

    def __str__(self) -> str:
        base = super().__str__()
        return f"[{self.kind}{f'/{self.status}' if self.status else ''}] {base}"


class _TTLCache:
    """Cache mémoire court, protégé par un verrou (Django sert en multi-thread)."""

    def __init__(self, ttl: int = CACHE_TTL_SECONDS):
        self._ttl = ttl
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            hit = self._data.get(key)
            if not hit:
                return None
            expires, value = hit
            if time.monotonic() > expires:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class ShieldClient:
    """Accès en lecture à l'API Shield. Ne connaît aucune règle métier."""

    def __init__(self, base_url: str, headers: dict[str, str], timeout: int = DEFAULT_TIMEOUT):
        self.base_url = (base_url or "").rstrip("/")
        self.headers = headers
        self.timeout = timeout
        self._cache = _TTLCache()

    # ── Transport ────────────────────────────────────────────────────────────
    def _url(self, path: str, params: dict[str, Any] | None) -> str:
        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                url += "?" + urllib.parse.urlencode(clean)
        return url

    def _fetch(self, url: str) -> Any:
        request = urllib.request.Request(url, method="GET", headers=self.headers)
        with urllib.request.urlopen(request, timeout=self.timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ShieldError("payload", f"Réponse non-JSON de {url}") from exc

    def get_json(self, path: str, params: dict[str, Any] | None = None, *, use_cache: bool = True) -> Any:
        if not self.base_url:
            raise ShieldError("network", "URL de base Shield non configurée.")
        url = self._url(path, params)
        if use_cache:
            cached = self._cache.get(url)
            if cached is not None:
                return cached

        last: ShieldError | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                data = self._fetch(url)
                if use_cache:
                    self._cache.set(url, data)
                return data
            except urllib.error.HTTPError as exc:
                # 401/403 : la source répond, elle refuse. Réessayer est inutile
                # et masquerait un problème de configuration derrière un timeout.
                if exc.code in (401, 403):
                    raise ShieldError("auth", f"Accès refusé par Shield sur {path}", exc.code) from exc
                if exc.code < 500:
                    raise ShieldError("http", f"Shield a répondu {exc.code} sur {path}", exc.code) from exc
                last = ShieldError("http", f"Shield a répondu {exc.code} sur {path}", exc.code)
            except TimeoutError as exc:
                last = ShieldError("timeout", f"Délai dépassé sur {path}")
                last.__cause__ = exc
            except urllib.error.URLError as exc:
                reason = getattr(exc, "reason", exc)
                if isinstance(reason, TimeoutError):
                    last = ShieldError("timeout", f"Délai dépassé sur {path}")
                else:
                    last = ShieldError("network", f"Shield injoignable sur {path} : {reason}")
            except ShieldError as exc:
                raise exc
            except Exception as exc:  # noqa: BLE001 — filet : jamais de 500 qui remonte
                last = ShieldError("payload", f"Échec inattendu sur {path} : {type(exc).__name__}")

            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])

        assert last is not None
        logger.warning("Shield : %s", last)
        raise last

    # ── Lectures usuelles ────────────────────────────────────────────────────
    def count(self, path: str, params: dict[str, Any] | None = None) -> int:
        """Total d'une collection paginée DRF, sans rapatrier les lignes.

        `limit=1` suffit : c'est `count` qui porte le total. Descendre les
        milliers de lignes pour les compter serait absurde et lent.
        """
        data = self.get_json(path, {**(params or {}), "limit": 1})
        if isinstance(data, dict):
            if isinstance(data.get("count"), int):
                return data["count"]
            results = data.get("results")
            if isinstance(results, list):
                return len(results)
        if isinstance(data, list):
            return len(data)
        raise ShieldError("payload", f"Ni 'count' ni liste dans la réponse de {path}")

    def results(self, path: str, params: dict[str, Any] | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """Première page d'une collection, normalisée en liste de dicts."""
        data = self.get_json(path, {**(params or {}), "limit": limit})
        rows = data.get("results") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ShieldError("payload", f"Ni 'results' ni liste dans la réponse de {path}")
        return [r for r in rows if isinstance(r, dict)]

    def paginate(self, path: str, params: dict[str, Any] | None = None,
                 page_size: int = 200, max_pages: int = MAX_PAGES) -> list[dict[str, Any]]:
        """Parcourt les pages via offset, borné par `max_pages`.

        Le plafond est délibéré : une pagination non bornée sur une API distante
        est un moyen sûr de faire tomber le backend qui l'interroge.
        """
        rows: list[dict[str, Any]] = []
        for page in range(max_pages):
            batch = self.results(path, {**(params or {}), "offset": page * page_size}, limit=page_size)
            rows.extend(batch)
            if len(batch) < page_size:
                break
        return rows

    def healthcheck(self, path: str = "/api/v1/sites/sites/") -> tuple[bool, str]:
        """Sonde légère : la source répond-elle, et nous laisse-t-elle lire ?"""
        try:
            # `use_cache=False` : une sonde de santé doit interroger la source,
            # pas confirmer qu'on a déjà une réponse en mémoire.
            self.get_json(path, {"limit": 1}, use_cache=False)
            return True, "Shield joignable et lecture autorisée."
        except ShieldError as exc:
            return False, str(exc)

    def clear_cache(self) -> None:
        self._cache.clear()
