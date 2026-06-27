"""Catalogue des Scores de Gouvernance par domaine (domaine pur, GÉNÉRÉ).

Source de vérité des dimensions + pondérations de chaque domaine métier. Le moteur
`score.weighted_score` calcule le score global ; les valeurs viennent du mart
(`mart.domain_score`), gouverné N/D tant qu'une dimension n'est pas alimentée (ADR-0007).

⚠️  PONDÉRATIONS = proposition à valider par la direction (comme le Human Capital Score).
Régénéré via scratchpad/gen_domain_scores.py à partir de frameworks.json (workflow vérifié).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from k_insight.kpi.score import weighted_score


@dataclass(frozen=True)
class DomainDimension:
    key: str
    label: str
    weight: int  # pondération en %
    mart_source: str  # table mart réceptacle (donnée réelle à brancher)
    rationale: str


@dataclass(frozen=True)
class DomainScoreFramework:
    domain: str
    label: str
    dimensions: tuple[DomainDimension, ...]

    def weights(self) -> dict[str, int]:
        return {d.key: d.weight for d in self.dimensions}

    def total_weight(self) -> int:
        return sum(d.weight for d in self.dimensions)


DOMAIN_SCORES: dict[str, DomainScoreFramework] = {
    "immobilier": DomainScoreFramework(
        domain="immobilier",
        label="Score de Gouvernance Immobilier",
        dimensions=(
            DomainDimension(
                key="maitrise_fonciere",
                label="Maîtrise foncière",
                weight=20,
                mart_source="mart.immobilier_maitrise_fonciere",
                rationale="Sécurisation des titres et régularité juridique du foncier : socle du risque patrimonial en zone UEMOA.",
            ),
            DomainDimension(
                key="execution_programmes",
                label="Exécution des programmes et chantiers",
                weight=22,
                mart_source="mart.immobilier_execution_programmes",
                rationale="Respect des jalons, délais et conformité de livraison : cœur de la performance opérationnelle des projets.",
            ),
            DomainDimension(
                key="discipline_financiere",
                label="Discipline financière des projets",
                weight=20,
                mart_source="mart.immobilier_discipline_financiere",
                rationale="Maîtrise budgétaire, financement et trésorerie projet : garantit la soutenabilité économique des opérations.",
            ),
            DomainDimension(
                key="performance_commerciale",
                label="Performance commerciale et locative",
                weight=16,
                mart_source="mart.immobilier_performance_commerciale",
                rationale="Taux d'écoulement, d'occupation et de recouvrement : mesure la création de valeur et la liquidité des actifs.",
            ),
            DomainDimension(
                key="securite_chantier",
                label="Sécurité et conformité de chantier",
                weight=12,
                mart_source="mart.immobilier_securite_chantier",
                rationale="HSE, sinistralité et conformité réglementaire : maîtrise du risque humain et légal sur les chantiers.",
            ),
            DomainDimension(
                key="pilotage_risques",
                label="Pilotage des risques immobiliers",
                weight=10,
                mart_source="mart.immobilier_pilotage_risques",
                rationale="Identification, couverture et provisionnement des risques : axe de gouvernance transverse et d'anticipation.",
            ),
        ),
    ),
    "finance": DomainScoreFramework(
        domain="finance",
        label="Score de Gouvernance Finance",
        dimensions=(
            DomainDimension(
                key="liquidite_tresorerie",
                label="Liquidité & couverture de trésorerie",
                weight=22,
                mart_source="mart.finance_liquidite_tresorerie",
                rationale="Mesure la capacité à honorer les engagements à court terme (jours de couverture, soldes positifs), socle de la solvabilité du Groupe.",
            ),
            DomainDimension(
                key="qualite_poste_clients",
                label="Qualité du poste clients",
                weight=18,
                mart_source="mart.finance_qualite_poste_clients",
                rationale="Apprécie la maîtrise du crédit clients (DSO, ancienneté, taux de créances douteuses) pour limiter l'immobilisation et les pertes.",
            ),
            DomainDimension(
                key="discipline_budgetaire",
                label="Discipline budgétaire",
                weight=18,
                mart_source="mart.finance_discipline_budgetaire",
                rationale="Evalue le respect des enveloppes et la faible amplitude des écarts réel/budget, gage de contrôle des dépenses.",
            ),
            DomainDimension(
                key="conformite_fiscale",
                label="Conformité fiscale & réglementaire",
                weight=16,
                mart_source="mart.finance_conformite_fiscale",
                rationale="Suit le respect des échéances et obligations fiscales (OHADA/UEMOA) afin d'éviter pénalités et risques de redressement.",
            ),
            DomainDimension(
                key="maitrise_risques_financiers",
                label="Maîtrise des risques financiers",
                weight=16,
                mart_source="mart.finance_maitrise_risques_financiers",
                rationale="Quantifie l'exposition aux risques de change XOF, de contrepartie et de concentration, ainsi que les couvertures mises en place pour la contenir (la liquidité étant suivie à part).",
            ),
            DomainDimension(
                key="fiabilite_previsionnelle",
                label="Fiabilité prévisionnelle",
                weight=10,
                mart_source="mart.finance_fiabilite_previsionnelle",
                rationale="Mesure la précision des prévisions face au réalisé, indicateur de la qualité du pilotage financier anticipé.",
            ),
        ),
    ),
    "operations": DomainScoreFramework(
        domain="operations",
        label="Score de Gouvernance Opérations",
        dimensions=(
            DomainDimension(
                key="maitrise_stocks",
                label="Maîtrise des stocks",
                weight=20,
                mart_source="mart.operations_maitrise_stocks",
                rationale="Mesure la fiabilité et la disponibilité des stocks (ruptures, surstocks, dormants) pour éviter immobilisation de capital et arrêts d'activité.",
            ),
            DomainDimension(
                key="fiabilite_inventaires",
                label="Fiabilité des inventaires",
                weight=12,
                mart_source="mart.operations_fiabilite_inventaires",
                rationale="Évalue l'écart entre stock théorique et physique, gage d'intégrité comptable et de lutte contre la démarque et la fraude.",
            ),
            DomainDimension(
                key="integrite_achats",
                label="Intégrité du cycle achats",
                weight=18,
                mart_source="mart.operations_integrite_achats",
                rationale="Contrôle la conformité du processus achats (engagements approuvés, mise en concurrence, séparation des tâches) pour prévenir surcoûts et corruption.",
            ),
            DomainDimension(
                key="performance_fournisseurs",
                label="Performance fournisseurs",
                weight=13,
                mart_source="mart.operations_performance_fournisseurs",
                rationale="Apprécie la qualité, les délais et la dépendance vis-à-vis des fournisseurs, axe clé de continuité d'approvisionnement et de réduction du risque tiers.",
            ),
            DomainDimension(
                key="disponibilite_actifs",
                label="Disponibilité des actifs",
                weight=15,
                mart_source="mart.operations_disponibilite_actifs",
                rationale="Suit le taux de disponibilité et la maintenance préventive des équipements et de la flotte, garant de la continuité opérationnelle et de la sécurité.",
            ),
            DomainDimension(
                key="maitrise_couts",
                label="Maîtrise des coûts opérationnels",
                weight=12,
                mart_source="mart.operations_maitrise_couts",
                rationale="Mesure le respect des budgets opérationnels et la dérive des coûts unitaires, indicateur de discipline financière et d'efficience.",
            ),
            DomainDimension(
                key="maitrise_risques_ops",
                label="Maîtrise des risques opérationnels",
                weight=10,
                mart_source="mart.operations_maitrise_risques_ops",
                rationale="Évalue l'identification, la couverture et le traitement des risques opérationnels (HSE, incidents, plans d'action) pour limiter pertes et responsabilités.",
            ),
        ),
    ),
    "commercial-clients": DomainScoreFramework(
        domain="commercial-clients",
        label="Score de Gouvernance Commercial & Clients",
        dimensions=(
            DomainDimension(
                key="fiabilite_donnees_crm",
                label="Fiabilité des données CRM",
                weight=22,
                mart_source="mart.commercial_clients_fiabilite_donnees_crm",
                rationale="Mesure l'hygiène du référentiel client (complétude, unicité, fraîcheur) qui conditionne la confiance dans toute décision commerciale.",
            ),
            DomainDimension(
                key="maitrise_pipeline",
                label="Maîtrise du pipeline",
                weight=20,
                mart_source="mart.commercial_clients_maitrise_pipeline",
                rationale="Évalue la santé et la prévisibilité du tunnel de vente (couverture, vieillissement, stades documentés) pour limiter le risque de tarissement du chiffre d'affaires.",
            ),
            DomainDimension(
                key="conformite_contractuelle",
                label="Conformité contractuelle",
                weight=20,
                mart_source="mart.commercial_clients_conformite_contractuelle",
                rationale="Apprécie la sécurisation des engagements (contrats signés, clauses conformes, délais respectés) afin de réduire l'exposition juridique et financière du Groupe.",
            ),
            DomainDimension(
                key="maitrise_reclamations",
                label="Maîtrise des réclamations",
                weight=16,
                mart_source="mart.commercial_clients_maitrise_reclamations",
                rationale="Contrôle le traitement des réclamations (délai de résolution, taux de récurrence, escalades) qui matérialise le risque réputationnel et réglementaire.",
            ),
            DomainDimension(
                key="tenue_satisfaction_client",
                label="Tenue de la satisfaction client",
                weight=12,
                mart_source="mart.commercial_clients_tenue_satisfaction_client",
                rationale="Suit le niveau et la mesure régulière de la satisfaction comme signal avancé du risque relationnel et de perte de clientèle.",
            ),
            DomainDimension(
                key="fiabilite_previsions_ventes",
                label="Fiabilité des prévisions de ventes",
                weight=10,
                mart_source="mart.commercial_clients_fiabilite_previsions_ventes",
                rationale="Mesure l'écart prévisions/réalisé et la discipline de mise à jour du forecast, gage de pilotage fiable et de crédibilité du reporting de direction.",
            ),
        ),
    ),
    "risques-conformite": DomainScoreFramework(
        domain="risques-conformite",
        label="Score de Gouvernance Risques & Conformité",
        dimensions=(
            DomainDimension(
                key="maitrise_des_risques",
                label="Maîtrise des risques",
                weight=22,
                mart_source="mart.risques_conformite_maitrise_des_risques",
                rationale="Mesure la couverture et le traitement effectif des risques cartographiés (résiduel vs brut), cœur de la maîtrise de la gouvernance.",
            ),
            DomainDimension(
                key="conformite_reglementaire",
                label="Conformité réglementaire",
                weight=20,
                mart_source="mart.risques_conformite_conformite_reglementaire",
                rationale="Évalue le respect des obligations légales et réglementaires (UEMOA/XOF) et la résorption des écarts de conformité ouverts.",
            ),
            DomainDimension(
                key="posture_securite",
                label="Posture de sécurité",
                weight=18,
                mart_source="mart.risques_conformite_posture_securite",
                rationale="Apprécie le niveau de protection des actifs et la réduction des vulnérabilités exposant le Groupe et ses filiales.",
            ),
            DomainDimension(
                key="assurance_audit",
                label="Assurance par l'audit",
                weight=15,
                mart_source="mart.risques_conformite_assurance_audit",
                rationale="Reflète la réalisation du plan d'audit et la clôture des recommandations, gage d'indépendance et de fiabilité du contrôle interne.",
            ),
            DomainDimension(
                key="gestion_incidents",
                label="Gestion des incidents",
                weight=13,
                mart_source="mart.risques_conformite_gestion_incidents",
                rationale="Mesure la capacité de détection, de réaction et de résolution des incidents (délais, récurrence, gravité résiduelle).",
            ),
            DomainDimension(
                key="exposition_juridique",
                label="Exposition juridique",
                weight=12,
                mart_source="mart.risques_conformite_exposition_juridique",
                rationale="Quantifie l'exposition aux contentieux et engagements à risque, et la maîtrise de la provision juridique du Groupe.",
            ),
        ),
    ),
}


def domain_score(domain: str, dimension_scores: Mapping[str, float]) -> Optional[float]:
    """Score global 0–100 d'un domaine ; None si domaine inconnu ou aucune dimension dispo."""
    framework = DOMAIN_SCORES.get(domain)
    if framework is None:
        return None
    return weighted_score(dimension_scores, framework.weights())
