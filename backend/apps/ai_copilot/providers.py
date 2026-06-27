"""Routage multi-provider du Copilot : DeepSeek (principal) → Claude (fallback) → repli
déterministe ancré (hors-ligne). Architecture extensible (OpenAI, Mistral…).

Garantie de gouvernance : les FAITS (métrique, valeur, source) sont calculés en amont par
l'ancrage (`semantic.grounding`) et passés au provider. Un LLM ne fait que reformuler autour
de ces faits — il ne doit ni inventer une métrique ni un chiffre. Hors-ligne ou en cas
d'échec de tous les LLM, on renvoie directement la phrase ancrée déterministe.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from django.conf import settings


class ProviderUnavailable(Exception):
    """Le provider ne peut pas répondre (clé absente, réseau, erreur API)."""


@dataclass
class GroundedFacts:
    """Faits ancrés (sortie de semantic.grounding.answer) servant de base factuelle."""

    grounded: bool
    answer: str
    metric: Optional[dict] = None
    value: Optional[float] = None
    source: Optional[str] = None


@dataclass
class ProviderResult:
    text: str
    provider: str
    latency_ms: int
    grounded: bool
    metric_key: str = ""
    attempts: list = field(default_factory=list)  # [{provider, ok, latency_ms, error}]


_RULES = (
    "Tu es K-Insight AI Copilot, assistant de gouvernance du Groupe Kaydan. RÈGLE ABSOLUE : "
    "ne jamais inventer de métrique ni de chiffre. Utilise UNIQUEMENT les faits fournis "
    "(catalogue, Data Warehouse). Si une donnée est indisponible, dis-le clairement et propose "
    "de configurer la source. Réponds en français, de façon factuelle et structurée."
)


class ProviderClient:
    name: str = "base"
    kind: str = "base"

    def is_available(self) -> bool:
        return False

    def complete(self, message: str, context: dict, facts: GroundedFacts) -> str:
        raise NotImplementedError


class OfflineGroundedProvider(ProviderClient):
    """Repli déterministe : renvoie la phrase ancrée telle quelle (aucune invention, aucune clé)."""

    name = "offline-grounded"
    kind = "offline"

    def is_available(self) -> bool:
        return True

    def complete(self, message: str, context: dict, facts: GroundedFacts) -> str:
        return facts.answer


class _HttpLLMClient(ProviderClient):
    """Base commune aux providers HTTP (DeepSeek/Claude). Réseau garde-fou par clé + timeout."""

    api_key_setting = ""
    timeout = 20

    def _key(self) -> str:
        return getattr(settings, self.api_key_setting, "") or ""

    def is_available(self) -> bool:
        return bool(self._key())

    def _system_prompt(self, context: dict, facts: GroundedFacts) -> str:
        ctx = json.dumps(context, ensure_ascii=False, default=str)
        fact = json.dumps(
            {"grounded": facts.grounded, "answer": facts.answer, "metric": facts.metric, "value": facts.value},
            ensure_ascii=False,
        )
        return f"{_RULES}\n\nCONTEXTE UTILISATEUR : {ctx}\n\nFAITS ANCRÉS (source de vérité) : {fact}"

    def _post(self, url: str, headers: dict, body: dict) -> dict:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderUnavailable(f"{self.name}: {exc}") from exc


class DeepSeekClient(_HttpLLMClient):
    name = "deepseek"
    kind = "deepseek"
    api_key_setting = "DEEPSEEK_API_KEY"

    def complete(self, message: str, context: dict, facts: GroundedFacts) -> str:
        if not self.is_available():
            raise ProviderUnavailable("deepseek: clé absente")
        base = getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = getattr(settings, "DEEPSEEK_MODEL", "deepseek-chat")
        out = self._post(
            f"{base}/chat/completions",
            {"Authorization": f"Bearer {self._key()}", "Content-Type": "application/json"},
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": self._system_prompt(context, facts)},
                    {"role": "user", "content": message},
                ],
                "stream": False,
            },
        )
        try:
            return out["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise ProviderUnavailable(f"deepseek: réponse inattendue ({exc})") from exc


class ClaudeClient(_HttpLLMClient):
    name = "claude"
    kind = "claude"
    api_key_setting = "ANTHROPIC_API_KEY"

    def complete(self, message: str, context: dict, facts: GroundedFacts) -> str:
        if not self.is_available():
            raise ProviderUnavailable("claude: clé absente")
        base = getattr(settings, "ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        model = getattr(settings, "AI_MODEL_SYNTHESIS", "claude-opus-4-8")
        out = self._post(
            f"{base}/v1/messages",
            {"x-api-key": self._key(), "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            {
                "model": model,
                "max_tokens": 1024,
                "system": self._system_prompt(context, facts),
                "messages": [{"role": "user", "content": message}],
            },
        )
        try:
            return out["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise ProviderUnavailable(f"claude: réponse inattendue ({exc})") from exc


# Ordre de fallback par défaut (DeepSeek principal → Claude → repli ancré toujours disponible).
def default_providers() -> list[ProviderClient]:
    return [DeepSeekClient(), ClaudeClient(), OfflineGroundedProvider()]


class AIProviderRouter:
    """Essaie les providers dans l'ordre ; renvoie la 1re réponse, en traçant chaque tentative."""

    def __init__(self, providers: Optional[list[ProviderClient]] = None) -> None:
        self._providers = providers if providers is not None else default_providers()

    def complete(self, message: str, context: dict, facts: GroundedFacts) -> ProviderResult:
        attempts: list[dict] = []
        for provider in self._providers:
            if not provider.is_available():
                attempts.append({"provider": provider.name, "ok": False, "error": "indisponible"})
                continue
            start = time.monotonic()
            try:
                text = provider.complete(message, context, facts)
                latency = int((time.monotonic() - start) * 1000)
                attempts.append({"provider": provider.name, "ok": True, "latency_ms": latency})
                return ProviderResult(
                    text=text,
                    provider=provider.name,
                    latency_ms=latency,
                    grounded=facts.grounded,
                    metric_key=(facts.metric or {}).get("key", "") if facts.metric else "",
                    attempts=attempts,
                )
            except ProviderUnavailable as exc:
                latency = int((time.monotonic() - start) * 1000)
                attempts.append({"provider": provider.name, "ok": False, "latency_ms": latency, "error": str(exc)})
                continue
        # Ne devrait jamais arriver : OfflineGroundedProvider est toujours disponible.
        raise ProviderUnavailable("Aucun provider disponible (repli ancré manquant ?).")
