"""Lire une métrique RH pour UNE période, UN jeu de filtres, UN utilisateur.

Modules, historique, alertes et exports passent par ici : la portée, la règle
d'agrégation et la comparaison sont donc les mêmes partout.

LE PRINCIPE QUI GOUVERNE CE MODULE : un filtre qui ne peut pas s'appliquer à une
métrique ne s'ignore pas. Afficher le total Groupe sous l'étiquette « Site
Chantier A » ferait croire à une valeur filtrée ; on rend N/D, et on dit pourquoi.
"""

from __future__ import annotations

from typing import Any

from rest_framework import status

from . import historique as H
from .filtres import FiltreInvalide, Filtres
from apps.accounts.rbac import peut_voir_permission

from .hr_registry import MOTIF_PERMISSION, ODOO, PERMISSION_REQUISE, REGISTRE, SHIELD, Metrique
from .hr_sources import societes_des_filiales
from .models import Dimension

# Métriques historisées par site et par type de personnel (collecte de présence).
VENTILEES_PAR_PRESENCE = {
    "hr.presents_jour", "hr.absents_jour", "hr.retards_jour",
    "hr.taux_presence_jour", "hr.taux_absence_jour", "hr.taux_ponctualite_jour",
}
# Métriques historisées par département (référentiel Odoo).
VENTILEES_PAR_DEPARTEMENT = {"hr.employes_actifs_odoo"}


def portee(user, metric: Metrique, filtres: Filtres) -> tuple[str, list[str] | None]:
    """(dimension, codes) à lire pour cet utilisateur et ces filtres.

    `codes` None = tous les codes de la dimension (lecture Groupe). Lève
    `FiltreInvalide` quand la portée ne peut pas être honorée sans inventer un
    rattachement ni servir des chiffres hors périmètre."""
    scope = user.scope()
    filiales = set(scope.subsidiaries) if not scope.is_group else None
    if filtres.subsidiary:
        if filiales is not None and filtres.subsidiary not in filiales:
            # Le filtre ne peut JAMAIS élargir le périmètre.
            raise FiltreInvalide("Filiale demandée hors de votre périmètre.", status.HTTP_403_FORBIDDEN)
        filiales = {filtres.subsidiary}

    if metric.source == SHIELD:
        if filiales is not None:
            raise FiltreInvalide("Non rattaché : Shield ne rattache pas ses sites aux filiales, ses "
                                 "chiffres sont des chiffres Groupe.")
        if filtres.departement:
            raise FiltreInvalide("Non ventilé par département : le département est un référentiel "
                                 "Odoo, Shield ne le porte pas.")
        dimension, code = filtres.dimension_presence()
        if dimension != Dimension.GROUPE and metric.id not in VENTILEES_PAR_PRESENCE:
            nom = "site" if dimension == Dimension.SITE else "type de personnel"
            raise FiltreInvalide(f"Non ventilé par {nom} : cette métrique n'est pas historisée à "
                                 f"cette maille.")
        return dimension, ([code] if code else None)

    if metric.source == ODOO:
        if filtres.site or filtres.type:
            raise FiltreInvalide("Non ventilé par site ni par type : ce sont des dimensions Shield, "
                                 "le référentiel Odoo ne les porte pas.")
        if filtres.departement:
            if metric.id not in VENTILEES_PAR_DEPARTEMENT:
                raise FiltreInvalide("Non ventilé par département pour cette métrique.")
            if filiales is not None:
                raise FiltreInvalide("Ventilation par département réservée au périmètre Groupe : elle "
                                     "n'est pas historisée par société.")
            return Dimension.DEPARTEMENT, [filtres.departement]
        if filiales is None:
            return Dimension.GROUPE, None
        societes = societes_des_filiales(frozenset(filiales))
        if not societes:
            raise FiltreInvalide("Hors périmètre : aucune société Odoo n'est rattachée à cette filiale.")
        return Dimension.SOCIETE, [str(s) for s in societes]

    raise FiltreInvalide(metric.motif_absence or "Aucune source ne sert cette métrique.")


def valeur_periode(user, metric_id: str, filtres: Filtres, *, comparer: bool = True) -> dict[str, Any]:
    """La valeur de la période, sa couverture et son écart à la période précédente.

    Ne lève jamais : un refus de portée devient `{status: disconnected, reason}`
    — sauf un 403, qui doit remonter tel quel à l'appelant."""
    metric = REGISTRE[metric_id]
    requise = PERMISSION_REQUISE.get(metric_id)
    if requise and not peut_voir_permission(user, requise):
        return {"value": None, "status": "disconnected", "reason": MOTIF_PERMISSION[requise]}
    if metric.source not in (SHIELD, ODOO):
        return {"value": None, "status": "disconnected", "reason": metric.motif_absence}
    try:
        dimension, codes = portee(user, metric, filtres)
    except FiltreInvalide as refus:
        # Seul un refus « rien à lire » devient un N/D motivé ; une requête
        # fautive (400) ou interdite (403) remonte telle quelle.
        if refus.code_http != status.HTTP_200_OK:
            raise
        return {"value": None, "status": "disconnected", "reason": refus.motif}

    resultat = H.agreger(metric.id, filtres.periode, dimension=dimension, codes=codes)
    sortie: dict[str, Any] = {
        "value": resultat["value"], "status": resultat["status"],
        "couverture": resultat["couverture"], "libelle": filtres.libelle,
        "debut": resultat["debut"], "fin": resultat["fin"],
    }
    if resultat["value"] is None:
        premiere = H.premiere_mesure(metric)
        sortie["reason"] = (f"Aucune journée mesurée sur {filtres.libelle} : l'historique commence le "
                            f"{premiere.strftime('%d/%m/%Y')}." if premiere else
                            "Historique en cours de constitution : aucune journée encore collectée.")
    if comparer:
        ref = H.agreger(metric.id, filtres.periode.precedente(), dimension=dimension, codes=codes)
        sortie["precedente"] = H.comparer(resultat, ref, est_taux=metric.format == "pct")
    return sortie


# ── La valeur du JOUR, live, sous les mêmes filtres ──────────────────────────

_CHAMP_DE_SITE = {"hr.presents_jour": "present", "hr.absents_jour": "absent", "hr.retards_jour": "late"}


def valeur_du_jour(metric_id: str, contexte, filtres: Filtres) -> dict[str, Any]:
    """La mesure live du jour, restreinte au site ou au type demandé quand la
    source le permet AUJOURD'HUI — sinon N/D et le motif, jamais le total Groupe.

    Le live par site vient de la répartition du jour (sites actifs détaillés) ;
    par type, de la ventilation employés/ouvriers des PRÉSENTS — Shield n'en sert
    pas d'autre en temps réel."""
    from apps.integrations import shield_rules as R

    from .hr_registry import resoudre

    base = resoudre(metric_id, contexte)
    metric = REGISTRE.get(metric_id)
    if metric is None or not (filtres.site or filtres.type or filtres.departement):
        return base
    if base.get("status") == "disconnected" and base.get("value") is None and base.get("reason", "").startswith(("Hors", "Non")):
        return base  # refus de droits ou de périmètre : il prime sur le filtre

    def refus(motif: str) -> dict[str, Any]:
        return {**base, "value": None, "status": "disconnected", "reason": motif}

    if metric.source != SHIELD or filtres.departement:
        return refus("Non ventilé à cette maille en temps réel.")
    charge = contexte.shield()
    if filtres.site:
        if metric_id not in VENTILEES_PAR_PRESENCE:
            return refus("Non ventilé par site : cette métrique n'est pas servie par site.")
        lignes = (charge.get("by_site") or {}).get("sites") or []
        ligne = next((l for l in lignes if str((l.get("site") or {}).get("id")) == str(filtres.site)), None)
        if ligne is None:
            return refus("Site absent de la répartition du jour (seuls les sites actifs détaillés y figurent).")
        p, a, l = ligne.get("present"), ligne.get("absent"), ligne.get("late")
        valeurs = {"hr.presents_jour": p, "hr.absents_jour": a, "hr.retards_jour": l,
                   "hr.taux_presence_jour": R.taux_presence(p, a),
                   "hr.taux_absence_jour": R.part_absents(p, a),
                   "hr.taux_ponctualite_jour": R.taux_ponctualite(l, p)}
        valeur = valeurs.get(metric_id)
        return {**base, "value": valeur, "status": "connected" if valeur is not None else "disconnected",
                **({} if valeur is not None else {"reason": "Valeur du site non servie aujourd'hui."})}
    # Type de personnel
    if metric_id != "hr.presents_jour":
        return refus("Non ventilé par type en temps réel : Shield ne sert que les présents par type ; "
                     "la période, elle, l'est.")
    par_type = charge.get("by_kind") or {}
    cle = "employees" if filtres.type == "employee" else "workers"
    valeur = par_type.get(cle) if par_type.get("status") == "connected" else None
    return {**base, "value": valeur, "status": "connected" if valeur is not None else "disconnected",
            **({} if valeur is not None else {"reason": "Ventilation par type indisponible aujourd'hui."})}
