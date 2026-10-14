"""Historique K-Insight : collecter les instantanés, puis les lire par période.

DEUX FAMILLES DE MESURES, DEUX FAÇONS DE COLLECTER.

  Présence (présents, absents, retards, et les taux qui en dérivent) — RATTRAPABLE.
  Shield conserve ses pointages journaliers (`/attendance/days/`). On collecte une
  journée CLOSE (la veille) en une passe, et elle donne d'un coup le Groupe, chaque
  site et chaque type de personnel. Un jour passé peut être recollecté à tout
  moment : c'est ce qui permet de reconstituer un trimestre.

  Stocks (effectifs déclarés, sites, référentiel Odoo) — NON RATTRAPABLES. Aucune
  source ne dit combien d'employés Shield comptait le 3 août. La série de ces
  métriques commence au premier instantané ; avant, elle est inconnue, pas nulle.

AUJOURD'HUI N'EST PAS HISTORISÉ. La présence du jour en cours est live et le reste :
la journée n'est pas close, un instantané de 10 h serait faux à 18 h. La lecture
par période s'arrête donc à la veille et le dit.

IDEMPOTENCE ET CHEVAUCHEMENT. L'écriture est un `update_or_create` sur le grain
unique (jour, source, métrique, dimension, code) : rejouer une collecte met ses
lignes à jour. Un verrou partagé (cache Redis) empêche deux collectes de la même
journée de s'exécuter en même temps — deux workers Celery, ou une tâche planifiée
et une commande manuelle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable

from django.db import transaction
from django.utils import timezone

from apps.integrations.odoo_session import _cache_add, _cache_delete

from .hr_registry import ODOO, REGISTRE, SHIELD, identifiant
from .models import Dimension, KpiSnapshot, StatutMesure

DUREE_VERROU = 60 * 60
PRESENCE = ("hr.presents_jour", "hr.absents_jour", "hr.retards_jour")
DRAPEAU_DE = {"hr.presents_jour": "present", "hr.absents_jour": "absent", "hr.retards_jour": "late"}
TYPE_DE = {"employee": "hr.presents_employes_jour", "worker": "hr.presents_ouvriers_jour"}


class CollecteEnCours(Exception):
    """Une autre collecte de la même journée tourne déjà."""


@dataclass
class Bilan:
    ecrites: int = 0
    inconnues: int = 0
    statut: str = "success"
    message: str = ""


def _ecrire(bilan: Bilan, *, jour: date, source: str, metric_id: str, valeur: float | None,
            dimension: str = Dimension.GROUPE, code: str = "", libelle: str = "",
            tache=None, statut: str | None = None) -> None:
    """Une ligne au grain unique. `None` est écrit `unknown`, jamais 0."""
    if statut is None:
        statut = StatutMesure.MESURE if valeur is not None else StatutMesure.INCONNU
    if statut != StatutMesure.MESURE:
        valeur = None
        bilan.inconnues += 1
    KpiSnapshot.objects.update_or_create(
        jour=jour, source=source, metric_id=metric_id, dimension=dimension, code=str(code or ""),
        defaults={"valeur": valeur, "statut": statut, "libelle": libelle[:200],
                  "collecte_le": timezone.now(), "tache": tache},
    )
    bilan.ecrites += 1


def _verrouiller(cle: str) -> None:
    if not _cache_add(f"historique:verrou:{cle}", 1, DUREE_VERROU):
        raise CollecteEnCours(f"Collecte « {cle} » déjà en cours.")


def _deverrouiller(cle: str) -> None:
    _cache_delete(f"historique:verrou:{cle}")


# ── Shield : présence d'une journée close ─────────────────────────────────────


def collecter_presence_shield(jour: date, *, tache=None) -> Bilan:
    """Présence d'UNE journée, en une passe : Groupe, sites, types de personnel.

    Une journée dont la collecte est incomplète (plafond de pages atteint, erreur
    sur un des trois jeux) est écrite `unknown` dans son ENSEMBLE : un taux calculé
    sur deux jeux sur trois serait un taux faux.
    """
    from apps.integrations.shield import (
        EP, ShieldError, _guard, _tally, build_client, collect_period,
    )

    if jour >= timezone.localdate():
        raise ValueError("Seule une journée close s'historise ; aujourd'hui reste live.")
    cle = f"shield:presence:{jour.isoformat()}"
    _verrouiller(cle)
    bilan = Bilan()
    try:
        source, bloque = _guard("hr")
        if bloque:
            bilan.statut, bilan.message = "failed", bloque.get("detail") or "Shield non connecté."
            return bilan
        client = build_client(source)
        texte = jour.isoformat()
        periode = collect_period(client, texte, texte)
        defaillante = bool(periode["errors"]) or periode["truncated"]

        with transaction.atomic():
            if defaillante:
                for metric_id in PRESENCE:
                    _ecrire(bilan, jour=jour, source=SHIELD, metric_id=metric_id, valeur=None,
                            tache=tache, statut=StatutMesure.ERREUR if periode["errors"] else StatutMesure.INCONNU)
                bilan.statut = "partial"
                bilan.message = ("Journée incomplète (plafond de pages ou erreur) : écrite non mesurée."
                                 if periode["truncated"] else "Erreur de collecte Shield.")
                return bilan

            lignes = {f: [r for r in periode["rows"][f] if r.get("date") == texte]
                      for f in ("present", "absent", "late")}
            for metric_id, drapeau in DRAPEAU_DE.items():
                _ecrire(bilan, jour=jour, source=SHIELD, metric_id=metric_id,
                        valeur=float(len(lignes[drapeau])), tache=tache)

            # Par type de personnel, pour les TROIS comptages : c'est ce qui permet au
            # filtre employé/ouvrier d'agir aussi sur les taux, recomposés depuis eux.
            # Comptage local, sans appel supplémentaire.
            for metric_id, drapeau in DRAPEAU_DE.items():
                par_type = _tally(lignes[drapeau], lambda r: r.get("holder_kind"))
                for kind in TYPE_DE:
                    _ecrire(bilan, jour=jour, source=SHIELD, metric_id=metric_id,
                            valeur=float(par_type.get(kind, 0)), dimension=Dimension.TYPE, code=kind,
                            libelle="Employés" if kind == "employee" else "Ouvriers", tache=tache)
            presents_par_type = _tally(lignes["present"], lambda r: r.get("holder_kind"))
            for kind, metric_id in TYPE_DE.items():
                _ecrire(bilan, jour=jour, source=SHIELD, metric_id=metric_id,
                        valeur=float(presents_par_type.get(kind, 0)), tache=tache)

            # Par site : le libellé vient du référentiel de sites, lu une fois.
            try:
                sites = {s.get("id"): s for s in client.results(EP.SITES, {}, limit=500)}
            except ShieldError:
                sites = {}
            comptes = {d: _tally(lignes[d], lambda r: r.get("site")) for d in ("present", "absent", "late")}
            for site_id in set().union(*[set(c) for c in comptes.values()]):
                meta = sites.get(site_id) or {}
                libelle = str(meta.get("name") or meta.get("code") or f"Site {site_id}")
                for metric_id, drapeau in DRAPEAU_DE.items():
                    _ecrire(bilan, jour=jour, source=SHIELD, metric_id=metric_id,
                            valeur=float(comptes[drapeau].get(site_id, 0)),
                            dimension=Dimension.SITE, code=str(site_id), libelle=libelle, tache=tache)
        return bilan
    finally:
        _deverrouiller(cle)


def collecter_stocks_shield(jour: date | None = None, *, tache=None) -> Bilan:
    """Effectifs et sites déclarés : l'état du jour, pour qu'il y ait une série demain."""
    from apps.integrations.shield import EP, ShieldError, _guard, build_client

    jour = jour or timezone.localdate()
    cle = f"shield:stocks:{jour.isoformat()}"
    _verrouiller(cle)
    bilan = Bilan()
    try:
        source, bloque = _guard("hr")
        if bloque:
            bilan.statut, bilan.message = "failed", bloque.get("detail") or "Shield non connecté."
            return bilan
        client = build_client(source)
        valeurs: dict[str, float | None] = {}
        for metric_id, chemin in (("hr.employes", EP.EMPLOYEES), ("hr.ouvriers", EP.WORKERS),
                                  ("hr.sites", EP.SITES)):
            try:
                valeurs[metric_id] = float(client.count(chemin))
            except (ShieldError, TypeError, ValueError):
                valeurs[metric_id] = None
        employes, ouvriers = valeurs["hr.employes"], valeurs["hr.ouvriers"]
        valeurs["hr.effectif_total"] = (employes + ouvriers
                                        if employes is not None and ouvriers is not None else None)
        with transaction.atomic():
            for metric_id, valeur in valeurs.items():
                _ecrire(bilan, jour=jour, source=SHIELD, metric_id=metric_id, valeur=valeur, tache=tache)
        if bilan.inconnues:
            bilan.statut = "partial"
        return bilan
    finally:
        _deverrouiller(cle)


# ── Odoo : référentiel, Groupe et par société ─────────────────────────────────


def collecter_odoo(jour: date | None = None, *, tache=None) -> Bilan:
    """Stocks du référentiel Odoo : Groupe, et CHAQUE société séparément.

    Les lignes par société rendent le chiffre d'une filiale recomposable à partir
    de ses sociétés déclarées — sans avoir collecté « par filiale », ce qui
    figerait la correspondance du jour de la collecte.
    """
    from apps.integrations.odoo import fetch_hr_kpis, get_odoo_source
    from apps.integrations.odoo_client import OdooError
    from apps.integrations.odoo_session import societes_odoo

    jour = jour or timezone.localdate()
    cle = f"odoo:stocks:{jour.isoformat()}"
    _verrouiller(cle)
    bilan = Bilan()
    try:
        source = get_odoo_source()
        groupe = fetch_hr_kpis()
        if groupe.get("status") in ("disconnected", "error") and not any(
                k.get("value") is not None for k in groupe.get("kpis") or []):
            bilan.statut, bilan.message = "failed", groupe.get("detail") or "Odoo non connecté."
            return bilan
        try:
            societes = societes_odoo(source.connector) if source is not None else []
        except OdooError:
            societes = []

        with transaction.atomic():
            for kpi in groupe.get("kpis") or []:
                metric_id = kpi.get("metric_id") or identifiant(ODOO, kpi.get("key", ""))
                if metric_id:
                    _ecrire(bilan, jour=jour, source=ODOO, metric_id=metric_id,
                            valeur=_nombre(kpi.get("value")), tache=tache)
            for ligne in (groupe.get("by_department") or {}).get("rows") or []:
                _ecrire(bilan, jour=jour, source=ODOO, metric_id="hr.employes_actifs_odoo",
                        valeur=_nombre(ligne.get("headcount")), dimension=Dimension.DEPARTEMENT,
                        code=str(ligne.get("department") or ""), libelle=str(ligne.get("department") or ""),
                        tache=tache)
            for societe in societes:
                charge = fetch_hr_kpis([societe["id"]])
                for kpi in charge.get("kpis") or []:
                    metric_id = kpi.get("metric_id") or identifiant(ODOO, kpi.get("key", ""))
                    if metric_id:
                        _ecrire(bilan, jour=jour, source=ODOO, metric_id=metric_id,
                                valeur=_nombre(kpi.get("value")), dimension=Dimension.SOCIETE,
                                code=str(societe["id"]), libelle=societe.get("name") or "", tache=tache)
        if bilan.inconnues:
            bilan.statut = "partial"
        return bilan
    finally:
        _deverrouiller(cle)


def _nombre(valeur: Any) -> float | None:
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return float(valeur)


# ── Lecture par période ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class Periode:
    debut: date
    fin: date               # incluse
    # « fenetre » (7/30/90 j, personnalisée) ou « trimestre » / « annee ». La
    # nature décide de la période PRÉCÉDENTE : une fenêtre glisse de sa propre
    # longueur, un trimestre recule d'un trimestre CALENDAIRE. Les confondre
    # comparait T3 (92 j) au 31 mars – 30 juin au lieu de T2.
    nature: str = "fenetre"

    @property
    def jours(self) -> int:
        return (self.fin - self.debut).days + 1

    def precedente(self) -> "Periode":
        if self.nature == "trimestre":
            mois = self.debut.month - 3
            annee = self.debut.year + (mois - 1) // 12
            debut = date(annee, (mois - 1) % 12 + 1, 1)
            # Trimestre en cours, donc tronqué à la veille : on compare « à date »,
            # au même nombre de jours écoulés depuis le début du précédent.
            fin = min(debut + timedelta(days=self.jours - 1), self.debut - timedelta(days=1))
            return Periode(debut, fin, "trimestre")
        if self.nature == "annee":
            return self.annee_precedente()
        duree = timedelta(days=self.jours)
        return Periode(self.debut - duree, self.fin - duree, self.nature)

    def annee_precedente(self) -> "Periode":
        def recul(d: date) -> date:
            try:
                return d.replace(year=d.year - 1)
            except ValueError:  # 29 février
                return d.replace(year=d.year - 1, day=28)
        return Periode(recul(self.debut), recul(self.fin), self.nature)


def _lignes(metric_ids: Iterable[str], periode: Periode, *, dimension: str, codes: list[str] | None):
    qs = KpiSnapshot.objects.filter(metric_id__in=list(metric_ids), dimension=dimension,
                                    jour__gte=periode.debut, jour__lte=periode.fin)
    if codes is not None:
        qs = qs.filter(code__in=codes)
    return qs


def serie(metric_id: str, periode: Periode, *, dimension: str = Dimension.GROUPE,
          codes: list[str] | None = None) -> list[dict[str, Any]]:
    """Un point par jour de la période, mesuré ou non. Les jours absents de
    l'historique sont rendus `unknown` : un trou n'est pas un zéro.

    `codes` (sociétés Odoo d'une filiale) : les valeurs des codes sont SOMMÉES par
    jour — un jour où une seule société est mesurée reste `unknown`, sans quoi une
    filiale semblerait perdre la moitié de son effectif."""
    m = REGISTRE[metric_id]
    if m.agregat == "ratio":
        composantes = {c: _par_jour(c, periode, dimension, codes)
                       for c in set(m.numerateur) | set(m.denominateur)}
        points = []
        for jour in _jours(periode):
            num = _somme_jour([composantes[c] for c in m.numerateur], jour)
            den = _somme_jour([composantes[c] for c in m.denominateur], jour)
            valeur = _taux(num, den, m.complement)
            points.append({"date": jour.isoformat(), "value": valeur,
                           "status": "measured" if valeur is not None else "unknown"})
        return points
    par_jour = _par_jour(metric_id, periode, dimension, codes)
    return [{"date": j.isoformat(), "value": par_jour.get(j),
             "status": "measured" if par_jour.get(j) is not None else "unknown"}
            for j in _jours(periode)]


def _jours(periode: Periode):
    for i in range(periode.jours):
        yield periode.debut + timedelta(days=i)


def _par_jour(metric_id: str, periode: Periode, dimension: str, codes: list[str] | None) -> dict[date, float]:
    attendu = len(codes) if codes else None
    valeurs: dict[date, list[float | None]] = {}
    for ligne in _lignes([metric_id], periode, dimension=dimension, codes=codes):
        valeurs.setdefault(ligne.jour, []).append(ligne.valeur if ligne.statut == StatutMesure.MESURE else None)
    resultat: dict[date, float] = {}
    for jour, liste in valeurs.items():
        if any(v is None for v in liste):
            continue
        if attendu is not None and len(liste) < attendu:
            continue  # une société manquante ce jour-là : total inconnu, pas partiel
        resultat[jour] = float(sum(liste))
    return resultat


def _somme_jour(composantes: list[dict[date, float]], jour: date) -> float | None:
    valeurs = [c.get(jour) for c in composantes]
    if any(v is None for v in valeurs):
        return None
    return float(sum(valeurs))


def _taux(num: float | None, den: float | None, complement: bool) -> float | None:
    if num is None or den is None or den <= 0:
        return None  # pas de taux si le dénominateur est inconnu ou nul
    taux = num * 100 / den
    return round(100 - taux if complement else taux, 1)


def agreger(metric_id: str, periode: Periode, *, dimension: str = Dimension.GROUPE,
            codes: list[str] | None = None) -> dict[str, Any]:
    """La valeur de la PÉRIODE selon la règle déclarée au registre, et sa couverture."""
    m = REGISTRE[metric_id]
    points = serie(metric_id, periode, dimension=dimension, codes=codes)
    mesures = [p for p in points if p["status"] == "measured"]
    couverture = {"jours": len(points), "jours_mesures": len(mesures)}

    if m.agregat == "ratio":
        composantes = {c: _par_jour(c, periode, dimension, codes)
                       for c in set(m.numerateur) | set(m.denominateur)}
        num = den = 0.0
        jours_utiles = 0
        for jour in _jours(periode):
            n = _somme_jour([composantes[c] for c in m.numerateur], jour)
            d = _somme_jour([composantes[c] for c in m.denominateur], jour)
            if n is None or d is None:
                continue  # un jour non mesuré ne pèse ni au numérateur ni au dénominateur
            num, den, jours_utiles = num + n, den + d, jours_utiles + 1
        valeur = _taux(num, den, m.complement) if jours_utiles else None
    elif m.agregat == "moyenne":
        valeur = round(sum(p["value"] for p in mesures) / len(mesures), 1) if mesures else None
    else:  # dernier
        valeur = mesures[-1]["value"] if mesures else None

    return {"metric_id": metric_id, "value": valeur, "regle": m.agregat,
            "debut": periode.debut.isoformat(), "fin": periode.fin.isoformat(),
            "couverture": couverture,
            "status": "measured" if valeur is not None else "unknown"}


def comparer(actuelle: dict[str, Any], reference: dict[str, Any], *, est_taux: bool) -> dict[str, Any]:
    """Écart entre deux agrégats. Un écart ne se calcule que si les DEUX existent ;
    pour un taux, il se dit en points, pas en pourcentage d'un pourcentage."""
    a, b = actuelle.get("value"), reference.get("value")
    if a is None or b is None:
        return {"value": b, "ecart": None, "ecart_pct": None, "unite_ecart": None,
                "debut": reference.get("debut"), "fin": reference.get("fin"),
                "couverture": reference.get("couverture")}
    ecart = round(a - b, 1)
    return {"value": b, "ecart": ecart, "unite_ecart": "pts" if est_taux else "abs",
            "ecart_pct": None if est_taux or b == 0 else round((a - b) * 100 / abs(b), 1),
            "debut": reference.get("debut"), "fin": reference.get("fin"),
            "couverture": reference.get("couverture")}


def premiere_mesure(metric) -> date | None:
    """Premier jour mesuré de la métrique OU de ses composantes : c'est la date à
    partir de laquelle une période peut avoir une valeur, et l'écran la cite."""
    ids = [metric.id, *metric.numerateur, *metric.denominateur]
    return (KpiSnapshot.objects.filter(metric_id__in=ids, statut=StatutMesure.MESURE)
            .order_by("jour").values_list("jour", flat=True).first())
