"""Moteur d'alertes de gouvernance (domaine pur, testé).

Une *règle* compare la valeur d'un indicateur à un seuil et, si elle est franchie,
émet une *alerte* d'une sévérité donnée. Principe gouverné (ADR-0007) : une valeur
absente (`None`) ne déclenche JAMAIS d'alerte — on n'invente pas un franchissement.

Le moteur est générique : la couche API l'alimente avec les valeurs réelles du mart
(scores de gouvernance aujourd'hui, autres métriques une fois les bindings branchés).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}
_OPERATORS = {
    "<": lambda v, t: v < t,
    "<=": lambda v, t: v <= t,
    ">": lambda v, t: v > t,
    ">=": lambda v, t: v >= t,
}


@dataclass(frozen=True)
class AlertRule:
    id: str
    label: str
    operator: str          # "<", "<=", ">", ">="
    threshold: float
    severity: str          # "info" | "warning" | "critical"

    def __post_init__(self) -> None:
        if self.operator not in _OPERATORS:
            raise ValueError(f"Opérateur inconnu : {self.operator!r}")
        if self.severity not in SEVERITY_ORDER:
            raise ValueError(f"Sévérité inconnue : {self.severity!r}")


@dataclass(frozen=True)
class Alert:
    rule_id: str
    label: str
    severity: str
    value: float
    threshold: float


def triggers(rule: AlertRule, value: Optional[float]) -> bool:
    """La règle se déclenche-t-elle ? `None` (donnée absente) → jamais (gouverné)."""
    if value is None:
        return False
    return _OPERATORS[rule.operator](value, rule.threshold)


def most_severe(rules: Iterable[AlertRule], value: Optional[float]) -> Optional[Alert]:
    """Alerte la PLUS sévère déclenchée par `value` parmi `rules`, sinon None.

    Évite d'empiler « < 70 (warning) » et « < 60 (critical) » : on ne garde que la pire.
    """
    if value is None:
        return None
    best: Optional[AlertRule] = None
    for r in rules:
        if triggers(r, value) and (best is None or SEVERITY_ORDER[r.severity] > SEVERITY_ORDER[best.severity]):
            best = r
    if best is None:
        return None
    return Alert(rule_id=best.id, label=best.label, severity=best.severity, value=value, threshold=best.threshold)


# Seuils de DÉMONSTRATION sur les scores de gouvernance (0–100).
# ⚠️ Proposition à valider par la direction (comme les pondérations de score).
SCORE_RULES: list[AlertRule] = [
    AlertRule("score_critique", "Score de gouvernance critique", "<", 60, "critical"),
    AlertRule("score_vigilance", "Score sous le seuil de vigilance", "<", 70, "warning"),
]

# Seuil sur une baisse de tendance mensuelle (points perdus sur le dernier mois).
TREND_DROP_RULES: list[AlertRule] = [
    AlertRule("chute_score", "Chute marquée du score sur un mois", ">=", 5, "warning"),
]
