"""Catalogue sémantique du domaine « operations » (GÉNÉRÉ).

Définitions déclaratives alignées sur le mart de matérialisation. Les VALEURS
viennent du Data Warehouse (gouverné N/D tant que la source n'est pas branchée).
Régénéré via scratchpad/gen_semantic.py depuis catalogs.json (workflow vérifié).
"""

from __future__ import annotations

from .registry import Direction, Metric

_DIMENSIONS = ("subsidiary", "period")

METRICS: list[Metric] = [
    Metric(
        key="operations.stock_value",
        domain="operations",
        label="Valorisation des stocks",
        unit="XOF",
        grain="filiale × mois",
        direction=Direction.NEUTRAL,
        description="Valeur comptable des stocks détenus en fin de période (matériaux, fournitures, pièces, consommables), en francs CFA entiers.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.service_rate",
        domain="operations",
        label="Taux de service approvisionnement",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des besoins de chantier servis complets et à temps rapportés aux besoins exprimés sur la période.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.purchase_lead_time",
        domain="operations",
        label="Délai moyen demande-à-commande",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Délai moyen entre la validation d'une demande d'achat et l'émission de la commande fournisseur.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.inventory_accuracy",
        domain="operations",
        label="Taux de fiabilité des stocks",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des références dont la quantité physique inventoriée concorde avec le stock théorique, sur les campagnes de la période.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.fleet_availability",
        domain="operations",
        label="Taux de disponibilité de la flotte",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part du temps où les véhicules sont opérationnels rapportée au temps théorique d'exploitation, hors immobilisations.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.maintenance_mttr",
        domain="operations",
        label="Délai moyen de résolution maintenance",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Durée moyenne entre la déclaration d'une panne et la remise en service de l'équipement, sur les interventions clôturées.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.project_progress",
        domain="operations",
        label="Avancement moyen des projets",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Taux d'avancement physique moyen des projets et zones de travaux actifs en fin de période.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.supplier_on_time_rate",
        domain="operations",
        label="Taux de livraisons fournisseurs à temps",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des livraisons fournisseurs reçues à la date convenue rapportée au total des livraisons attendues.",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="operations.open_incidents",
        domain="operations",
        label="Incidents opérationnels ouverts",
        unit="nombre",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre d'incidents opérationnels non clôturés en fin de période (ruptures, retards, pannes, non-conformités).",
        mart="mart.operations_kpi",
        dimensions=_DIMENSIONS,
    ),
]
