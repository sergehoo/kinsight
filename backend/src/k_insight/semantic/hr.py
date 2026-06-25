"""Catalogue sémantique du domaine RH (1er incrément).

Ces définitions doivent rester alignées avec les fonctions de `kpi/hr.py`
(même clé = même sémantique) et avec le mart `mart.hr_kpi`.
"""

from __future__ import annotations

from .registry import Direction, Metric

_DIMENSIONS = ("subsidiary", "department", "period")

METRICS: list[Metric] = [
    Metric(
        key="hr.headcount",
        domain="hr",
        label="Effectif",
        unit="personnes",
        grain="filiale × département × jour",
        direction=Direction.NEUTRAL,
        description="Nombre de salariés en poste à une date (stock).",
        mart="mart.hr_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="hr.entries",
        domain="hr",
        label="Entrées",
        unit="personnes",
        grain="filiale × département × mois",
        direction=Direction.NEUTRAL,
        description="Embauches dont la date tombe dans la période.",
        mart="mart.hr_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="hr.exits",
        domain="hr",
        label="Sorties",
        unit="personnes",
        grain="filiale × département × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Départs dont la date tombe dans la période.",
        mart="mart.hr_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="hr.turnover_rate",
        domain="hr",
        label="Taux de turnover",
        unit="ratio",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Départs sur la période rapportés à l'effectif moyen.",
        mart="mart.hr_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="hr.absenteeism_rate",
        domain="hr",
        label="Taux d'absentéisme",
        unit="ratio",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Jours d'absence rapportés aux jours théoriques travaillés.",
        mart="mart.hr_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="hr.payroll_mass",
        domain="hr",
        label="Masse salariale (brut)",
        unit="XOF",
        grain="filiale × département × mois",
        direction=Direction.NEUTRAL,
        description="Somme des salaires bruts sur la période (francs CFA, entiers).",
        mart="mart.hr_kpi",
        dimensions=_DIMENSIONS,
    ),
]
