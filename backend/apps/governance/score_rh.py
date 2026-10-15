"""Score de gouvernance RH calculé sur données RÉELLES (historique Shield + Odoo).

LA FORMULE NE CHANGE PAS. Neuf dimensions, poids fixés par la direction
(`k_insight.kpi.hr_score`), moyenne pondérée, aucune valeur inventée. Ce qui
change, ce sont les ENTRÉES : elles venaient de `mart.hr_score`, que seul un jeu
de démonstration alimentait — et l'écran l'affichait « Données EDW — réel ».

UNE DIMENSION N'EST SCORÉE QUE SI SES DONNÉES LE PERMETTENT.
  Présence & ponctualité — taux de présence et de ponctualité de la période,
  convertis par une règle LINÉAIRE et écrite (ci-dessous). Exige les deux taux,
  et une couverture d'au moins la moitié des jours.
  Les huit autres — aucune source dans l'architecture Shield + Odoo : N/D avec
  le motif, jamais 0.

LE SCORE GLOBAL EXIGE UNE COUVERTURE. La renormalisation sur les seules
dimensions disponibles produirait un « score global » à partir de la seule
présence (10 % du poids) — un chiffre d'apparence consolidée qui ne mesure
qu'un dixième de ce qu'il prétend. Le global n'est donc calculé que si les
dimensions scorées représentent au moins `COUVERTURE_GLOBALE_MIN` du poids
total ; en deçà il est N/D, et la réponse dit pourquoi.

PÉRIMÈTRE. La dimension Présence repose sur Shield, dont les chiffres sont des
chiffres Groupe (ADR-0009) : un périmètre restreint la reçoit N/D « non rattaché ».
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.integrations import shield_rules as R
from k_insight.kpi.hr_score import HC_DIMENSIONS, total_weight

from . import historique as H
from .filtres import FiltreInvalide, Filtres
from .lecture_rh import portee
from .hr_registry import REGISTRE

# ── Règles de conversion, écrites une fois ───────────────────────────────────
# Présence : 0 point au seuil critique de `shield_rules` (la journée y est jugée
# compromise), 100 points à l'objectif. Linéaire entre les deux, borné.
PRESENCE_PLANCHER = R.PRESENCE_CRITIQUE          # 70 %
PRESENCE_OBJECTIF = 95.0
# Ponctualité : 0 point à 85 % de présents à l'heure, 100 points à 99 %.
PONCTUALITE_PLANCHER = 85.0
PONCTUALITE_OBJECTIF = 99.0
# Part minimale de jours mesurés pour qu'une dimension soit scorée.
COUVERTURE_DIMENSION_MIN = 0.5
# Part minimale du poids total couverte pour publier un score global.
COUVERTURE_GLOBALE_MIN = 50

FORMULE_PRESENCE = (
    f"moyenne de deux sous-scores linéaires bornés 0–100 : présence "
    f"({PRESENCE_PLANCHER:g} % → 0, {PRESENCE_OBJECTIF:g} % → 100) et ponctualité "
    f"({PONCTUALITE_PLANCHER:g} % → 0, {PONCTUALITE_OBJECTIF:g} % → 100)"
)

MOTIFS_SANS_SOURCE: dict[str, str] = {
    "effectifs_stabilite": "Turnover et mouvements non mesurés : les dates d'entrée et de sortie ne sont pas lues dans Odoo.",
    "productivite": "Aucune mesure de production rapportée au temps travaillé : les heures ne sont pas servies.",
    "recrutement": "Le recrutement Odoo (hr.applicant) n'est encore que compté, sans délais ni conversions.",
    "performance": "Aucune évaluation de performance n'est lue (module Odoo non raccordé).",
    "formation_competences": "Aucune donnée de formation ni de compétences n'est lue.",
    "engagement_climat": "Aucune enquête d'engagement n'est raccordée.",
    "sante_securite": "Les incidents et accidents du travail ne sont pas rapprochés des effectifs.",
    "conformite": "Contrats et échéances (hr.contract) pas encore lus en détail.",
}


def _lineaire(valeur: float, plancher: float, objectif: float) -> float:
    return round(max(0.0, min(100.0, (valeur - plancher) * 100 / (objectif - plancher))), 1)


def score_presence(user, filtres: Filtres) -> dict[str, Any]:
    """Score de la dimension Présence & ponctualité, avec le détail de son calcul."""
    base = {"formule": FORMULE_PRESENCE, "source": "Kaydan Shield"}
    try:
        dimension, codes = portee(user, REGISTRE["hr.taux_presence_jour"], filtres)
    except FiltreInvalide as refus:
        # Une requête interdite (filiale hors périmètre) n'est pas un « non
        # mesuré » : elle remonte en 403. Seul un refus « rien à lire » devient N/D.
        if refus.code_http != 200:
            raise
        return {**base, "score": None, "motif": refus.motif}

    presence = H.agreger("hr.taux_presence_jour", filtres.periode, dimension=dimension, codes=codes)
    ponctualite = H.agreger("hr.taux_ponctualite_jour", filtres.periode, dimension=dimension, codes=codes)
    couverture = presence["couverture"]
    entrees = {"taux_presence": presence["value"], "taux_ponctualite": ponctualite["value"],
               "jours_mesures": couverture["jours_mesures"], "jours": couverture["jours"]}

    if presence["value"] is None or ponctualite["value"] is None:
        return {**base, "score": None, "entrees": entrees,
                "motif": "Taux de présence ou de ponctualité non mesuré sur la période."}
    if couverture["jours"] and couverture["jours_mesures"] / couverture["jours"] < COUVERTURE_DIMENSION_MIN:
        return {**base, "score": None, "entrees": entrees,
                "motif": (f"Couverture insuffisante : {couverture['jours_mesures']} jour(s) mesuré(s) sur "
                          f"{couverture['jours']} (minimum {int(COUVERTURE_DIMENSION_MIN * 100)} %).")}

    sous_presence = _lineaire(presence["value"], PRESENCE_PLANCHER, PRESENCE_OBJECTIF)
    sous_ponctualite = _lineaire(ponctualite["value"], PONCTUALITE_PLANCHER, PONCTUALITE_OBJECTIF)
    return {**base, "score": round((sous_presence + sous_ponctualite) / 2, 1), "entrees": entrees,
            "sous_scores": {"presence": sous_presence, "ponctualite": sous_ponctualite}}


def calculer(user, filtres: Filtres) -> dict[str, Any]:
    """Les neuf dimensions, le global (sous condition de couverture), la tendance."""
    presence = score_presence(user, filtres)
    precedente = score_presence(user, _decaler(filtres, filtres.periode.precedente()))

    dimensions = []
    for d in HC_DIMENSIONS:
        if d.key == "presence_ponctualite":
            dimensions.append({"key": d.key, "label": d.label, "weight": d.weight,
                               "score": presence["score"], "formule": presence["formule"],
                               "source": presence["source"], "entrees": presence.get("entrees"),
                               "sous_scores": presence.get("sous_scores"),
                               "motif": presence.get("motif"),
                               "precedent": precedente["score"]})
        else:
            dimensions.append({"key": d.key, "label": d.label, "weight": d.weight, "score": None,
                               "motif": MOTIFS_SANS_SOURCE.get(d.key, "Aucune source.")})

    scorees = [x for x in dimensions if x["score"] is not None]
    poids_couvert = sum(x["weight"] for x in scorees)
    couverture = {"poids_couvert": poids_couvert, "poids_total": total_weight(),
                  "dimensions_scorees": len(scorees), "dimensions": len(dimensions),
                  "seuil": COUVERTURE_GLOBALE_MIN}
    if scorees and poids_couvert >= COUVERTURE_GLOBALE_MIN:
        global_ = round(sum(x["score"] * x["weight"] for x in scorees) / poids_couvert, 1)
        motif_global = None
    else:
        global_ = None
        motif_global = (f"Couverture insuffisante : les dimensions mesurées pèsent {poids_couvert} % du score "
                        f"(seuil de publication {COUVERTURE_GLOBALE_MIN} %). Un global calculé sur elles seules "
                        f"ne représenterait pas la gouvernance RH.")

    return {"global": global_, "motif_global": motif_global, "dimensions": dimensions,
            "couverture": couverture, "tendance": _tendance(user)}


def _decaler(filtres: Filtres, periode: H.Periode) -> Filtres:
    return Filtres(periode=periode, libelle=filtres.libelle, nature=filtres.nature,
                   subsidiary=filtres.subsidiary, site=filtres.site, type=filtres.type,
                   departement=filtres.departement)


def _tendance(user, mois: int = 12) -> list[dict[str, Any]]:
    """Score de la dimension Présence, mois par mois (journées closes uniquement)."""
    from django.utils import timezone

    hier = timezone.localdate() - timedelta(days=1)
    points = []
    debut = date(hier.year, hier.month, 1)
    for _ in range(mois):
        fin = min(_fin_de_mois(debut), hier)
        f = Filtres(periode=H.Periode(debut, fin), libelle=debut.strftime("%m/%Y"), nature="fenetre",
                    subsidiary=None, site=None, type=None, departement=None)
        points.append({"month": debut.isoformat(), "score": score_presence(user, f)["score"]})
        debut = date(debut.year - (debut.month == 1), (debut.month - 2) % 12 + 1, 1)
    return list(reversed(points))


def _fin_de_mois(d: date) -> date:
    suivant = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return suivant - timedelta(days=1)
