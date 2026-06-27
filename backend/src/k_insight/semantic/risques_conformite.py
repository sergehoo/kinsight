"""Catalogue sémantique du domaine « risques-conformite » (GÉNÉRÉ).

Définitions déclaratives alignées sur le mart de matérialisation. Les VALEURS
viennent du Data Warehouse (gouverné N/D tant que la source n'est pas branchée).
Régénéré via scratchpad/gen_semantic.py depuis catalogs.json (workflow vérifié).
"""

from __future__ import annotations

from .registry import Direction, Metric

_DIMENSIONS = ("subsidiary", "period")

METRICS: list[Metric] = [
    Metric(
        key="risques.taux_cloture_recommandations_audit",
        domain="risques-conformite",
        label="Taux de clôture des recommandations d'audit",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des recommandations d'audit clôturées rapportée au total des recommandations émises sur la période.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.recommandations_critiques_en_retard",
        domain="risques-conformite",
        label="Recommandations critiques en retard",
        unit="nombre",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre de recommandations d'audit de criticité élevée dont l'échéance de mise en oeuvre est dépassée et non clôturée.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.taux_couverture_controles_conformite",
        domain="risques-conformite",
        label="Taux de couverture des contrôles de conformité",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des contrôles de conformité exécutés et conformes rapportée au plan de contrôle attendu sur la période.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.taux_respect_sla_correctifs_securite",
        domain="risques-conformite",
        label="Taux de respect des SLA de correctifs de sécurité",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des vulnérabilités de sécurité corrigées dans le délai cible rapportée aux vulnérabilités identifiées sur la période.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.comptes_dormants_a_privileges",
        domain="risques-conformite",
        label="Comptes dormants à privilèges",
        unit="nombre",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre de comptes disposant de droits d'accès étendus sans connexion sur la période de référence définie.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.delai_moyen_resolution_incidents",
        domain="risques-conformite",
        label="Délai moyen de résolution des incidents",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Durée moyenne entre la déclaration et la clôture des incidents de risque ou de sécurité résolus sur la période.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.documents_critiques_expires",
        domain="risques-conformite",
        label="Documents critiques expirés",
        unit="nombre",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre de documents critiques (licences, agréments, polices, contrats) dont la date de validité est dépassée à la date d'arrêté.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.provision_litiges_actifs",
        domain="risques-conformite",
        label="Provision sur litiges juridiques actifs",
        unit="XOF",
        grain="filiale × mois",
        direction=Direction.NEUTRAL,
        description="Montant total des provisions comptabilisées au titre des litiges juridiques en cours à la date d'arrêté (francs CFA, entiers).",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="risques.taux_couverture_cartographie_risques",
        domain="risques-conformite",
        label="Taux de couverture de la cartographie des risques",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des risques cartographiés assortis d'un plan de maîtrise actif rapportée à l'ensemble des risques recensés.",
        mart="mart.risques_kpi",
        dimensions=_DIMENSIONS,
    ),
]
