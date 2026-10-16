"""Le rapport Capital Humain : UNE assemblée, trois formats.

Excel, PDF et PowerPoint rendent le MÊME objet, assemblé une fois sous les
filtres et le périmètre de l'utilisateur (ou du destinataire d'un rapport
programmé) : les lectures passent par `lecture_rh`, `signaux_rh`,
`decision_rh` et `score_rh`, exactement comme les écrans. Un export ne peut donc
ni montrer plus que l'écran, ni diverger de lui.

Ce que le rapport porte, pour être vérifiable hors de l'application : le
périmètre, les filtres, la période, la date et l'auteur de l'extraction, les KPI
avec leur source et leur comparaison, les séries quotidiennes réelles, le
classement des sites, les signaux, les constats, le score et la fraîcheur des
sources. Un indicateur non mesuré y figure N/D avec son motif — jamais 0.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Max
from django.utils import timezone

from . import historique as H
from .decision_rh import HRDecisionEngine, synthese_deterministe
from .filtres import FiltreInvalide, Filtres
from .hr_registry import ODOO, REGISTRE, SHIELD
from .lecture_rh import portee, valeur_periode
from .models import Dimension, KpiSnapshot
from .score_rh import calculer
from .signaux_rh import SOURCE_DE, evaluer

# Les KPI du rapport, dans l'ordre de lecture d'un comité de direction.
KPI_RAPPORT = [
    "hr.taux_presence_jour", "hr.presents_jour", "hr.absents_jour", "hr.retards_jour",
    "hr.taux_ponctualite_jour", "hr.taux_absence_jour",
    "hr.effectif_total", "hr.employes", "hr.ouvriers",
    "hr.employes_actifs_odoo", "hr.departements", "hr.postes_a_pourvoir",
    "hr.turnover", "hr.absenteisme_mensuel", "hr.masse_salariale", "hr.heures_supplementaires",
]
# La règle d'agrégation dite dans le libellé : « 655 présents » sur 30 jours
# serait lu comme un total ; c'est une moyenne quotidienne.
SUFFIXE_REGLE = {"moyenne": " · moyenne / jour", "dernier": " · dernière valeur"}
SERIES = [("hr.taux_presence_jour", "Taux de présence (%)"), ("hr.presents_jour", "Présents"),
          ("hr.absents_jour", "Absents"), ("hr.retards_jour", "Retards")]


def _serie(user, metric_id: str, filtres: Filtres) -> list[dict] | None:
    try:
        dimension, codes = portee(user, REGISTRE[metric_id], filtres)
    except FiltreInvalide as refus:
        if refus.code_http != 200:
            raise
        return None
    return H.serie(metric_id, filtres.periode, dimension=dimension, codes=codes)


def _sites(user, filtres: Filtres) -> list[dict]:
    try:
        dimension, codes = portee(user, REGISTRE["hr.taux_presence_jour"], filtres)
    except FiltreInvalide as refus:
        if refus.code_http != 200:
            raise
        return []
    if dimension != Dimension.GROUPE or codes is not None:
        return []
    return H.ventiler("hr.taux_presence_jour", filtres.periode, Dimension.SITE)


def _fraicheur() -> list[dict]:
    from apps.integrations.models import DataSource, SourceType

    dernieres = dict(KpiSnapshot.objects.values_list("source").annotate(m=Max("collecte_le")))
    etats = {}
    for source, type_ in ((SHIELD, SourceType.KAYDAN_SHIELD), (ODOO, SourceType.ODOO_HR)):
        ds = DataSource.objects.filter(source_type=type_).first()
        etats[source] = ds.get_status_display() if ds else "Non déclarée"
    return [{"source": SOURCE_DE[s], "etat": etats[s],
             "derniere_collecte": (timezone.localtime(dernieres[s]).strftime("%d/%m/%Y %H:%M") + " (heure d'Abidjan)")
             if dernieres.get(s) else None}
            for s in (SHIELD, ODOO)]


def structure_pour(user) -> dict[str, Any] | None:
    """Structure des effectifs Shield sous le périmètre de `user` (None si rien de visible
    ou source indisponible) — la même règle que l'écran."""
    try:
        from apps.integrations.shield_structure import lire_structure
        from apps.integrations.views import structure_visible

        charge = structure_visible(user)
    except Exception:  # noqa: BLE001 — une source indisponible n'empêche pas le rapport
        return None
    if not charge or not charge.get("lignes"):
        return None
    return lire_structure(charge, {})


def assembler(user, filtres: Filtres) -> dict[str, Any]:
    """Tout le rapport, sous le périmètre de `user`. Lève `FiltreInvalide` (403, 400)."""
    scope = user.scope()
    kpis = []
    for metric_id in KPI_RAPPORT:
        m = REGISTRE[metric_id]
        v = valeur_periode(user, metric_id, filtres)
        libelle = m.libelle.replace(" du jour", "").replace(" aujourd'hui", "")
        if m.source in (SHIELD, ODOO):
            libelle += SUFFIXE_REGLE.get(m.agregat, "")
        kpis.append({"metric_id": metric_id, "libelle": libelle,
                     "valeur": v.get("value"), "unite": m.unite, "format": m.format, "regle": m.agregat,
                     "source": SOURCE_DE.get(m.source, "Aucune source"), "motif": v.get("reason"),
                     "couverture": v.get("couverture"), "precedente": v.get("precedente")})

    series = {}
    for metric_id, libelle in SERIES:
        points = _serie(user, metric_id, filtres)
        if points is not None:
            series[metric_id] = {"libelle": libelle, "points": points}

    moteur = HRDecisionEngine(user, filtres)
    constats = moteur.constats()
    signaux = evaluer(user, filtres)
    return {
        "titre": "Rapport Capital Humain",
        "genere_le": timezone.now().isoformat(),
        "auteur": user.get_full_name() or user.username,
        "role": getattr(user, "role", ""),
        "perimetre": "Groupe" if scope.is_group else ", ".join(sorted(scope.subsidiaries)) or "aucune filiale",
        "filtres": filtres.comme_trace(),
        "periode": {"debut": filtres.periode.debut.isoformat(), "fin": filtres.periode.fin.isoformat(),
                    "libelle": filtres.libelle},
        "kpis": kpis,
        "series": series,
        "sites": _sites(user, filtres),
        "signaux": signaux["signaux"],
        "compteurs": signaux["compteurs"],
        "constats": constats,
        "synthese": synthese_deterministe(constats, moteur.angles_morts()),
        "score": calculer(user, filtres),
        "structure": structure_pour(user),
        "sources": _fraicheur(),
    }


def libelle_filtres(r: dict) -> str:
    f = r["filtres"]
    morceaux = [f"Période : {r['periode']['libelle']} ({r['periode']['debut']} → {r['periode']['fin']})"]
    for cle, nom in (("subsidiary", "Filiale"), ("site", "Site"), ("type", "Personnel"), ("departement", "Département")):
        if f.get(cle):
            morceaux.append(f"{nom} : {f[cle]}")
    return " · ".join(morceaux)


def valeur_texte(k: dict) -> str:
    v = k.get("valeur")
    if v is None:
        return "N/D"
    if k.get("format") == "pct" or k.get("unite") == "%":
        return f"{v:.1f} %".replace(".", ",")
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", " ")
    return f"{v:.1f}".replace(".", ",")


def _nombre(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def comparaison_texte(k: dict) -> str:
    p = k.get("precedente") or {}
    e = p.get("ecart")
    if e is None:
        return ""
    signe = "+" if e > 0 else "−" if e < 0 else ""
    if p.get("unite_ecart") == "pts":
        return f"{signe}{_nombre(abs(e))} pt{'s' if abs(e) >= 2 else ''} vs préc."
    pct = p.get("ecart_pct")
    relatif = f" ({signe}{_nombre(abs(pct))} %)" if pct is not None and round(abs(pct), 1) >= 0.1 else ""
    return f"{signe}{_nombre(abs(e))}{relatif} vs préc."
