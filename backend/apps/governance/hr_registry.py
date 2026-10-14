"""Registre canonique des métriques RH : une métrique, un identifiant, une source.

POURQUOI CE REGISTRE. L'inventaire du dépôt a trouvé six définitions de
« l'effectif total », quatre de l'absentéisme, quatre du turnover, et des cartes
qui affichaient « N/D — mart à connecter » pour un chiffre que Shield servait déjà
deux écrans plus loin. La cause n'était pas l'absence de données mais l'absence
d'un endroit unique qui dise ce que chaque métrique EST et d'où elle vient.

CE QUE PORTE CHAQUE MÉTRIQUE.
  - `id` stable (`hr.effectif_total`) : même métrique ⇒ même identifiant, partout.
  - `source` réelle : Shield, Odoo, ou AUCUNE — et dans ce dernier cas le motif
    exact, affiché tel quel. N/D n'est légitime que si aucune source ne la sert.
  - `instant` : vrai pour une mesure « aujourd'hui ». Ces valeurs sont live et
    doivent être marquées comme telles : elles ne répondent PAS au filtre de
    période tant que l'historique n'existe pas.
  - `definition` : ce que mesure le nombre. « Taux d'absence du jour » et
    « absentéisme mensuel » ne sont pas la même chose ; les confondre était
    l'erreur la plus fréquente de l'inventaire.

CE QUI N'EST PAS ICI. Aucune valeur par défaut, aucun repli sur 0. Une métrique
non servie reste `None` avec son état et son motif (ADR-0007).

ARCHITECTURE. Shield + Odoo, sans mart EDW obligatoire : aucune métrique de ce
registre ne lit `mart.*`. Les anciens marts ne sont pas supprimés ; ils cessent
seulement d'être la condition d'un écran RH.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

SHIELD = "shield"
ODOO = "odoo"
AUCUNE = "aucune"

LIBELLE_SOURCE = {SHIELD: "Kaydan Shield", ODOO: "Odoo RH", AUCUNE: "Aucune source"}


@dataclass(frozen=True)
class Metrique:
    id: str
    libelle: str
    source: str
    definition: str
    unite: str = "personnes"
    format: str = "int"            # int | pct
    instant: bool = False          # mesure « aujourd'hui », live
    cle_source: str = ""           # clé du KPI dans la charge de la source
    domaine: str = "capital-humain"
    motif_absence: str = ""        # obligatoire quand source == AUCUNE


_M: list[Metrique] = [
    # ── Kaydan Shield : effectifs déclarés et présence du jour ─────────────────
    Metrique("hr.effectif_total", "Effectif total", SHIELD,
             "Employés + ouvriers déclarés dans Shield, tous statuts confondus.",
             cle_source="effectif_total", instant=True),
    Metrique("hr.employes", "Employés", SHIELD,
             "Employés déclarés dans Shield (tous statuts).", cle_source="employes", instant=True),
    Metrique("hr.ouvriers", "Ouvriers", SHIELD,
             "Ouvriers déclarés dans Shield (tous statuts).", cle_source="ouvriers", instant=True),
    Metrique("hr.presents_jour", "Présents aujourd'hui", SHIELD,
             "Personnes pointées présentes aujourd'hui (synthèse du jour Shield).",
             cle_source="presents", instant=True),
    Metrique("hr.absents_jour", "Absents aujourd'hui", SHIELD,
             "Personnes attendues et non pointées aujourd'hui.", cle_source="absents", instant=True),
    Metrique("hr.retards_jour", "Retards aujourd'hui", SHIELD,
             "Pointages en retard aujourd'hui (nombre, sans durée).", cle_source="retards", instant=True),
    Metrique("hr.taux_presence_jour", "Taux de présence du jour", SHIELD,
             "Présents ÷ (présents + absents) × 100, aujourd'hui. Non calculé si le "
             "dénominateur est nul.", unite="%", format="pct", cle_source="taux_presence",
             instant=True),
    Metrique("hr.taux_absence_jour", "Taux d'absence du jour", SHIELD,
             "Absents ÷ (présents + absents) × 100, aujourd'hui. Ce n'est PAS "
             "l'absentéisme mensuel.", unite="%", format="pct", cle_source="taux_absence_jour",
             instant=True),
    Metrique("hr.taux_ponctualite_jour", "Taux de ponctualité du jour", SHIELD,
             "100 − retards ÷ présents × 100, aujourd'hui.", unite="%", format="pct",
             cle_source="taux_ponctualite", instant=True),
    Metrique("hr.sites", "Sites déclarés", SHIELD,
             "Sites déclarés dans Shield, tous statuts.", unite="sites", cle_source="sites",
             instant=True),
    Metrique("hr.presents_employes_jour", "Employés présents aujourd'hui", SHIELD,
             "Présents du jour dont le titulaire est un employé (holder_kind).",
             cle_source="by_kind.employees", instant=True),
    Metrique("hr.presents_ouvriers_jour", "Ouvriers présents aujourd'hui", SHIELD,
             "Présents du jour dont le titulaire est un ouvrier (holder_kind).",
             cle_source="by_kind.workers", instant=True),

    # ── Odoo : référentiel RH ──────────────────────────────────────────────────
    Metrique("hr.employes_actifs_odoo", "Employés actifs (Odoo)", ODOO,
             "Fiches employé actives dans Odoo (hr.employee, active = vrai). N'inclut "
             "pas les ouvriers gérés hors Odoo.", cle_source="employes_actifs", instant=True),
    Metrique("hr.employes_archives_odoo", "Employés archivés (Odoo)", ODOO,
             "Fiches employé archivées dans Odoo : un STOCK cumulé, pas des départs "
             "sur une période.", cle_source="employes_inactifs", instant=True),
    Metrique("hr.departements", "Départements", ODOO,
             "Départements déclarés dans Odoo (hr.department).", unite="départements",
             cle_source="departements", instant=True),
    Metrique("hr.postes_definis", "Postes définis", ODOO,
             "Postes déclarés dans Odoo (hr.job).", unite="postes", cle_source="metiers",
             instant=True),
    Metrique("hr.postes_a_pourvoir", "Postes à pourvoir", ODOO,
             "Somme des objectifs de recrutement déclarés sur les postes "
             "(hr.job.no_of_recruitment).", unite="postes", cle_source="postes_ouverts",
             instant=True),

    # ── Sans source dans l'architecture Shield + Odoo ──────────────────────────
    Metrique("hr.turnover", "Turnover", AUCUNE,
             "Départs de la période ÷ effectif moyen × 100.", unite="%", format="pct",
             motif_absence="Les départs datés ne sont pas lus dans Odoo : le flux de "
                           "sorties d'une période n'est pas connu. La part d'archivés "
                           "Odoo est un stock, pas un turnover."),
    Metrique("hr.absenteisme_mensuel", "Taux d'absentéisme", AUCUNE,
             "Jours d'absence ÷ jours travaillés théoriques de la période × 100.",
             unite="%", format="pct",
             motif_absence="Les jours travaillés théoriques ne sont servis par aucune "
                           "source. Le taux d'absence DU JOUR (Shield) existe, mais ne "
                           "mesure pas la même chose."),
    Metrique("hr.entrees", "Entrées", AUCUNE, "Embauches sur la période.",
             motif_absence="Les dates d'entrée ne sont pas encore lues dans Odoo."),
    Metrique("hr.sorties", "Départs", AUCUNE, "Départs sur la période.",
             motif_absence="Les dates de sortie ne sont pas encore lues dans Odoo."),
    Metrique("hr.masse_salariale", "Masse salariale", AUCUNE,
             "Somme des salaires bruts de la période.", unite="XOF", format="currency",
             motif_absence="La paie Odoo (hr.payslip) n'est pas installée sur l'instance : "
                           "aucune source ne sert la masse salariale."),
    Metrique("hr.heures_travaillees", "Heures travaillées", AUCUNE,
             "Somme des durées entre entrée et sortie pointées.", unite="h",
             motif_absence="Shield ne publie pas les heures d'entrée et de sortie dans la "
                           "synthèse lue : la durée n'est pas calculable."),
    Metrique("hr.heures_supplementaires", "Heures supplémentaires", AUCUNE,
             "Heures au-delà de l'horaire contractuel.", unite="h",
             motif_absence="Aucune règle métier d'horaire contractuel n'est définie, et les "
                           "durées ne sont pas servies."),
    Metrique("hr.departs_anticipes", "Départs anticipés", AUCUNE,
             "Sorties avant l'heure de fin prévue.",
             motif_absence="Les heures de sortie ne sont pas lues dans Shield."),
    Metrique("hr.pointages_rfid", "Pointages RFID", AUCUNE,
             "Événements de badge sur la période.",
             motif_absence="Les événements d'accès Shield ne sont pas encore agrégés en "
                           "pointages RH."),
]

REGISTRE: dict[str, Metrique] = {m.id: m for m in _M}
_PAR_CLE_SOURCE: dict[tuple[str, str], str] = {(m.source, m.cle_source): m.id for m in _M if m.cle_source}


def identifiant(source: str, cle: str) -> str | None:
    """L'identifiant canonique d'un KPI de source (`shield`, `presents`) → `hr.presents_jour`.

    Les connecteurs l'apposent sur leurs charges : le frontend fusionne métriques
    déclarées et métriques reçues PAR IDENTIFIANT, et un identifiant différent par
    écran était précisément ce qui produisait six « effectif total ».
    """
    return _PAR_CLE_SOURCE.get((source, cle))
assert all(m.motif_absence for m in _M if m.source == AUCUNE), "motif obligatoire sans source"


# ── Cartes des modules → métrique canonique ──────────────────────────────────
#
# La liaison se fait par LIBELLÉ de carte (c'est la clé que le frontend affiche)
# vers un IDENTIFIANT de métrique (c'est ce qui la définit). Deux cartes de deux
# modules qui portent le même identifiant affichent forcément le même nombre.
LIAISONS: dict[str, dict[str, str]] = {
    "hr-executive": {
        "Effectif total": "hr.effectif_total",
        "Employés actifs": "hr.employes_actifs_odoo",
        "Employés inactifs": "hr.employes_archives_odoo",
        "Nouveaux employés": "hr.entrees",
        "Départs": "hr.sorties",
    },
    "hr-organization": {
        "Nombre de départements": "hr.departements",
        "Postes vacants": "hr.postes_a_pourvoir",
    },
    "hr-attendance": {
        "Présents": "hr.presents_jour",
        "Absents": "hr.absents_jour",
        "Retards": "hr.retards_jour",
        "Taux de présence": "hr.taux_presence_jour",
        "Taux de ponctualité": "hr.taux_ponctualite_jour",
        # Le libellé dit « absentéisme » : on le lie à la métrique mensuelle, sans
        # source, plutôt qu'au taux du jour — qui afficherait un chiffre réel sous
        # une définition fausse.
        "Taux d'absentéisme": "hr.absenteisme_mensuel",
        "Heures travaillées": "hr.heures_travaillees",
        "Heures supplémentaires": "hr.heures_supplementaires",
        "Départs anticipés": "hr.departs_anticipes",
        "Pointages RFID": "hr.pointages_rfid",
    },
    "hr-payroll": {
        "Masse salariale": "hr.masse_salariale",
        "Heures supplémentaires": "hr.heures_supplementaires",
    },
    "hr-ai": {
        "Effectifs": "hr.effectif_total",
        "Présence": "hr.taux_presence_jour",
    },
    "chantier-resources": {
        "Ouvriers présents": "hr.presents_ouvriers_jour",
        "Présence temps réel": "hr.presents_jour",
        "Heures travaillées": "hr.heures_travaillees",
        "Pointage RFID": "hr.pointages_rfid",
    },
    "security": {
        "Présence": "hr.presents_jour",
    },
}


def liaisons(cle_module: str) -> dict[str, str] | None:
    return LIAISONS.get(cle_module)


# ── Résolution ───────────────────────────────────────────────────────────────


@dataclass
class Contexte:
    """Ce dont la résolution a besoin, pour UNE requête : qui, et quelles charges."""

    peut_voir: Callable[[str], bool]          # domaine → droit
    perimetre_groupe: bool
    filiales: frozenset[str] = frozenset()
    charge_shield: Callable[[], dict] | None = None
    charge_odoo: Callable[[list[int] | None], dict] | None = None
    societes_des_filiales: Callable[[frozenset[str]], list[int]] | None = None
    _memo: dict[str, Any] = field(default_factory=dict)

    def shield(self) -> dict:
        if "shield" not in self._memo:
            self._memo["shield"] = self.charge_shield() if self.charge_shield else {}
        return self._memo["shield"]

    def odoo(self) -> dict | None:
        """La charge Odoo restreinte au périmètre — ou None si elle ne peut pas l'être."""
        if "odoo" not in self._memo:
            if self.charge_odoo is None:
                self._memo["odoo"] = {}
            elif self.perimetre_groupe:
                self._memo["odoo"] = self.charge_odoo(None)
            else:
                ids = (self.societes_des_filiales or (lambda _f: []))(self.filiales)
                self._memo["odoo"] = self.charge_odoo(ids) if ids else None
        return self._memo["odoo"]


def _indisponible(m: Metrique, statut: str, motif: str) -> dict[str, Any]:
    return {"value": None, "status": statut, "reason": motif}


def _lire_kpi(charge: dict, cle: str) -> tuple[Any, str, str]:
    """(valeur, statut, motif) d'un KPI de charge source, `by_kind.x` compris."""
    if cle.startswith("by_kind."):
        bloc = charge.get("by_kind") or {}
        statut = bloc.get("status") or "disconnected"
        valeur = bloc.get(cle.split(".", 1)[1]) if statut == "connected" else None
        return valeur, statut, "" if valeur is not None else "Ventilation par type indisponible."
    for kpi in charge.get("kpis") or []:
        if kpi.get("key") == cle:
            # Le motif de la SOURCE quand le KPI n'en porte pas : « source non
            # déclarée » ou « non connectée » dit quoi faire ; « valeur non
            # servie » ne le disait pas.
            return (kpi.get("value"), kpi.get("status") or "disconnected",
                    kpi.get("detail") or charge.get("detail") or "")
    statut = charge.get("status") or "disconnected"
    return None, statut, charge.get("detail") or "Indicateur absent de la réponse source."


def resoudre(metric_id: str, ctx: Contexte) -> dict[str, Any]:
    """La valeur gouvernée d'une métrique pour CE contexte : valeur, état, provenance."""
    m = REGISTRE.get(metric_id)
    if m is None:
        return {"value": None, "status": "error", "reason": f"Métrique inconnue : {metric_id}."}

    base = {
        "metric_id": m.id, "label": m.libelle, "definition": m.definition,
        "unit": m.unite, "format": m.format, "instant": m.instant,
        "source": m.source, "source_label": LIBELLE_SOURCE[m.source],
    }
    if not ctx.peut_voir(m.domaine):
        return {**base, **_indisponible(m, "disconnected",
                                        "Hors de vos droits : cette métrique relève du "
                                        "domaine Capital Humain.")}
    if m.source == AUCUNE:
        return {**base, **_indisponible(m, "disconnected", m.motif_absence)}

    if m.source == SHIELD:
        if not ctx.perimetre_groupe:
            # Shield ne rattache pas ses sites aux filiales du Groupe : un total
            # Shield est un total GROUPE. L'attribuer à une filiale serait inventer
            # ce rattachement ; le servir tel quel ferait sortir les chiffres des
            # autres filiales. On refuse, et on dit pourquoi.
            return {**base, **_indisponible(
                m, "disconnected",
                "Hors périmètre : Shield ne rattache pas ses sites aux filiales, ses "
                "totaux sont des totaux Groupe.")}
        charge = ctx.shield()
    else:
        charge = ctx.odoo()
        if charge is None:
            return {**base, **_indisponible(
                m, "disconnected",
                "Hors périmètre : aucune société Odoo n'est rattachée à votre filiale. "
                "La correspondance se déclare dans le centre de connecteurs.")}

    valeur, statut, motif = _lire_kpi(charge or {}, m.cle_source)
    if valeur is None:
        return {**base, "value": None,
                "status": statut if statut != "connected" else "disconnected",
                "reason": motif or "Valeur non servie par la source."}
    resultat = {**base, "value": valeur, "status": statut}
    if charge.get("cache"):
        resultat["as_of"] = charge["cache"].get("collecte_le")
    elif charge.get("updated_at"):
        resultat["as_of"] = charge.get("updated_at")
    return resultat
