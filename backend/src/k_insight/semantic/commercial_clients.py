"""Catalogue sémantique du domaine « commercial-clients » (GÉNÉRÉ).

Définitions déclaratives alignées sur le mart de matérialisation. Les VALEURS
viennent du Data Warehouse (gouverné N/D tant que la source n'est pas branchée).
Régénéré via scratchpad/gen_semantic.py depuis catalogs.json (workflow vérifié).
"""

from __future__ import annotations

from .registry import Direction, Metric

_DIMENSIONS = ("subsidiary", "period")

METRICS: list[Metric] = [
    Metric(
        key="commercial.taux_conversion_pipeline",
        domain="commercial-clients",
        label="Taux de conversion du pipeline",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des opportunités du pipeline aboutissant à une vente signée sur la période, rapportée aux opportunités sorties du pipeline (gagnées + perdues).",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.delai_moyen_cycle_vente",
        domain="commercial-clients",
        label="Délai moyen du cycle de vente",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre moyen de jours entre la qualification d'un prospect et la signature de la vente, pour les ventes conclues sur la période.",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.chiffre_affaires_signe",
        domain="commercial-clients",
        label="Chiffre d'affaires signé",
        unit="XOF",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Montant total des ventes signées sur la période, exprimé en francs CFA (entiers).",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.taux_concretisation_reservations",
        domain="commercial-clients",
        label="Taux de concrétisation des réservations",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des réservations de la période transformées en contrat signé, rapportée au total des réservations enregistrées.",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.delai_traitement_reclamation",
        domain="commercial-clients",
        label="Délai de traitement des réclamations",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre moyen de jours entre l'ouverture et la clôture d'une réclamation client résolue sur la période.",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.satisfaction_client",
        domain="commercial-clients",
        label="Satisfaction client moyenne",
        unit="note",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Note moyenne de satisfaction issue des enquêtes clients clôturées sur la période.",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.taux_retention_clients",
        domain="commercial-clients",
        label="Taux de rétention clients",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des clients actifs en début de période toujours actifs en fin de période, rapportée au stock initial de clients actifs.",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.fiabilite_previsions_ventes",
        domain="commercial-clients",
        label="Fiabilité des prévisions de ventes",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Taux d'adhérence des prévisions de ventes au réalisé : complément de l'écart absolu entre ventes réalisées et ventes prévues, rapporté aux ventes prévues. Une valeur proche de 100 % traduit une prévision fiable ; toute sous- ou sur-réalisation dégrade l'indicateur.",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="commercial.qualite_donnees_crm",
        domain="commercial-clients",
        label="Qualité des données CRM",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des fiches clients du CRM dont les champs de gouvernance obligatoires sont renseignés, rapportée au total des fiches actives.",
        mart="mart.commercial_kpi",
        dimensions=_DIMENSIONS,
    ),
]
