"""Construction du contexte dynamique transmis au Copilot à chaque message.

Le contexte est dérivé du vrai profil de l'utilisateur (rôle, périmètre RBAC) et de l'état
courant de l'UI (module, page, filtres, période, filiale). Il fixe aussi la liste des
actions AUTORISÉES — l'IA ne se voit jamais proposer un outil hors de ses droits.
"""

from __future__ import annotations

from typing import Optional


def build_context(user, payload: Optional[dict] = None, registry=None) -> dict:
    payload = payload or {}
    scope = user.scope()
    try:
        year = int(payload.get("year", 2026))
        quarter = int(payload.get("quarter", 1))
    except (TypeError, ValueError):
        year, quarter = 2026, 1

    # Filiale : normalisée au périmètre RBAC (une filiale hors scope → "all", jamais imposée).
    # Note : l'accès aux données applique de toute façon le scope EN AMONT (value_resolver,
    # build_group_report) ; cette normalisation évite un libellé de contexte trompeur.
    subsidiary = payload.get("subsidiary") or "all"
    if subsidiary != "all" and not scope.allows(subsidiary):
        subsidiary = "all"

    allowed_actions: list[str] = []
    if registry is not None:
        allowed_actions = [t.name for t in registry.allowed_for(user)]

    return {
        "user": getattr(user, "username", None),
        "role": getattr(user, "role", ""),
        "can_see_nominative": bool(getattr(user, "can_see_nominative", False)),
        "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
        "module": payload.get("module") or "",
        "page": payload.get("page") or "",
        "period": {"year": year, "quarter": quarter},
        "subsidiary": subsidiary,
        "filters": payload.get("filters") or {},
        "allowed_actions": allowed_actions,
    }
