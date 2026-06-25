"""Types et helpers transverses du moteur de KPI.

Conventions (cohérentes avec AUGUSTINE, cf. ADR-0008) :
- Les montants sont des **entiers XOF** (0 décimale). Jamais de float pour l'argent.
- Les périodes sont **demi-ouvertes** : [start, end[ pour les flux (paie, mouvements),
  et on évalue les *stocks* (effectif) à une date instantanée donnée.
- Aucune dépendance externe : `datetime`, `dataclasses`, `collections` uniquement.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Hashable, Iterable, Sequence, TypeVar

T = TypeVar("T")
K = TypeVar("K", bound=Hashable)


class KpiError(ValueError):
    """Erreur de cohérence dans un calcul de KPI (entrée invalide)."""


@dataclass(frozen=True)
class Period:
    """Période d'analyse, bornes demi-ouvertes [start, end[.

    `start` est inclus, `end` est exclu. Une période RH « 1er trimestre 2026 »
    s'exprime donc `Period(date(2026, 1, 1), date(2026, 4, 1))`.
    """

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise KpiError(f"Période invalide : end={self.end} <= start={self.start}")

    def contains(self, d: date) -> bool:
        """Vrai si `d` appartient à [start, end[."""
        return self.start <= d < self.end

    @property
    def last_instant(self) -> date:
        """Dernier instant *inclus* dans la période (end exclu => end n'en fait pas partie)."""
        return self.end


@dataclass(frozen=True)
class MetricResult:
    """Résultat d'un KPI : valeur + unité + contexte (période, dimensions).

    `value` est `int` (effectifs, montants XOF) ou `float` (taux, ratios).
    `dimensions` porte le découpage (filiale, département…) quand le résultat
    est ventilé ; vide pour un agrégat groupe.
    """

    key: str
    value: float
    unit: str
    period: Period
    dimensions: dict[str, str] = field(default_factory=dict)


def aggregate_by(
    items: Iterable[T],
    key_fn: Callable[[T], K],
    value_fn: Callable[[T], float],
) -> dict[K, float]:
    """Somme `value_fn` par clé `key_fn`. Base de toute ventilation (par filiale, etc.)."""
    out: dict[K, float] = defaultdict(float)
    for it in items:
        out[key_fn(it)] += value_fn(it)
    return dict(out)


def safe_ratio(numerator: float, denominator: float) -> float:
    """Ratio robuste : retourne 0.0 si le dénominateur est nul (évite la division par zéro)."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def pct_change(previous: float, current: float) -> float:
    """Variation relative (current - previous) / |previous|. 0.0 si previous == 0."""
    if previous == 0:
        return 0.0
    return (current - previous) / abs(previous)
