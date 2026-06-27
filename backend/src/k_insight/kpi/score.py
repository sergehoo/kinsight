"""Moteur de score de gouvernance générique (domaine pur, testé).

Un *score de domaine* (0–100) est une moyenne pondérée de dimensions stratégiques.
La **formule** fait foi ici ; les scores de dimension viennent du Data Warehouse
(gouverné : tant qu'une dimension n'est pas alimentée, elle est exclue et le score
est renormalisé sur les dimensions disponibles — jamais de valeur inventée, ADR-0007).

Le Human Capital Score RH (`hr_score.py`) est une instance de ce moteur ; les autres
domaines (Immobilier, Finance, Opérations, Commercial, Risques) en sont d'autres
instances via le catalogue `domain_scores.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class ScoreDimension:
    key: str
    label: str
    weight: int  # pondération en %


def weighted_score(
    dimension_scores: Mapping[str, float],
    weights: Mapping[str, int],
) -> Optional[float]:
    """Score global 0–100 = moyenne pondérée des dimensions **disponibles**.

    `dimension_scores` : { clé_dimension -> score 0..100 }. Les clés absentes de
    `weights` sont ignorées ; les dimensions pondérées mais absentes des scores sont
    exclues et le total est renormalisé sur les poids présents. Retourne None si aucune
    dimension n'est disponible (→ « N/D » côté UI).
    """
    weighted = 0.0
    weight_sum = 0
    for key, score in dimension_scores.items():
        w = weights.get(key)
        if w is None:
            continue
        clamped = max(0.0, min(100.0, float(score)))
        weighted += clamped * w
        weight_sum += w
    if weight_sum == 0:
        return None
    return round(weighted / weight_sum, 1)
