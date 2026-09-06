"""Connecteur lecture Kaydan Shield → KPIs RH normalisés (ADR-0004).

Architecture imposée : Shield → CE backend → normalisation → API K-Insight → React.
React n'appelle JAMAIS Shield directement. Aucun endpoint n'est inventé : seuls les
chemins réels documentés dans l'OpenAPI Shield (/api/v1/...) sont utilisés.

Gouvernance « aucune donnée inventée » (ADR-0007) : tant que la source `kaydan-shield`
n'existe pas ou n'est pas connectée, on renvoie un état explicite `disconnected`
(valeurs nulles), jamais des chiffres fabriqués.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.utils import timezone

from .models import AuthMethod, CredentialKind, DataSource, SourceStatus, SourceType

SHIELD_SOURCE_SLUG = "kaydan-shield"

# Chemins RÉELS (OpenAPI Kaydan Shield, base /api/v1/). Ne rien inventer ici.
EP_EMPLOYEES = "/api/v1/employees/employees/"
EP_WORKERS = "/api/v1/ouvriers/workers/"
EP_SITES = "/api/v1/sites/sites/"
EP_ATTENDANCE_TODAY = "/api/v1/attendance/summary/today/"

_TIMEOUT = 8


# ── Résolution source / configuration ────────────────────────────────────────
def get_shield_source() -> DataSource | None:
    return (
        DataSource.objects.filter(source_type=SourceType.KAYDAN_SHIELD, is_active=True)
        .select_related("connector")
        .first()
        or DataSource.objects.filter(slug=SHIELD_SOURCE_SLUG).select_related("connector").first()
    )


def _base_url(source: DataSource) -> str:
    connector = getattr(source, "connector", None)
    url = (getattr(connector, "base_url", "") or "").rstrip("/")
    if not url:
        url = (getattr(settings, "SHIELD_BASE_URL", "") or "").rstrip("/")
    return url


def _pick_secret(connector) -> str:
    """Sélectionne le credential porteur du secret, de façon DÉTERMINISTE.

    `credentials.first()` seul est non déterministe (aucun `ordering` sur le modèle) :
    avec plusieurs identifiants (client_id + api_token…), on risquait d'envoyer le mauvais.
    On privilégie donc le token/clé API, puis le plus ancien, et on ignore les vides.
    """
    preferred = [CredentialKind.API_TOKEN, CredentialKind.API_KEY]
    queryset = connector.credentials.order_by("created_at")
    for cred in list(queryset.filter(kind__in=preferred)) + list(queryset.exclude(kind__in=preferred)):
        if cred.is_set:
            return cred.secret
    return ""


def _auth_headers(source: DataSource) -> dict[str, str]:
    """Construit les en-têtes d'auth depuis le connecteur (secrets chiffrés) ou l'env.

    HMAC Shield n'est pas encore implémenté ici (squelette) : on gère bearer / api_key /
    header personnalisé, sinon on retombe sur les headers non secrets déclarés.
    """
    headers: dict[str, str] = {"Accept": "application/json", "User-Agent": "k-insight"}
    connector = getattr(source, "connector", None)
    if connector is None:
        token = getattr(settings, "SHIELD_API_TOKEN", "") or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
    headers.update({k: str(v) for k, v in (connector.headers or {}).items()})
    secret = _pick_secret(connector) or (getattr(settings, "SHIELD_API_TOKEN", "") or "")
    if not secret:
        return headers
    if connector.auth_method in (AuthMethod.BEARER, AuthMethod.OAUTH2):
        headers["Authorization"] = f"Bearer {secret}"
    elif connector.auth_method == AuthMethod.API_KEY:
        name = (connector.config or {}).get("api_key_header", "X-API-Key")
        headers[name] = secret
    elif connector.auth_method == AuthMethod.HEADER:
        name = (connector.config or {}).get("auth_header", "Authorization")
        headers[name] = secret
    return headers


def _get_json(base: str, path: str, headers: dict[str, str], params: dict[str, Any] | None = None) -> Any:
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, method="GET", headers=headers)
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as resp:  # noqa: S310 — hôte configuré, interne
        return json.loads(resp.read().decode("utf-8"))


def _count(base: str, path: str, headers: dict[str, str]) -> int:
    """Total d'une liste paginée DRF (`count`), sinon longueur des résultats."""
    data = _get_json(base, path, headers, {"limit": 1})
    if isinstance(data, dict):
        if isinstance(data.get("count"), int):
            return data["count"]
        results = data.get("results")
        if isinstance(results, list):
            return len(results)
    if isinstance(data, list):
        return len(data)
    raise ValueError("Réponse inattendue (ni count ni liste).")


# ── Normalisation KPIs ───────────────────────────────────────────────────────
def _kpi(key: str, title: str, value: Any, unit: str = "", status: str = "connected") -> dict[str, Any]:
    return {"key": key, "title": title, "value": value, "unit": unit, "status": status}


def _disconnected_kpis(source_label: str) -> list[dict[str, Any]]:
    specs = [
        ("effectif_total", "Effectif total", ""),
        ("employes", "Employés", ""),
        ("ouvriers", "Ouvriers", ""),
        ("presents", "Présents aujourd'hui", ""),
        ("absents", "Absents", ""),
        ("retards", "Retards", ""),
        ("taux_presence", "Taux de présence", "%"),
        ("sites", "Sites", ""),
    ]
    return [_kpi(k, t, None, u, "disconnected") for k, t, u in specs]


def fetch_hr_kpis() -> dict[str, Any]:
    """Renvoie un état gouverné : disconnected | connected (avec KPIs) | error par KPI."""
    source = get_shield_source()
    label = "Kaydan Shield"
    if source is None:
        return {"status": "disconnected", "source": label, "detail": "Source kaydan-shield non configurée.", "kpis": _disconnected_kpis(label)}

    base = _base_url(source)
    connected = source.status == SourceStatus.CONNECTED
    if not base or not connected:
        return {
            "status": "disconnected",
            "source": source.name or label,
            "detail": "Source non connectée — configurez et testez la connexion.",
            "kpis": _disconnected_kpis(source.name or label),
        }

    headers = _auth_headers(source)
    src = source.name or label
    kpis: list[dict[str, Any]] = []

    def safe(fn):
        try:
            return fn(), None
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError, TimeoutError) as exc:
            return None, f"{type(exc).__name__}"

    employes, e_err = safe(lambda: _count(base, EP_EMPLOYEES, headers))
    ouvriers, o_err = safe(lambda: _count(base, EP_WORKERS, headers))
    sites, s_err = safe(lambda: _count(base, EP_SITES, headers))
    summary, sum_err = safe(lambda: _get_json(base, EP_ATTENDANCE_TODAY, headers))

    def st(err):
        return "error" if err else "connected"

    effectif = None
    if employes is not None and ouvriers is not None:
        effectif = employes + ouvriers
    kpis.append(_kpi("effectif_total", "Effectif total", effectif, "", st(e_err or o_err)))
    kpis.append(_kpi("employes", "Employés", employes, "", st(e_err)))
    kpis.append(_kpi("ouvriers", "Ouvriers", ouvriers, "", st(o_err)))

    present = absent = late = None
    if isinstance(summary, dict):
        present = summary.get("present_count")
        absent = summary.get("absent_count")
        late = summary.get("late_count")
    kpis.append(_kpi("presents", "Présents aujourd'hui", present, "", st(sum_err)))
    kpis.append(_kpi("absents", "Absents", absent, "", st(sum_err)))
    kpis.append(_kpi("retards", "Retards", late, "", st(sum_err)))

    taux = None
    if isinstance(present, int) and isinstance(absent, int) and (present + absent) > 0:
        taux = round(present * 100 / (present + absent), 1)
    kpis.append(_kpi("taux_presence", "Taux de présence", taux, "%", st(sum_err)))
    kpis.append(_kpi("sites", "Sites", sites, "", st(s_err)))

    # Statut global HONNÊTE : `partial` dès qu'une mesure manque, jamais « connected »
    # alors qu'une partie des appels a échoué.
    ok = sum(1 for k in kpis if k["status"] == "connected")
    if ok == len(kpis):
        status = "connected"
    elif ok:
        status = "partial"
    else:
        status = "error"
    return {"status": status, "source": src, "updated_at": timezone.now().isoformat(), "kpis": kpis}
