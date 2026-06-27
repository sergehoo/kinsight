"""Résolution métrique → valeur réelle du mart (binding, Phase 6).

Fournit le `value_lookup` utilisé par l'ancrage. Aujourd'hui seul le mart RH (`mart.hr_kpi`)
est câblé bout-en-bout : `hr.payroll_mass / hr.entries / hr.exits` renvoient de VRAIES valeurs
(filtrées par périmètre RBAC + filiale). Les autres métriques restent None → N/D gouverné
tant que leur mart n'est pas branché. Toute indisponibilité du mart → None (jamais d'erreur,
jamais de 0 inventé)."""

from __future__ import annotations

from typing import Callable, Optional


def build_value_lookup(user, year: int, quarter: int, subsidiary: str = "all") -> Callable[[str], Optional[float]]:
    values: dict[str, float] = {}
    try:
        from apps.governance.gateway import get_mart_gateway
        from apps.governance.services import period_from_quarter
        from k_insight.access import filter_by_scope
        from k_insight.kpi.hr_mart import total_entries, total_exits, total_payroll_mass

        period = period_from_quarter(year, quarter)
        scope = user.scope()
        rows = filter_by_scope(get_mart_gateway().fetch_hr_kpi(), scope, key=lambda r: r.subsidiary)
        if subsidiary and subsidiary != "all":
            rows = [r for r in rows if r.subsidiary == subsidiary]
        values = {
            "hr.payroll_mass": float(total_payroll_mass(rows, period)),
            "hr.entries": float(total_entries(rows, period)),
            "hr.exits": float(total_exits(rows, period)),
        }
    except Exception:  # noqa: BLE001 — mart indisponible → tout N/D (gouverné), jamais de crash
        values = {}

    def lookup(key: str) -> Optional[float]:
        return values.get(key)

    return lookup
