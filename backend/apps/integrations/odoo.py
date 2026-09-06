"""Squelette connecteur Odoo RH (ADR-0003/0004) — AUCUN appel réel à ce stade.

Volontairement inerte : Shield est la source RH prioritaire et déjà branchée. Ce module
pose la structure (résolution de source, entités cibles, état gouverné) pour que le
branchement Odoo soit un ajout localisé, sans toucher au reste.

Gouvernance : tant que rien n'est implémenté, on renvoie un état EXPLICITE
(`not_configured` / `not_implemented`) — jamais de donnée, jamais de valeur simulée.
"""

from __future__ import annotations

from typing import Any

from .models import DataSource, SourceType

ODOO_SOURCE_SLUG = "odoo-hr"

# Modèles Odoo standard visés en lecture, par domaine K-Insight. Aucun endpoint
# n'est appelé ici : la couche transport (XML-RPC/JSON-RPC ou Airbyte) reste à décider.
ODOO_MODELS_BY_DOMAIN: dict[str, tuple[str, ...]] = {
    "rh": (
        "hr.employee",          # employés
        "hr.department",        # départements
        "hr.job",               # postes
        "hr.attendance",        # présence
        "hr.leave",             # congés
        "hr.applicant",         # recrutement
    ),
    "finance": ("account.move", "account.move.line", "account.account"),
    "operations": ("stock.picking", "purchase.order", "project.task"),
}

# Rétro-compatibilité : liste RH à plat (utilisée par la réponse `models`).
ODOO_HR_MODELS = ODOO_MODELS_BY_DOMAIN["rh"]


def get_odoo_source() -> DataSource | None:
    return (
        DataSource.objects.filter(source_type=SourceType.ODOO_HR, is_active=True).select_related("connector").first()
        or DataSource.objects.filter(slug=ODOO_SOURCE_SLUG).select_related("connector").first()
    )


def fetch_hr_reference() -> dict[str, Any]:
    """État gouverné du référentiel RH Odoo. Ne renvoie jamais de données.

    `not_configured` : aucune source Odoo déclarée.
    `not_implemented` : source déclarée, mais le transport Odoo n'est pas encore branché.
    """
    source = get_odoo_source()
    if source is None:
        return {
            "status": "not_configured",
            "source": "Odoo RH",
            "detail": "Aucune source Odoo RH déclarée.",
            "models": list(ODOO_HR_MODELS),
            "models_by_domain": {k: list(v) for k, v in ODOO_MODELS_BY_DOMAIN.items()},
            "records": [],
        }
    return {
        "status": "not_implemented",
        "source": source.name or "Odoo RH",
        "detail": "Source déclarée — connecteur Odoo non encore branché (priorité : Kaydan Shield).",
        "models": list(ODOO_HR_MODELS),
        "models_by_domain": {k: list(v) for k, v in ODOO_MODELS_BY_DOMAIN.items()},
        "records": [],
    }
