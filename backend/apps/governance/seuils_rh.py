"""Seuils des signaux RH : valeurs par défaut écrites, surcharges arbitrées.

UNE SEULE SOURCE. Les seuils vivaient en constantes dans `shield_rules` : justes,
mais figés — la direction ne pouvait pas les arbitrer. Ils deviennent ici des
VALEURS PAR DÉFAUT, que la DRH Groupe peut surcharger (`SeuilRh`, par l'API). Les
surcharges remontent aussi dans `shield_rules.seuils_publics()` : les constats du
jour, la carte de chaleur et les signaux de période jugent donc avec les mêmes
bornes — un seuil modifié ici ne laisse pas un écran sur l'ancienne valeur.

CE QUI NE BOUGE PAS. Le barème du score de gouvernance (`score_rh`) lit les
constantes, pas la configuration : sa formule est fixée par la direction, et un
réglage d'alerte ne doit pas faire varier un score d'une semaine à l'autre.

Les valeurs par défaut sont des propositions de seuils, pas des données : elles
sont affichées comme telles (« par défaut ») tant que personne ne les a arbitrées.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.core.cache import cache
from django.db import DatabaseError

from apps.integrations import shield_rules as R

journal = logging.getLogger(__name__)

CLE_CACHE = "governance:seuils-rh"
DUREE_CACHE = 300


@dataclass(frozen=True)
class Defaut:
    """`sens` : « bas » — une valeur BASSE est mauvaise (présence) ; « haut » — une
    valeur HAUTE est mauvaise (retards, baisse d'effectif)."""

    sens: str
    unite: str
    surveillance: float
    critique: float


DEFAUTS: dict[str, Defaut] = {
    "presence_faible": Defaut("bas", "%", R.PRESENCE_SURVEILLANCE, R.PRESENCE_CRITIQUE),
    "absenteisme": Defaut("haut", "%", 15.0, R.ABSENTEISME_ELEVE),
    "retard_eleve": Defaut("haut", "%", R.RETARDS_ELEVES, 25.0),
    "site_sous_effectif": Defaut("bas", "%", R.PRESENCE_CRITIQUE, R.PRESENCE_SITE_CRITIQUE),
    "effectif_critique": Defaut("haut", "%", 5.0, 10.0),
}

# Seuils de signal qui ont un équivalent dans les constats du jour (Shield).
VERS_SHIELD: dict[tuple[str, str], str] = {
    ("presence_faible", "surveillance"): "presence_surveillance",
    ("presence_faible", "critique"): "presence_critique",
    ("absenteisme", "critique"): "absenteisme_eleve",
    ("retard_eleve", "surveillance"): "retards_eleves",
    ("site_sous_effectif", "critique"): "presence_site_critique",
}


class SeuilInvalide(ValueError):
    pass


def _surcharges() -> dict[str, tuple[float, float]]:
    """{signal: (surveillance, critique)} arbitrés. Cache partagé, base en repli."""
    try:
        en_cache = cache.get(CLE_CACHE)
    except Exception:  # cache indisponible : la base répond
        en_cache = None
    if en_cache is not None:
        return en_cache
    from .models import SeuilRh

    try:
        lignes = {s.signal: (s.surveillance, s.critique) for s in SeuilRh.objects.all()}
    except DatabaseError:
        # Table absente (migration pas encore jouée) : les défauts s'appliquent.
        journal.warning("Seuils RH illisibles : valeurs par défaut appliquées.")
        return {}
    try:
        cache.set(CLE_CACHE, lignes, DUREE_CACHE)
    except Exception:
        pass
    return lignes


def oublier() -> None:
    try:
        cache.delete(CLE_CACHE)
    except Exception:
        pass


def effectifs() -> dict[str, dict]:
    """Les seuils appliqués, signal par signal, avec leur provenance."""
    surcharges = _surcharges()
    resultat = {}
    for cle, d in DEFAUTS.items():
        surveillance, critique = surcharges.get(cle, (d.surveillance, d.critique))
        resultat[cle] = {"sens": d.sens, "unite": d.unite, "surveillance": surveillance,
                         "critique": critique, "par_defaut": cle not in surcharges,
                         "defaut": {"surveillance": d.surveillance, "critique": d.critique}}
    return resultat


def surcharges_shield() -> dict[str, float]:
    """Les surcharges, traduites dans le vocabulaire de `shield_rules`."""
    surcharges = _surcharges()
    sortie = {}
    for (signal, palier), cle_shield in VERS_SHIELD.items():
        if signal in surcharges:
            surveillance, critique = surcharges[signal]
            sortie[cle_shield] = surveillance if palier == "surveillance" else critique
    return sortie


def valider(signal: str, surveillance, critique) -> tuple[float, float]:
    """Deux nombres dans 0..100, dans l'ordre que le sens impose."""
    d = DEFAUTS.get(signal)
    if d is None:
        raise SeuilInvalide(f"Signal inconnu ou sans seuil : « {signal} ».")
    try:
        s, c = float(surveillance), float(critique)
    except (TypeError, ValueError):
        raise SeuilInvalide("Les deux seuils doivent être des nombres.") from None
    if not (0 <= s <= 100 and 0 <= c <= 100):
        raise SeuilInvalide("Les seuils s'expriment en pourcentage, entre 0 et 100.")
    if d.sens == "bas" and not c < s:
        raise SeuilInvalide("Le seuil critique doit être INFÉRIEUR au seuil de surveillance : "
                            "une valeur basse est mauvaise pour ce signal.")
    if d.sens == "haut" and not c > s:
        raise SeuilInvalide("Le seuil critique doit être SUPÉRIEUR au seuil de surveillance : "
                            "une valeur haute est mauvaise pour ce signal.")
    return s, c


def etat(valeur: float | None, signal: str, seuils: dict[str, dict] | None = None) -> str:
    """normal / surveillance / critique — ou non_mesure, jamais déduit d'une absence."""
    if valeur is None:
        return "non_mesure"
    s = (seuils or effectifs())[signal]
    if s["sens"] == "bas":
        return "critique" if valeur < s["critique"] else "surveillance" if valeur < s["surveillance"] else "normal"
    return "critique" if valeur > s["critique"] else "surveillance" if valeur > s["surveillance"] else "normal"
