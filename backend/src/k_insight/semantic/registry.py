"""Registre des métriques : structures + catalogue global.

Chaque métrique déclare son domaine, son unité, sa maille (grain), sa direction
(une hausse est-elle « bonne » ou « mauvaise » ?) et la table/mart qui la matérialise.
L'IA et les alertes s'appuient sur `direction` pour interpréter une variation sans
jugement codé en dur dans le prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    """Sens « favorable » d'une variation de la métrique."""

    HIGHER_IS_BETTER = "higher_is_better"   # ex. effectif productif, rentabilité
    LOWER_IS_BETTER = "lower_is_better"     # ex. turnover, absentéisme, coûts
    NEUTRAL = "neutral"                     # ex. effectif (ni bon ni mauvais en soi)


@dataclass(frozen=True)
class Metric:
    """Définition déclarative d'un indicateur de gouvernance."""

    key: str                 # identifiant stable, ex. "hr.turnover_rate"
    domain: str              # "hr", "finance", "fleet", "security"…
    label: str               # libellé humain (fr)
    unit: str                # "ratio", "XOF", "personnes", "jours"…
    grain: str               # maille minimale, ex. "filiale × mois"
    direction: Direction
    description: str
    mart: str                # mart/table de matérialisation, ex. "mart.hr_kpi"
    dimensions: tuple[str, ...] = field(default_factory=tuple)  # axes d'analyse


class MetricCatalog:
    """Catalogue indexé des métriques. Immuable après construction."""

    def __init__(self, metrics: list[Metric]) -> None:
        self._by_key: dict[str, Metric] = {}
        for m in metrics:
            if m.key in self._by_key:
                raise ValueError(f"Clé de métrique dupliquée : {m.key}")
            self._by_key[m.key] = m

    def get(self, key: str) -> Metric:
        if key not in self._by_key:
            raise KeyError(f"Métrique inconnue : {key!r} (l'IA ne doit pas l'inventer)")
        return self._by_key[key]

    def has(self, key: str) -> bool:
        return key in self._by_key

    def by_domain(self, domain: str) -> list[Metric]:
        return [m for m in self._by_key.values() if m.domain == domain]

    def all(self) -> list[Metric]:
        return list(self._by_key.values())

    def keys(self) -> list[str]:
        return list(self._by_key.keys())


# Le catalogue global est assemblé à partir des modules par domaine.
# On l'enrichira incrément après incrément (finance, fleet, security…).
from . import hr as _hr  # noqa: E402  (import après définition des classes, volontaire)

CATALOG = MetricCatalog(_hr.METRICS)
