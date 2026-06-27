"""Human Capital Score (0–100) — score de gouvernance RH consolidé (domaine pur, testé).

Moyenne pondérée de 9 dimensions stratégiques (pondérations fixées par la direction).
La *formule* fait foi ici ; les scores de dimension viennent du Data Warehouse (gouverné :
tant qu'une dimension n'est pas alimentée, elle est exclue et le score est renormalisé sur
les dimensions disponibles — jamais de valeur inventée).
"""

from __future__ import annotations

from typing import Mapping, Optional

from k_insight.kpi.score import ScoreDimension, weighted_score

__all__ = ["ScoreDimension", "HC_DIMENSIONS", "human_capital_score", "total_weight"]


# Somme des pondérations = 100 (vérifié par test).
HC_DIMENSIONS: list[ScoreDimension] = [
    ScoreDimension("effectifs_stabilite", "Effectifs & stabilité", 15),
    ScoreDimension("presence_ponctualite", "Présence & ponctualité", 10),
    ScoreDimension("productivite", "Productivité", 15),
    ScoreDimension("recrutement", "Recrutement", 10),
    ScoreDimension("performance", "Performance", 15),
    ScoreDimension("formation_competences", "Formation & compétences", 10),
    ScoreDimension("engagement_climat", "Engagement & climat social", 10),
    ScoreDimension("sante_securite", "Santé & sécurité", 10),
    ScoreDimension("conformite", "Conformité RH", 5),
]

_WEIGHTS = {d.key: d.weight for d in HC_DIMENSIONS}


def total_weight() -> int:
    return sum(d.weight for d in HC_DIMENSIONS)


def human_capital_score(dimension_scores: Mapping[str, float]) -> Optional[float]:
    """Score global 0–100 = moyenne pondérée des dimensions **disponibles** (cf. `weighted_score`).

    `dimension_scores` : { clé_dimension -> score 0..100 }. Les clés inconnues sont ignorées ;
    les dimensions absentes sont exclues et le score est renormalisé sur les poids présents.
    Retourne None si aucune dimension n'est disponible (→ « N/D » côté UI).
    """
    return weighted_score(dimension_scores, _WEIGHTS)
