"""Catalogue sémantique du domaine « immobilier » (GÉNÉRÉ).

Définitions déclaratives alignées sur le mart de matérialisation. Les VALEURS
viennent du Data Warehouse (gouverné N/D tant que la source n'est pas branchée).
Régénéré via scratchpad/gen_semantic.py depuis catalogs.json (workflow vérifié).
"""

from __future__ import annotations

from .registry import Direction, Metric

_DIMENSIONS = ("subsidiary", "period")

METRICS: list[Metric] = [
    Metric(
        key="immobilier.taux_securisation_fonciere",
        domain="immobilier",
        label="Taux de sécurisation foncière",
        unit="pourcentage",
        grain="filiale × programme × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des parcelles d'un programme disposant d'un titre foncier ou ACD régulier et purgé de tout litige, rapportée à la surface foncière totale du programme. Mesure le socle de risque patrimonial en zone UEMOA/OHADA.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.avancement_construction",
        domain="immobilier",
        label="Taux d'avancement construction",
        unit="pourcentage",
        grain="filiale × programme × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Avancement physique du chantier (gros œuvre et second œuvre) constaté à la date, rapporté au programme de travaux total. Reflète l'exécution opérationnelle réelle, distincte de l'encaissement client.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.avancement_vrd",
        domain="immobilier",
        label="Taux d'avancement VRD",
        unit="pourcentage",
        grain="filiale × programme × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Avancement des travaux de voirie et réseaux divers (voiries, assainissement, adduction, électricité) rapporté au lot VRD prévu. Conditionne la viabilisation des lots et leur livraison effective.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.taux_commercialisation",
        domain="immobilier",
        label="Taux de commercialisation",
        unit="pourcentage",
        grain="filiale × programme × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Nombre de lots, villas ou appartements réservés ou vendus rapporté au nombre total de lots du programme. Mesure l'écoulement commercial et la création de valeur des actifs.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.taux_occupation_locatif",
        domain="immobilier",
        label="Taux d'occupation locatif",
        unit="pourcentage",
        grain="filiale × programme × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Surface ou nombre de biens loués rapporté au parc locatif disponible du périmètre sur la période. Apprécie la liquidité et le rendement des actifs conservés en gestion locative.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.ecart_budget_projet",
        domain="immobilier",
        label="Écart budgétaire projet",
        unit="pourcentage",
        grain="filiale × programme × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Écart relatif entre le coût engagé cumulé et le budget prévisionnel du programme à la date. Une valeur positive signale un dépassement consommant la marge et la trésorerie projet.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.retard_jalons_livraison",
        domain="immobilier",
        label="Retard moyen sur jalons de livraison",
        unit="jours",
        grain="filiale × programme × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Décalage moyen, en jours, entre la date de livraison contractuelle des lots et la date réalisée ou reprévue, sur les jalons du programme. Mesure la tenue du planning et le respect des engagements clients.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.taux_frequence_accidents_chantier",
        domain="immobilier",
        label="Taux de fréquence des accidents de chantier",
        unit="ratio",
        grain="filiale × programme × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre d'accidents de chantier avec arrêt rapporté au volume d'heures travaillées sur la période (base normalisée). Mesure la sinistralité HSE et le risque humain et légal sur les chantiers.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="immobilier.couverture_risques_provisionnes",
        domain="immobilier",
        label="Taux de couverture des risques provisionnés",
        unit="pourcentage",
        grain="filiale × programme × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des risques immobiliers identifiés et cartographiés faisant l'objet d'une provision ou d'une couverture (assurance, garantie) rapportée à l'exposition totale recensée. Axe transverse d'anticipation et de gouvernance des risques.",
        mart="mart.immobilier_kpi",
        dimensions=_DIMENSIONS,
    ),
]
