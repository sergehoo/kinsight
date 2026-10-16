"""Structure des effectifs lue dans Kaydan Shield : contrats, départements, postes,
sociétés, statuts, genre, âge, ancienneté — employés ET ouvriers.

D'OÙ VIENNENT LES CHAMPS. Les filtres documentés de Shield (`shield_endpoints`)
établissent `company`, `contract_type`, `department`, `status` sur les employés et
`site`, `status`, `trade`, `subcontractor` sur les ouvriers. Pour les autres
notions (genre, naissance, embauche, poste, fin de contrat), le nom du champ n'est
pas garanti : on ne retient un candidat QUE s'il figure dans les enregistrements
LIVE, et `decouvrir()` publie les champs réellement exposés pour vérification.
Une notion dont aucun champ n'est présent reste N/D avec son motif — jamais une
valeur supposée, jamais une énumération recopiée : les catégories (CDI, CDD…)
sont celles que Shield renvoie.

CE QUI EST GARDÉ. Seuls des attributs catégoriels (société, département, contrat,
tranche d'âge…) sont conservés, en cache partagé : aucun nom, aucun matricule,
aucune date de naissance exacte. Les répartitions se recalculent par requête,
sous les filtres et le périmètre de l'utilisateur.

UNE SEULE COLLECTE pour tout le cockpit (cache partagé + single-flight, 15 min) :
jamais un appel Shield par widget.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from django.utils import timezone

from . import shield_endpoints as EP

TTL_STRUCTURE = 900

# Candidats par notion, dans l'ordre. Les premiers sont les noms de filtres
# DOCUMENTÉS ; les suivants ne servent que s'ils existent dans la réponse live.
CANDIDATS: dict[str, tuple[str, ...]] = {
    "societe": ("company", "company_name", "company_id"),
    "departement": ("department", "department_name", "department_id"),
    "poste": ("position", "position_name", "position_id", "job_title", "job"),
    "contrat": ("contract_type",),
    "statut": ("status",),
    "genre": ("gender", "sex"),
    "naissance": ("birth_date", "date_of_birth"),
    "embauche": ("hire_date", "date_hired", "start_date", "employment_date"),
    "site": ("site", "site_name", "site_id"),
    "metier": ("trade",),
    "sous_traitant": ("subcontractor",),
}
CANDIDATS_FIN_CONTRAT = ("end_date", "date_end", "contract_end", "expiry_date")

LIBELLES = {
    "societe": "Société", "departement": "Département", "poste": "Poste", "contrat": "Type de contrat",
    "statut": "Statut", "genre": "Genre", "tranche_age": "Tranche d'âge", "tranche_anciennete": "Ancienneté",
    "site": "Site", "metier": "Métier (ouvriers)", "sous_traitant": "Sous-traitant", "nature": "Nature",
}
# Notions catégorielles exposées en filtres et en répartitions.
DIMENSIONS = ("nature", "societe", "departement", "poste", "contrat", "statut", "genre",
              "tranche_age", "tranche_anciennete", "site", "metier", "sous_traitant")
FILTRABLES = ("nature", "societe", "departement", "poste", "contrat", "statut", "site", "metier")
NATURES = {"employe": "Employés", "ouvrier": "Ouvriers"}

TRANCHES_AGE = ((25, "< 25 ans"), (35, "25–34 ans"), (45, "35–44 ans"), (55, "45–54 ans"), (200, "55 ans et +"))
TRANCHES_ANCIENNETE = ((1, "< 1 an"), (3, "1–3 ans"), (5, "3–5 ans"), (10, "5–10 ans"), (200, "10 ans et +"))
HORIZONS_ECHEANCE = (30, 60, 90)
VALEURS_ACTIVES = {"active", "actif", "actived", "enabled"}


# ── Normalisation ────────────────────────────────────────────────────────────

def _champ_present(lignes: list[dict], candidats: Iterable[str]) -> str | None:
    """Le premier candidat réellement présent (non nul) dans les enregistrements live."""
    for c in candidats:
        if any(isinstance(l, dict) and l.get(c) not in (None, "") for l in lignes[:200]):
            return c
    return None


def _libelle(valeur: Any, referentiel: dict[str, str] | None = None, ligne: dict | None = None,
             champ: str | None = None) -> tuple[str, str] | None:
    """(code, libellé) d'une valeur catégorielle, quelle que soit sa forme live."""
    if valeur in (None, ""):
        return None
    if isinstance(valeur, dict):
        code = valeur.get("code") or valeur.get("id") or valeur.get("value")
        nom = valeur.get("name") or valeur.get("label") or valeur.get("title") or valeur.get("code")
        if code is None and nom is None:
            return None
        return str(code if code is not None else nom), str(nom if nom is not None else code)
    code = str(valeur)
    # DRF expose souvent le libellé à côté : `status_display`, `company_name`…
    if ligne is not None and champ:
        for suffixe in ("_display", "_label", "_name"):
            voisin = ligne.get(f"{champ}{suffixe}")
            if isinstance(voisin, str) and voisin:
                return code, voisin
    if referentiel and code in referentiel:
        return code, referentiel[code]
    return code, code


def _date(valeur: Any) -> date | None:
    if isinstance(valeur, str) and len(valeur) >= 10:
        try:
            return date.fromisoformat(valeur[:10])
        except ValueError:
            return None
    return None


def _tranche(annees: float | None, tranches) -> str | None:
    if annees is None or annees < 0:
        return None
    for borne, libelle in tranches:
        if annees < borne:
            return libelle
    return None


def _referentiel(lignes: list[dict]) -> dict[str, str]:
    ref = {}
    for l in lignes:
        ident = l.get("id")
        nom = l.get("name") or l.get("label") or l.get("title") or l.get("code")
        if ident is not None and nom:
            ref[str(ident)] = str(nom)
    return ref


def normaliser(employes: list[dict], ouvriers: list[dict], *, departements: list[dict] = (),
               postes: list[dict] = (), contrats: list[dict] = (), aujourd_hui: date | None = None) -> dict[str, Any]:
    """Lignes catégorielles anonymes + champs effectivement trouvés."""
    aujourd_hui = aujourd_hui or timezone.localdate()
    refs = {"departement": _referentiel(list(departements)), "poste": _referentiel(list(postes))}
    champs: dict[str, dict[str, str | None]] = {"employe": {}, "ouvrier": {}}
    lignes: list[dict[str, Any]] = []

    # Fin de contrat : depuis le référentiel des contrats, rattaché à l'employé.
    champ_fin = _champ_present(list(contrats), CANDIDATS_FIN_CONTRAT)
    champ_employe_contrat = _champ_present(list(contrats), ("employee", "employee_id"))
    fins: dict[str, date] = {}
    types_contrat_par_employe: dict[str, str] = {}
    if champ_fin and champ_employe_contrat:
        for c in contrats:
            e = c.get(champ_employe_contrat)
            e = e.get("id") if isinstance(e, dict) else e
            fin = _date(c.get(champ_fin))
            if e is not None and fin is not None:
                cle = str(e)
                if cle not in fins or fin > fins[cle]:
                    fins[cle] = fin
                    if c.get("contract_type") not in (None, ""):
                        types_contrat_par_employe[cle] = str(c.get("contract_type"))

    for nature, source in (("employe", employes), ("ouvrier", ouvriers)):
        trouves = {notion: _champ_present(source, cands) for notion, cands in CANDIDATS.items()}
        champs[nature] = trouves
        for r in source:
            ligne: dict[str, Any] = {"nature": ("employe", NATURES["employe"]) if nature == "employe"
                                     else ("ouvrier", NATURES["ouvrier"])}
            for notion in ("societe", "departement", "poste", "contrat", "statut", "genre", "site", "metier",
                           "sous_traitant"):
                champ = trouves.get(notion)
                if champ:
                    ligne[notion] = _libelle(r.get(champ), refs.get(notion), r, champ.removesuffix("_id"))
            naissance = _date(r.get(trouves["naissance"])) if trouves.get("naissance") else None
            if naissance:
                ligne["tranche_age"] = (lambda t: (t, t) if t else None)(
                    _tranche((aujourd_hui - naissance).days / 365.25, TRANCHES_AGE))
            embauche = _date(r.get(trouves["embauche"])) if trouves.get("embauche") else None
            if embauche:
                ligne["tranche_anciennete"] = (lambda t: (t, t) if t else None)(
                    _tranche((aujourd_hui - embauche).days / 365.25, TRANCHES_ANCIENNETE))
            if nature == "employe" and r.get("id") is not None and str(r["id"]) in fins:
                ligne["fin_contrat"] = fins[str(r["id"])].isoformat()
            lignes.append(ligne)

    return {"lignes": lignes, "champs": champs,
            "contrats": {"champ_fin": champ_fin, "champ_employe": champ_employe_contrat,
                         "lus": len(contrats)}}


# ── Collecte (une fois pour tout le cockpit) ─────────────────────────────────

def collecter() -> dict[str, Any]:
    from .shield import ShieldError, _guard, build_client

    source, bloque = _guard("hr")
    if bloque:
        return {**bloque, "lignes": []}
    client = build_client(source)
    erreurs, tronque = {}, False

    def lire(chemin, **kw):
        nonlocal tronque
        try:
            rows = client.paginate(chemin, kw.get("params"), page_size=200)
            if len(rows) >= 200 * 10:
                tronque = True
            return rows
        except ShieldError as exc:
            erreurs[chemin] = str(exc)
            return []

    employes = lire(EP.EMPLOYEES)
    ouvriers = lire(EP.WORKERS)
    departements = lire(EP.DEPARTMENTS)
    postes = lire(EP.POSITIONS)
    contrats = lire(EP.CONTRACTS)
    if not employes and not ouvriers and erreurs:
        return {"status": "error", "source": source.name or "Kaydan Shield", "lignes": [],
                "detail": "Lecture des effectifs Shield impossible.", "erreurs": erreurs}
    norme = normaliser(employes, ouvriers, departements=departements, postes=postes, contrats=contrats)
    return {"status": "partial" if (erreurs or tronque) else "connected",
            "source": source.name or "Kaydan Shield", "collecte_le": timezone.now().isoformat(),
            "tronque": tronque, "erreurs": erreurs, **norme}


def charge_structure() -> dict[str, Any]:
    from apps.governance.hr_sources import _cle

    from . import partage
    from .shield import get_shield_source

    source = get_shield_source()
    if source is None:
        return collecter()
    return partage.lire(_cle("shield.structure", source), collecter, ttl=TTL_STRUCTURE)


# ── Lecture : filtres, répartitions, échéances ───────────────────────────────

def _code(ligne: dict, notion: str) -> str | None:
    v = ligne.get(notion)
    return v[0] if isinstance(v, (tuple, list)) and v else None


def appliquer(lignes: list[dict], filtres: dict[str, str]) -> list[dict]:
    actifs = {k: v for k, v in filtres.items() if k in FILTRABLES and v}
    return [l for l in lignes if all(_code(l, k) == v for k, v in actifs.items())]


def repartition(lignes: list[dict], notion: str) -> list[dict[str, Any]]:
    compte: Counter = Counter()
    libelles: dict[str, str] = {}
    for l in lignes:
        v = l.get(notion)
        if isinstance(v, (tuple, list)) and v:
            compte[v[0]] += 1
            libelles[v[0]] = v[1]
    total = sum(compte.values())
    return [{"code": c, "libelle": libelles[c], "valeur": n, "part": round(n * 100 / total, 1) if total else None}
            for c, n in compte.most_common()]


def echeances(lignes: list[dict], aujourd_hui: date) -> dict[str, Any]:
    fins = [date.fromisoformat(l["fin_contrat"]) for l in lignes if l.get("fin_contrat")]
    a_venir = [f for f in fins if f >= aujourd_hui]
    par_horizon = {str(h): sum(1 for f in a_venir if f <= aujourd_hui + timedelta(days=h)) for h in HORIZONS_ECHEANCE}
    proches = [l for l in lignes if l.get("fin_contrat")
               and aujourd_hui <= date.fromisoformat(l["fin_contrat"]) <= aujourd_hui + timedelta(days=90)]
    return {"par_horizon": par_horizon, "echus": sum(1 for f in fins if f < aujourd_hui),
            "par_contrat": repartition(proches, "contrat"), "renseignes": len(fins)}


def lire_structure(charge: dict, filtres: dict[str, str], aujourd_hui: date | None = None) -> dict[str, Any]:
    """Ce qu'un écran affiche : effectifs, répartitions, échéances, listes de filtres."""
    aujourd_hui = aujourd_hui or timezone.localdate()
    toutes = charge.get("lignes") or []
    if not toutes and charge.get("status") in ("disconnected", "error"):
        # Rien n'a été lu : N/D avec le motif de la source — jamais un effectif à 0.
        motif = charge.get("detail") or "Effectifs Shield non lus."
        return {"status": charge.get("status"), "source": charge.get("source"), "detail": motif,
                "effectifs": None, "repartitions": {}, "libelles": {}, "filtres": {}, "applique": {},
                "motifs": {n: motif for n in DIMENSIONS}, "contrats": None, "contrats_motif": motif}
    lignes = appliquer(toutes, filtres)
    champs = charge.get("champs") or {}

    def present(notion: str) -> bool:
        return any(isinstance(l.get(notion), (tuple, list)) for l in toutes)

    repartitions, motifs = {}, {}
    for notion in DIMENSIONS:
        if present(notion):
            repartitions[notion] = repartition(lignes, notion)
        else:
            motifs[notion] = MOTIFS_ABSENCE.get(notion, "Champ non exposé par Shield.")

    employes = [l for l in lignes if _code(l, "nature") == "employe"]
    ouvriers = [l for l in lignes if _code(l, "nature") == "ouvrier"]
    statuts = Counter(str(_code(l, "statut")).lower() for l in lignes if _code(l, "statut"))
    actifs = (sum(n for s, n in statuts.items() if s in VALEURS_ACTIVES)
              if any(s in VALEURS_ACTIVES for s in statuts) else None)
    contrats_info = charge.get("contrats") or {}
    contrats = (echeances(employes, aujourd_hui) if contrats_info.get("champ_fin") and contrats_info.get("champ_employe")
                else None)
    return {
        "status": charge.get("status"), "source": charge.get("source"), "detail": charge.get("detail"),
        "collecte_le": charge.get("collecte_le"), "cache": charge.get("cache"), "tronque": charge.get("tronque", False),
        "effectifs": {"total": len(lignes), "employes": len(employes), "ouvriers": len(ouvriers),
                      "actifs": actifs, "inactifs": (len(lignes) - actifs) if actifs is not None else None},
        "repartitions": repartitions,
        "libelles": {k: LIBELLES.get(k, k) for k in repartitions},
        "motifs": motifs,
        "contrats": contrats,
        "contrats_motif": None if contrats else ("Les dates de fin de contrat ne sont pas exposées par Shield "
                                                 "(référentiel des contrats sans date de fin rattachée)."),
        # Les listes de filtres viennent des données LIVE, jamais d'une liste en dur.
        "filtres": {notion: [{"code": r["code"], "libelle": r["libelle"]}
                             for r in sorted(repartition(toutes, notion), key=lambda r: r["libelle"])]
                    for notion in FILTRABLES if present(notion)},
        "applique": {k: v for k, v in filtres.items() if k in FILTRABLES and v},
        "champs": champs,
    }


MOTIFS_ABSENCE = {
    "genre": "Le genre n'est pas exposé par Shield dans les fiches lues.",
    "tranche_age": "Aucune date de naissance n'est exposée par Shield.",
    "tranche_anciennete": "Aucune date d'embauche n'est exposée par Shield.",
    "poste": "Aucun poste n'est exposé par Shield dans les fiches lues.",
    "societe": "Aucune société n'est exposée par Shield dans les fiches lues.",
    "departement": "Aucun département n'est exposé par Shield dans les fiches lues.",
    "contrat": "Aucun type de contrat n'est exposé par Shield dans les fiches lues.",
}


# ── Découverte : ce que Shield expose VRAIMENT ───────────────────────────────

ENTITES = ("employee", "worker", "ouvrier", "contract", "department", "position", "company", "site", "attendance")


def decouvrir() -> dict[str, Any]:
    """Chemins et champs exposés par le schéma OpenAPI live, plus les clés réellement
    présentes dans les enregistrements — sans aucune valeur personnelle."""
    from .shield import ShieldError, _guard, build_client

    source, bloque = _guard("hr")
    if bloque:
        return bloque
    client = build_client(source)
    sortie: dict[str, Any] = {"status": "connected"}
    try:
        schema = client.get_json(EP.SCHEMA, {"format": "json"}, use_cache=False)
        chemins = sorted((schema or {}).get("paths", {}).keys()) if isinstance(schema, dict) else []
        composants = (schema or {}).get("components", {}).get("schemas", {}) if isinstance(schema, dict) else {}
        sortie["chemins"] = chemins
        sortie["schemas"] = {
            nom: {prop: {k: v for k, v in (spec or {}).items() if k in ("type", "format", "enum", "nullable", "readOnly")}
                  for prop, spec in (val.get("properties") or {}).items()}
            for nom, val in composants.items()
            if any(e in nom.lower() for e in ENTITES) and isinstance(val, dict)
        }
    except ShieldError as exc:
        sortie["schema_erreur"] = str(exc)
    observes = {}
    for nom, chemin in (("employees", EP.EMPLOYEES), ("workers", EP.WORKERS), ("contracts", EP.CONTRACTS),
                        ("departments", EP.DEPARTMENTS), ("positions", EP.POSITIONS), ("sites", EP.SITES)):
        try:
            rows = client.results(chemin, {}, limit=5)
            observes[nom] = sorted({k for r in rows for k in r.keys()})
        except ShieldError as exc:
            observes[nom] = f"indisponible : {exc}"
    sortie["champs_observes"] = observes
    return sortie
