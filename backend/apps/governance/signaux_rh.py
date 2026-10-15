"""Signaux RH : neuf règles de seuil évaluées sur la période filtrée.

Chaque signal est une comparaison écrite (`regle`) d'une mesure RÉELLE de
l'historique à deux seuils (`seuils_rh`) : normal, surveillance ou critique. Un
signal dont la mesure n'existe pas est « non mesuré », avec son motif — jamais
« normal » : l'absence de mesure n'est pas l'absence de problème.

La période, les filtres et le périmètre sont ceux de toutes les lectures RH
(`lecture_rh.portee`) : un RH de filiale ne reçoit pas un signal calculé sur les
chiffres Groupe de Shield, il reçoit « non rattaché ».

Chaque signal porte ce qu'un décideur doit pouvoir vérifier : la valeur, la
comparaison à la période précédente, la période, la source, la couverture et une
confiance qui en découle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import historique as H
from . import seuils_rh as S
from .filtres import FiltreInvalide, Filtres
from .hr_registry import REGISTRE
from .lecture_rh import portee
from .models import Dimension

BASE = "/dashboard/capital-humain"
ORDRE = {"critique": 0, "surveillance": 1, "normal": 2, "non_mesure": 3}


@dataclass(frozen=True)
class Signal:
    cle: str
    libelle: str
    regle: str
    lien: str
    metric_id: str | None = None
    motif_absence: str | None = None


SIGNAUX: list[Signal] = [
    Signal("presence_faible", "Présence faible",
           "Taux de présence de la période : présents ÷ attendus (Σ/Σ sur les jours mesurés).",
           f"{BASE}/presence", "hr.taux_presence_jour"),
    Signal("absenteisme", "Absentéisme (absences pointées)",
           "Absents ÷ attendus sur la période. L'absentéisme mensuel (jours d'absence ÷ jours "
           "théoriques) n'est pas mesuré : ce signal porte sur les absences pointées par Shield.",
           f"{BASE}/presence", "hr.taux_absence_jour"),
    Signal("retard_eleve", "Retards élevés",
           "Retards ÷ présents sur la période (= 100 − taux de ponctualité).",
           f"{BASE}/presence", "hr.taux_ponctualite_jour"),
    Signal("site_sous_effectif", "Site en sous-effectif",
           "Taux de présence de chaque site sur la période ; le signal prend l'état du site le "
           "plus faible et liste les sites hors de la zone normale.",
           f"{BASE}/presence", "hr.taux_presence_jour"),
    Signal("effectif_critique", "Effectif critique — baisse de l'effectif déclaré",
           "Baisse de l'effectif déclaré (dernière valeur de la période) par rapport à la "
           "période précédente, en %.",
           f"{BASE}/overview", "hr.effectif_total"),
    Signal("turnover_eleve", "Turnover élevé", "Départs de la période ÷ effectif moyen.",
           f"{BASE}/overview", motif_absence=REGISTRE["hr.turnover"].motif_absence),
    Signal("contrat_echeance", "Contrats à échéance", "Contrats arrivant à échéance sur l'horizon arbitré par la DRH.",
           f"{BASE}/conformite",
           motif_absence="Les contrats (hr.contract) et leurs dates de fin ne sont pas lus dans Odoo."),
    Signal("recrutement_sous_cible", "Recrutement sous la cible", "Embauches de la période ÷ cible de recrutement.",
           f"{BASE}/recrutement",
           motif_absence="Aucune cible de recrutement datée n'est déclarée et les embauches ne sont pas "
                         "lues : seuls les postes à pourvoir sont comptés."),
    Signal("heures_sup_elevees", "Heures supplémentaires élevées",
           "Heures supplémentaires ÷ heures contractuelles.", f"{BASE}/presence",
           motif_absence=REGISTRE["hr.heures_supplementaires"].motif_absence),
]

SOURCE_DE = {"shield": "Kaydan Shield", "odoo": "Odoo RH"}


def confiance(couverture: dict | None) -> str | None:
    """Élevée / moyenne / faible selon la part de jours mesurés sur la période."""
    if not couverture or not couverture.get("jours"):
        return None
    part = couverture["jours_mesures"] / couverture["jours"]
    return "élevée" if part >= 0.8 else "moyenne" if part >= 0.5 else "faible"


def _lire(user, metric_id: str, filtres: Filtres):
    """(dimension, codes) ou le motif d'une lecture impossible. Un refus 403 remonte."""
    try:
        return portee(user, REGISTRE[metric_id], filtres), None
    except FiltreInvalide as refus:
        if refus.code_http != 200:
            raise
        return None, refus.motif


def _taux(sig: Signal, user, filtres: Filtres, seuils: dict, complement: bool = False) -> dict[str, Any]:
    lecture, motif = _lire(user, sig.metric_id, filtres)
    if lecture is None:
        return {"valeur": None, "motif": motif}
    dimension, codes = lecture
    actuel = H.agreger(sig.metric_id, filtres.periode, dimension=dimension, codes=codes)
    reference = H.agreger(sig.metric_id, filtres.periode.precedente(), dimension=dimension, codes=codes)
    if complement:  # retard = 100 − ponctualité, sur la valeur comme sur la référence
        actuel = {**actuel, "value": None if actuel["value"] is None else round(100 - actuel["value"], 1)}
        reference = {**reference, "value": None if reference["value"] is None else round(100 - reference["value"], 1)}
    comparaison = H.comparer(actuel, reference, est_taux=True)
    valeur = actuel["value"]
    return {"valeur": valeur, "couverture": actuel["couverture"], "comparaison": comparaison,
            "motif": None if valeur is not None else "Aucune journée mesurée sur la période."}


def _sites(sig: Signal, user, filtres: Filtres, seuils: dict) -> dict[str, Any]:
    lecture, motif = _lire(user, sig.metric_id, filtres)
    if lecture is None:
        return {"valeur": None, "motif": motif}
    dimension, codes = lecture
    if dimension == Dimension.TYPE:
        return {"valeur": None, "motif": "Non ventilé par site sous un filtre type de personnel : le "
                                         "croisement site × type n'est pas historisé."}
    lignes = H.ventiler(sig.metric_id, filtres.periode, Dimension.SITE,
                        codes if dimension == Dimension.SITE else None)
    mesurees = [l for l in lignes if l["value"] is not None]
    if not mesurees:
        return {"valeur": None, "motif": "Aucun site mesuré sur la période."}
    hors_norme = sorted(
        ({"code": l["code"], "libelle": l["libelle"], "valeur": l["value"],
          "etat": S.etat(l["value"], sig.cle, seuils)} for l in mesurees),
        key=lambda l: l["valeur"])
    pire = hors_norme[0]
    return {"valeur": pire["valeur"], "sites_mesures": len(mesurees),
            "details": [l for l in hors_norme if l["etat"] != "normal"],
            "pire": {"libelle": pire["libelle"], "valeur": pire["valeur"]},
            "couverture": None}


def _effectif(sig: Signal, user, filtres: Filtres, seuils: dict) -> dict[str, Any]:
    lecture, motif = _lire(user, sig.metric_id, filtres)
    if lecture is None:
        return {"valeur": None, "motif": motif}
    dimension, codes = lecture
    actuel = H.agreger(sig.metric_id, filtres.periode, dimension=dimension, codes=codes)
    reference = H.agreger(sig.metric_id, filtres.periode.precedente(), dimension=dimension, codes=codes)
    if actuel["value"] is None:
        return {"valeur": None, "motif": "Effectif déclaré non mesuré sur la période."}
    if not reference["value"]:
        return {"valeur": None, "motif": "Effectif déclaré non mesuré sur la période précédente : "
                                         "pas de variation calculable."}
    comparaison = H.comparer(actuel, reference, est_taux=False)
    baisse = round((reference["value"] - actuel["value"]) * 100 / reference["value"], 1)
    return {"valeur": baisse, "effectif": actuel["value"], "couverture": actuel["couverture"],
            "comparaison": comparaison}


EVALUATEURS = {
    "presence_faible": lambda sig, u, f, s: _taux(sig, u, f, s),
    "absenteisme": lambda sig, u, f, s: _taux(sig, u, f, s),
    "retard_eleve": lambda sig, u, f, s: _taux(sig, u, f, s, complement=True),
    "site_sous_effectif": _sites,
    "effectif_critique": _effectif,
}


def evaluer(user, filtres: Filtres) -> dict[str, Any]:
    seuils = S.effectifs()
    resultats = []
    for sig in SIGNAUX:
        base = {"cle": sig.cle, "libelle": sig.libelle, "regle": sig.regle, "lien": sig.lien,
                "seuils": seuils.get(sig.cle),
                "source": SOURCE_DE.get(REGISTRE[sig.metric_id].source) if sig.metric_id else None,
                "metric_id": sig.metric_id}
        if sig.metric_id is None:
            resultats.append({**base, "etat": "non_mesure", "valeur": None, "motif": sig.motif_absence})
            continue
        mesure = EVALUATEURS[sig.cle](sig, user, filtres, seuils)
        etat = S.etat(mesure["valeur"], sig.cle, seuils)
        resultats.append({**base, **mesure, "etat": etat, "confiance": confiance(mesure.get("couverture"))})

    resultats.sort(key=lambda r: ORDRE[r["etat"]])
    compteurs = {e: sum(1 for r in resultats if r["etat"] == e) for e in ORDRE}
    return {"signaux": resultats, "compteurs": compteurs}
