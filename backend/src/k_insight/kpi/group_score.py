"""Indice de Gouvernance Groupe — score consolidé du Groupe Kaydan (domaine pur, testé).

Moyenne pondérée des **scores de gouvernance par domaine** (RH + métiers). La formule
fait foi ici ; les scores de domaine viennent eux-mêmes du mart via leurs cadres
respectifs (`hr_score.py`, `domain_scores.py`). Gouverné : un domaine sans donnée est
exclu et l'indice est renormalisé sur les domaines disponibles (ADR-0007).

⚠️  PONDÉRATIONS DE DOMAINE = proposition à valider par la direction (comme les autres scores).
"""

from __future__ import annotations

from typing import Mapping, Optional

from k_insight.kpi.score import weighted_score

# (clé de domaine, libellé, pondération en %) — somme = 100 (vérifié par test).
GROUP_DOMAINS: list[tuple[str, str, int]] = [
    ("immobilier", "Immobilier", 22),
    ("finance", "Finance", 20),
    ("commercial-clients", "Commercial & Clients", 16),
    ("capital-humain", "Capital Humain", 16),
    ("operations", "Opérations", 14),
    ("risques-conformite", "Risques & Conformité", 12),
]

GROUP_DOMAIN_WEIGHTS = {key: weight for key, _label, weight in GROUP_DOMAINS}


def total_weight() -> int:
    return sum(weight for _k, _l, weight in GROUP_DOMAINS)


def group_governance_index(domain_globals: Mapping[str, float]) -> Optional[float]:
    """Indice Groupe 0–100 = moyenne pondérée des scores de domaine **disponibles**.

    `domain_globals` : { clé_domaine -> score global 0..100 }. Domaines inconnus ignorés ;
    domaines absents exclus et indice renormalisé sur les poids présents. None si vide.
    """
    return weighted_score(domain_globals, GROUP_DOMAIN_WEIGHTS)
