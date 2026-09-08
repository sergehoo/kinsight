"""Seuils et règles de décision RH — un seul endroit, explicite et testable.

Deux raisons de les centraliser ici plutôt que de les disperser :
un seuil enfoui dans un composant devient invisible pour qui doit l'arbitrer, et
un même seuil dupliqué finit toujours par diverger entre deux écrans.

Aucune inférence : chaque règle est une comparaison à un seuil nommé, appliquée à
une mesure réellement obtenue. Un constat qui ne peut pas être justifié par une
formule n'est pas produit.
"""

from __future__ import annotations

from typing import Any

# ── Seuils ───────────────────────────────────────────────────────────────────
# Exprimés en pourcentage de présence, sauf mention contraire.
PRESENCE_CRITIQUE = 70.0        # en dessous : la journée est compromise
PRESENCE_SITE_CRITIQUE = 50.0   # un site sous ce seuil ne peut pas opérer
ABSENTEISME_ELEVE = 25.0        # part d'absents jugée anormale
RETARDS_ELEVES = 15.0           # part de retardataires parmi les présents
BAISSE_INHABITUELLE = 15.0      # chute, en points, vs la moyenne de la période
MIN_JOURS_POUR_COMPARER = 5     # en deçà, une moyenne n'a pas de sens

# Nombre de jours proposés pour la série de présence. 90 n'y figure pas :
# la série se construit par des comptages JOURNALIERS (le seul moyen documenté),
# soit 3 requêtes par jour. 90 jours demanderaient 270 allers-retours à chaque
# rafraîchissement — un coût que l'API Shield n'a pas à supporter.
FENETRES_JOURS = (7, 30)
MAX_JOURS = 30


def _pct(part: float | int | None, total: float | int | None) -> float | None:
    """Pourcentage, ou None si le rapport n'a pas de sens. Jamais 0 par défaut."""
    if not isinstance(part, (int, float)) or not isinstance(total, (int, float)):
        return None
    if total <= 0:
        return None
    return round(part * 100 / total, 1)


def taux_presence(present: Any, absent: Any) -> float | None:
    """Présents ÷ (présents + absents) × 100.

    Renvoie None quand personne n'est ni présent ni absent : le taux est alors
    indéterminable, et l'afficher à 0 % laisserait croire à une désertion.
    """
    if not isinstance(present, int) or not isinstance(absent, int):
        return None
    return _pct(present, present + absent)


def part_absents(present: Any, absent: Any) -> float | None:
    if not isinstance(present, int) or not isinstance(absent, int):
        return None
    return _pct(absent, present + absent)


def part_retards(late: Any, present: Any) -> float | None:
    """Retardataires rapportés aux présents : un retard suppose une présence."""
    if not isinstance(late, int) or not isinstance(present, int):
        return None
    return _pct(late, present)


def taux_ponctualite(late: Any, present: Any) -> float | None:
    """Complément à 100 de la part de retardataires, RAPPORTÉE AUX PRÉSENTS.

    La base est explicite parce qu'elle change le sens du chiffre : un retard
    suppose une présence, donc le taux porte sur les gens venus, pas sur
    l'effectif attendu. Un service où la moitié des effectifs est absente et où
    tous les venus sont à l'heure affiche 100 % — c'est correct sous cette
    définition, et trompeur sous l'autre. La formule voyage avec la valeur
    jusqu'à l'écran pour que la base ne soit jamais devinée.
    """
    part = part_retards(late, present)
    return None if part is None else round(100 - part, 1)


FORMULES = {
    "taux_presence": "présents ÷ (présents + absents) × 100",
    "part_absents": "absents ÷ (présents + absents) × 100",
    "part_retards": "retards ÷ présents × 100",
    "taux_ponctualite": "100 − (retards ÷ présents × 100), sur les présents du jour",
    "baisse": "taux du jour − moyenne des jours précédents de la fenêtre",
}


def _insight(rid, severity, title, finding, impact, formula, source, period, action=None,
             level="computed", portee="groupe"):
    """Un constat, et la portée de ce qu'il révèle.

    `portee` n'est pas décoratif : c'est ce sur quoi la porte RBAC s'appuie pour
    savoir si un constat peut être servi à un périmètre restreint. Un insight qui
    nomme un site et rechiffre sa présence porte la même donnée que la répartition
    par site — il doit tomber avec elle. La règle qui produit le constat est seule à
    savoir ce qu'elle expose : c'est donc elle qui le déclare, ici, plutôt qu'un
    filtre qui devinerait plus tard à partir de l'identifiant.
    """
    return {
        "id": rid, "severity": severity, "title": title, "finding": finding,
        "impact": impact, "level": level, "formula": formula,
        "source": source, "period": period, "confidence": 1.0, "portee": portee,
        "action": action or {"label": "Voir la présence", "to": "/dashboard/capital-humain/presence"},
    }


def evaluer_presence_globale(present, absent, late, source: str, period: str) -> list[dict]:
    """Règles portant sur la journée en cours."""
    out: list[dict] = []
    taux = taux_presence(present, absent)
    if taux is not None and taux < PRESENCE_CRITIQUE:
        out.append(_insight(
            "hr.presence_basse", "critical",
            "Présence globale sous le seuil d'alerte",
            f"Taux de présence de {taux} % ({present} présents, {absent} absents), "
            f"sous le seuil de {PRESENCE_CRITIQUE} %.",
            "Capacité de production réduite sur l'ensemble des sites.",
            FORMULES["taux_presence"], source, period))

    abs_pct = part_absents(present, absent)
    if abs_pct is not None and abs_pct > ABSENTEISME_ELEVE:
        out.append(_insight(
            "hr.absenteisme", "warning",
            "Absentéisme au-dessus du seuil",
            f"{absent} absents sur {present + absent} personnes attendues, soit {abs_pct} % "
            f"(seuil : {ABSENTEISME_ELEVE} %).",
            "Charge reportée sur les équipes présentes.",
            FORMULES["part_absents"], source, period))

    retard_pct = part_retards(late, present)
    if retard_pct is not None and retard_pct > RETARDS_ELEVES:
        out.append(_insight(
            "hr.retards", "warning",
            "Retards au-dessus du seuil",
            f"{late} retards pour {present} présents, soit {retard_pct} % (seuil : {RETARDS_ELEVES} %).",
            "Démarrage de chantier décalé.",
            FORMULES["part_retards"], source, period))
    return out


def evaluer_sites(sites: list[dict], source: str, period: str, limite: int = 3) -> list[dict]:
    """Sites dont le taux de présence passe sous le seuil critique."""
    faibles = [
        s for s in sites
        if isinstance(s.get("attendance_rate"), (int, float))
        and s["attendance_rate"] < PRESENCE_SITE_CRITIQUE
    ]
    out = []
    for s in sorted(faibles, key=lambda s: s["attendance_rate"])[:limite]:
        nom = s["site"]["name"]
        out.append(_insight(
            f"hr.sous_effectif.{s['site'].get('code') or s['site'].get('id')}", "warning",
            f"Sous-effectif sur {nom}",
            f"{s['present']} présents pour {s['absent']} absents, soit {s['attendance_rate']} % "
            f"(seuil : {PRESENCE_SITE_CRITIQUE} %).",
            "Site potentiellement en incapacité d'assurer ses opérations du jour.",
            FORMULES["taux_presence"], source, period,
            action={"label": f"Ouvrir {nom}", "to": "/dashboard/capital-humain/presence"},
            # Ce constat nomme le site et redonne ses effectifs : il ne sort pas du
            # périmètre Groupe, exactement comme la répartition dont il est tiré.
            portee="site"))
    return out


def evaluer_tendance(points: list[dict], source: str) -> list[dict]:
    """Chute inhabituelle du taux, comparée à la moyenne de la fenêtre.

    On exige `MIN_JOURS_POUR_COMPARER` jours mesurés : comparer à une moyenne de
    deux points produirait des alertes au moindre soubresaut.
    """
    mesures = [p for p in points if isinstance(p.get("taux_presence"), (int, float))]
    if len(mesures) < MIN_JOURS_POUR_COMPARER + 1:
        return []
    dernier, precedents = mesures[-1], mesures[:-1]
    moyenne = round(sum(p["taux_presence"] for p in precedents) / len(precedents), 1)
    ecart = round(moyenne - dernier["taux_presence"], 1)
    if ecart < BAISSE_INHABITUELLE:
        return []
    return [_insight(
        "hr.baisse_presence", "critical",
        "Baisse inhabituelle de la présence",
        f"Taux de {dernier['taux_presence']} % le {dernier['date']}, contre {moyenne} % en moyenne "
        f"sur les {len(precedents)} jours mesurés précédents, soit {ecart} points de moins "
        f"(seuil : {BAISSE_INHABITUELLE} points).",
        "Rupture de rythme à expliquer avant qu'elle ne s'installe.",
        FORMULES["baisse"], source, f"{mesures[0]['date']} → {dernier['date']}")]
