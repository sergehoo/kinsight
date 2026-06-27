"""Catalogue sémantique du domaine « finance » (GÉNÉRÉ).

Définitions déclaratives alignées sur le mart de matérialisation. Les VALEURS
viennent du Data Warehouse (gouverné N/D tant que la source n'est pas branchée).
Régénéré via scratchpad/gen_semantic.py depuis catalogs.json (workflow vérifié).
"""

from __future__ import annotations

from .registry import Direction, Metric

_DIMENSIONS = ("subsidiary", "period")

METRICS: list[Metric] = [
    Metric(
        key="finance.tresorerie_nette",
        domain="finance",
        label="Trésorerie nette",
        unit="XOF",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Solde net de trésorerie en fin de période (disponibilités et équivalents diminués des découverts et concours bancaires courants), en francs CFA entiers.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.jours_couverture_tresorerie",
        domain="finance",
        label="Jours de couverture de trésorerie",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Nombre de jours de décaissements opérationnels que la trésorerie disponible permet de couvrir, mesurant le coussin de liquidité.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.dso",
        domain="finance",
        label="Délai moyen de recouvrement client (DSO)",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Nombre moyen de jours entre la facturation et l'encaissement des créances clients sur la période.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.taux_recouvrement",
        domain="finance",
        label="Taux de recouvrement",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des créances échues effectivement encaissées sur la période, rapportée au total des créances échues attendues.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.dpo",
        domain="finance",
        label="Délai moyen de règlement fournisseurs (DPO)",
        unit="jours",
        grain="filiale × mois",
        direction=Direction.NEUTRAL,
        description="Nombre moyen de jours entre la réception d'une facture fournisseur et son règlement ; un délai élevé soulage la trésorerie mais peut dégrader la relation fournisseur, d'où une direction neutre.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.ecart_budgetaire",
        domain="finance",
        label="Écart budgétaire (réel vs budget)",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.LOWER_IS_BETTER,
        description="Amplitude de l'écart entre dépenses réelles et budget alloué sur la période, en valeur absolue rapportée au budget ; un faible écart traduit la discipline budgétaire.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.marge_operationnelle",
        domain="finance",
        label="Marge opérationnelle",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Résultat d'exploitation rapporté au chiffre d'affaires de la période, mesurant la rentabilité dégagée par l'activité courante.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.taux_conformite_fiscale",
        domain="finance",
        label="Taux de respect des échéances fiscales",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Part des obligations fiscales et déclaratives (OHADA/UEMOA) honorées dans les délais légaux sur la période, rapportée au total des échéances dues.",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
    Metric(
        key="finance.fiabilite_prevision_tresorerie",
        domain="finance",
        label="Fiabilité des prévisions de trésorerie",
        unit="pourcentage",
        grain="filiale × mois",
        direction=Direction.HIGHER_IS_BETTER,
        description="Précision des prévisions de trésorerie sur la période, exprimée comme le complément de l'erreur relative moyenne entre trésorerie prévue et réalisée (une erreur faible donne une fiabilité élevée).",
        mart="mart.finance_kpi",
        dimensions=_DIMENSIONS,
    ),
]
