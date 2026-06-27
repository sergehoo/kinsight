"""Registre des liaisons module ↔ mart (gabarit de branchement des données réelles).

Une clé de module liée fournit des **valeurs réelles** calculées depuis un mart.
Les clés non liées restent gouvernées (l'API répond `available: false` et le frontend
conserve l'affichage « N/D — mart à connecter »). On étend ce registre mart par mart.

Les libellés ci-dessous doivent correspondre EXACTEMENT aux libellés KPI déclarés côté
frontend (`lib/modules.tsx`) pour que la valeur réelle remplace le N/D de la bonne carte.
"""

# metric ∈ {"payroll", "entries", "exits", "net"} — calculés depuis mart.hr_kpi
HR_MART_SOURCE = "mart.hr_kpi"

HR_BINDINGS: dict[str, dict[str, str]] = {
    "hr-executive": {
        "Masse salariale": "payroll",
        "Recrutements": "entries",
        "Départs": "exits",
    },
    "hr-payroll": {
        "Masse salariale": "payroll",
    },
}


def hr_binding(key: str) -> dict[str, str] | None:
    return HR_BINDINGS.get(key)
