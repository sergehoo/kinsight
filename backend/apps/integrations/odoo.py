"""Connecteur lecture Odoo RH → KPIs normalisés (même contrat que Kaydan Shield).

Architecture imposée : Odoo → CE backend → normalisation → API K-Insight → React.
React n'appelle JAMAIS Odoo directement.

CE MODULE ÉTAIT UN SQUELETTE INERTE. Il déclarait une liste de modèles cibles et
renvoyait `not_implemented` — jamais une donnée. Le transport est désormais réel
(`odoo_client`, XML-RPC), et l'instance a été sondée : rh.kaydan.tech, Odoo 18.0.

LA RÈGLE QUI GOUVERNE TOUT CE FICHIER : on ne demande à Odoo que des champs dont
on a VÉRIFIÉ l'existence sur l'instance. Deux raisons, l'une technique et l'autre
de fond.

  Technique : un champ inconnu fait échouer l'appel ENTIER. Demander `date_hired`
  — qui n'existe pas dans Odoo standard — ferait tomber tout l'écran, pas
  seulement la carte concernée.

  De fond : les noms du contrat `raw` (`subsidiary_code`, `department_code`,
  `gross_amount`) ne sont pas ceux d'Odoo. Présumer une correspondance
  reviendrait à publier sous un libellé du Groupe un chiffre qui mesure autre
  chose. Un indicateur dont le champ source est absent reste `disconnected` et
  dit lequel manque — c'est l'ADR-0007 appliqué à une source dont on ne maîtrise
  pas le paramétrage.

CE QUI N'EST PAS ICI. Aucune écriture, aucune donnée nominative : les écrans de
gouvernance consolident des effectifs, ils n'affichent pas de dossiers. Le client
n'expose d'ailleurs que des méthodes de lecture.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from .models import CredentialKind, DataSource, SourceStatus, SourceType
from .odoo_client import ClientOdoo, OdooError

ODOO_SOURCE_SLUG = "odoo-hr"

MEASURED = "measured"
COMPUTED = "computed"

# Modèles Odoo standard visés en lecture, par domaine K-Insight. La présence de
# chacun est VÉRIFIÉE à l'exécution : `hr.payslip` n'existe que si la paie est
# installée, et elle ne fait pas partie d'Odoo Community.
ODOO_MODELS_BY_DOMAIN: dict[str, tuple[str, ...]] = {
    "rh": (
        "hr.employee",          # effectifs, organigramme
        "hr.department",        # répartition par département
        "hr.job",               # postes et métiers
        "hr.contract",          # contrats et échéances
        "hr.leave",             # congés et absences
        "hr.applicant",         # recrutement
        "hr.attendance",        # pointages
        # La paie est sondée bien qu'elle ne fasse PAS partie d'Odoo Community :
        # c'est justement le modèle dont l'absence décide du sort du mart de paie,
        # et le contrat `raw` en dépend (raw.odoo_hr_payslip).
        "hr.payslip",
    ),
    "finance": ("account.move", "account.move.line", "account.account"),
    "operations": ("stock.picking", "purchase.order", "project.task"),
}
ODOO_HR_MODELS = ODOO_MODELS_BY_DOMAIN["rh"]

# (clé, libellé, unité, niveau, formule, champ source Odoo)
KPI_SPECS: list[tuple[str, str, str, str, str, str]] = [
    ("effectif_total", "Effectif total", "", MEASURED, "", "hr.employee[active=true].count"),
    ("employes_actifs", "Employés actifs", "", MEASURED, "", "hr.employee[active=true].count"),
    ("employes_inactifs", "Employés sortis", "", MEASURED, "", "hr.employee[active=false].count"),
    ("departements", "Départements", "", MEASURED, "", "hr.department.count"),
    ("metiers", "Postes définis", "", MEASURED, "", "hr.job.count"),
    ("societes", "Sociétés", "", MEASURED, "", "res.company.count"),
    ("postes_ouverts", "Postes à pourvoir", "", MEASURED, "", "hr.job.no_of_recruitment"),
    ("taux_rotation_sortis", "Part de sortis", "%", COMPUTED,
     "sortis ÷ (actifs + sortis) × 100", ""),
]
KPI_META = {k: (t, u, lv, f, sf) for k, t, u, lv, f, sf in KPI_SPECS}


# ── Résolution de la source ──────────────────────────────────────────────────
def get_odoo_source() -> DataSource | None:
    return (
        DataSource.objects.filter(source_type=SourceType.ODOO_HR, is_active=True)
        .select_related("connector").first()
        or DataSource.objects.filter(slug=ODOO_SOURCE_SLUG).select_related("connector").first()
    )


def _cle_api(connector) -> str:
    """La clé API déposée sur le connecteur, la plus récente d'abord.

    Même tri descendant que pour Shield, et pour la même raison apprise à ses
    dépens : en prenant la plus ancienne, toute rotation de secret restait sans
    effet et la source répondait « refusé » quelle que soit la clé fraîchement
    saisie.
    """
    for kind in (CredentialKind.API_KEY, CredentialKind.API_TOKEN, CredentialKind.PASSWORD):
        cred = connector.credentials.filter(kind=kind).order_by("-created_at").first()
        if cred is not None and cred.is_set:
            try:
                return cred.secret
            except Exception:  # noqa: BLE001 — clé de chiffrement changée
                return ""
    return ""


def build_client(source: DataSource) -> ClientOdoo:
    """Client prêt à lire, monté depuis la configuration du connecteur.

    La base et le login vivent dans `connector.config` — ce ne sont pas des
    secrets — et la clé API dans les identifiants chiffrés. Séparer les deux
    permet de montrer la configuration à l'écran sans jamais exposer la clé.
    """
    connector = getattr(source, "connector", None)
    config = (getattr(connector, "config", None) or {}) if connector else {}
    return ClientOdoo(
        url=(getattr(connector, "base_url", "") or ""),
        base=str(config.get("database") or config.get("db") or ""),
        login=str(config.get("login") or config.get("username") or ""),
        cle=_cle_api(connector) if connector else "",
    )


def _guard():
    """Contexte commun : source absente, non connectée, ou configuration incomplète."""
    source = get_odoo_source()
    label = "Odoo RH"
    if source is None:
        return None, {"status": "disconnected", "source": label,
                      "detail": "Source odoo-hr non déclarée dans le centre de connecteurs."}
    connector = getattr(source, "connector", None)
    if connector is None or not connector.base_url or source.status != SourceStatus.CONNECTED:
        return None, {"status": "disconnected", "source": source.name or label,
                      "detail": "Source non connectée — renseignez l'URL, la base, le compte "
                                "et la clé API, puis testez la connexion."}
    return source, None


def _kpi(key, valeur, statut, detail=""):
    titre, unite, niveau, formule, champ = KPI_META[key]
    ligne = {"key": key, "title": titre, "value": valeur, "unit": unite,
             "status": statut, "level": niveau, "formula": formule, "source_field": champ}
    if detail:
        ligne["detail"] = detail
    return ligne


def _tous_deconnectes(detail: str = "") -> list[dict]:
    return [_kpi(k, None, "disconnected", detail) for k, *_ in KPI_SPECS]


def _enveloppe(status: str, source: str, kpis: list[dict], **extra) -> dict[str, Any]:
    return {"status": status, "source": source,
            "updated_at": timezone.now().isoformat(), "kpis": kpis, **extra}


def _lecture(fn):
    """Exécute une lecture ; rend (valeur, erreur) sans jamais laisser fuir."""
    try:
        return fn(), None
    except OdooError as exc:
        return None, exc
    except Exception as exc:  # noqa: BLE001 — un bug de normalisation ne doit pas rendre 500
        return None, OdooError("protocole", f"{type(exc).__name__}: {exc}")


def _pourcentage(part, total) -> float | None:
    """Jamais 0 par défaut : un rapport indéterminable n'a pas de valeur."""
    if not isinstance(part, int) or not isinstance(total, int) or total <= 0:
        return None
    return round(part * 100 / total, 1)


# ── Lecture RH ───────────────────────────────────────────────────────────────
def fetch_hr_kpis() -> dict[str, Any]:
    """KPIs RH normalisés depuis Odoo, chacun portant son propre état.

    Chaque compteur est lu indépendamment : un modèle absent — la paie, le
    recrutement — retire SA carte sans emporter les autres. C'est la différence
    entre un écran partiellement alimenté, qui reste utile, et un écran vide.
    """
    source, bloque = _guard()
    if bloque:
        return {**bloque, "kpis": _tous_deconnectes(bloque.get("detail", "")),
                "by_department": {"status": "disconnected", "rows": []}}

    client = build_client(source)
    nom = source.name or "Odoo RH"

    # La configuration peut être incomplète : on le dit AVANT de tenter des
    # lectures qui échoueraient toutes de la même façon.
    try:
        client.uid()
    except OdooError as exc:
        return _enveloppe("error", nom, _tous_deconnectes(str(exc)),
                          detail=str(exc), cause=exc.kind,
                          by_department={"status": "error", "rows": []})

    actifs, e_actifs = _lecture(lambda: client.compter("hr.employee", [["active", "=", True]]))
    sortis, e_sortis = _lecture(lambda: client.compter("hr.employee", [["active", "=", False]]))
    departements, e_dep = _lecture(lambda: client.compter("hr.department"))
    metiers, e_met = _lecture(lambda: client.compter("hr.job"))
    societes, e_soc = _lecture(lambda: client.compter("res.company"))

    def etat(err: OdooError | None) -> str:
        # Un modèle absent n'est pas une panne : c'est un module non installé, et
        # la carte doit le dire plutôt que d'afficher « indisponible ».
        if err is None:
            return "connected"
        return "disconnected" if err.kind in ("absent", "droits") else "error"

    def motif(err: OdooError | None) -> str:
        return "" if err is None else str(err)

    kpis = [
        _kpi("effectif_total", actifs, etat(e_actifs), motif(e_actifs)),
        _kpi("employes_actifs", actifs, etat(e_actifs), motif(e_actifs)),
        _kpi("employes_inactifs", sortis, etat(e_sortis), motif(e_sortis)),
        _kpi("departements", departements, etat(e_dep), motif(e_dep)),
        _kpi("metiers", metiers, etat(e_met), motif(e_met)),
        _kpi("societes", societes, etat(e_soc), motif(e_soc)),
        _kpi("postes_ouverts", *_postes_ouverts(client)),
        _kpi("taux_rotation_sortis",
             _pourcentage(sortis, (actifs or 0) + (sortis or 0))
             if e_actifs is None and e_sortis is None else None,
             "connected" if e_actifs is None and e_sortis is None else "disconnected"),
    ]

    erreurs = [e_actifs, e_sortis, e_dep, e_met, e_soc]
    valeurs = [actifs, sortis, departements, metiers, societes]
    obtenues = sum(1 for v, e in zip(valeurs, erreurs) if e is None and v is not None)
    status = "connected" if obtenues == len(valeurs) else ("partial" if obtenues else "error")

    return _enveloppe(status, nom, kpis,
                      by_department=_repartition_par_departement(client),
                      api_calls=client.appels)


def _postes_ouverts(client: ClientOdoo) -> tuple[Any, str, str]:
    """Postes à pourvoir, SI le champ existe sur cette instance.

    `no_of_recruitment` est standard sur `hr.job`, mais un module tiers peut
    l'avoir retiré. On vérifie le schéma d'abord : demander un champ inconnu
    ferait échouer l'appel entier.
    """
    try:
        champs = client.champs_de("hr.job")
    except OdooError as exc:
        return None, ("disconnected" if exc.kind in ("absent", "droits") else "error"), str(exc)
    if "no_of_recruitment" not in champs:
        return None, "disconnected", "Champ `no_of_recruitment` absent de hr.job sur cette instance."
    lignes, err = _lecture(lambda: client.lire("hr.job", ["no_of_recruitment"], limite=500))
    if err is not None:
        return None, ("disconnected" if err.kind in ("absent", "droits") else "error"), str(err)
    total = sum(int(l.get("no_of_recruitment") or 0) for l in lignes)
    return total, "connected", ""


def _repartition_par_departement(client: ClientOdoo) -> dict[str, Any]:
    """Effectif par département, agrégé LOCALEMENT.

    On lit les employés avec leur `department_id` puis on compte ici, plutôt que
    d'appeler `read_group` : cette méthode a changé de signature entre les
    versions récentes d'Odoo, et le connecteur doit survivre à une montée de
    version sans réécriture. Le volume reste borné.
    """
    try:
        champs = client.champs_de("hr.employee")
    except OdooError as exc:
        return {"status": "disconnected" if exc.kind in ("absent", "droits") else "error",
                "detail": str(exc), "rows": []}
    if "department_id" not in champs:
        return {"status": "disconnected",
                "detail": "Champ `department_id` absent de hr.employee sur cette instance.",
                "rows": []}

    lignes, err = _lecture(lambda: client.lire(
        "hr.employee", ["department_id"], [["active", "=", True]], limite=MAX_EMPLOYES))
    if err is not None:
        return {"status": "disconnected" if err.kind in ("absent", "droits") else "error",
                "detail": str(err), "rows": []}

    comptes: dict[str, int] = {}
    sans_departement = 0
    for ligne in lignes:
        dep = ligne.get("department_id")
        # Odoo rend une relation sous la forme [id, libellé], ou False si vide.
        if isinstance(dep, (list, tuple)) and len(dep) == 2:
            comptes[str(dep[1])] = comptes.get(str(dep[1]), 0) + 1
        else:
            sans_departement += 1

    rows = [{"department": nom, "headcount": n}
            for nom, n in sorted(comptes.items(), key=lambda kv: -kv[1])]
    tronque = len(lignes) >= MAX_EMPLOYES
    return {
        "status": "partial" if tronque else "connected",
        # Le plafond est DIT : une répartition tronquée présentée comme complète
        # ferait croire à un effectif plus petit qu'il n'est.
        "detail": (f"Lecture bornée à {MAX_EMPLOYES} employés : la répartition est incomplète."
                   if tronque else ""),
        "unassigned": sans_departement,
        "rows": rows,
    }


# Borne de lecture : au-delà, on préfère une répartition explicitement partielle
# à une requête qui immobiliserait un worker web.
MAX_EMPLOYES = 2000


def fetch_hr_reference() -> dict[str, Any]:
    """État du référentiel RH Odoo : quels modèles existent et ce qu'ils contiennent.

    Sert au centre de connecteurs et au diagnostic. Ne renvoie aucune donnée
    nominative — uniquement des présences et des volumes.
    """
    source, bloque = _guard()
    modeles = list(ODOO_HR_MODELS)
    if bloque:
        return {**bloque, "models": modeles,
                "models_by_domain": {k: list(v) for k, v in ODOO_MODELS_BY_DOMAIN.items()},
                "records": []}

    client = build_client(source)
    nom = source.name or "Odoo RH"
    try:
        client.uid()
    except OdooError as exc:
        return {"status": "error", "source": nom, "detail": str(exc), "cause": exc.kind,
                "models": modeles,
                "models_by_domain": {k: list(v) for k, v in ODOO_MODELS_BY_DOMAIN.items()},
                "records": []}

    lignes = []
    for modele in modeles + ["res.company"]:
        nombre, err = _lecture(lambda m=modele: client.compter(m))
        lignes.append({
            "model": modele,
            "present": err is None,
            "count": nombre,
            "detail": "" if err is None else str(err),
        })
    presents = sum(1 for l in lignes if l["present"])
    return {
        "status": "connected" if presents == len(lignes) else ("partial" if presents else "error"),
        "source": nom,
        "updated_at": timezone.now().isoformat(),
        "models": modeles,
        "models_by_domain": {k: list(v) for k, v in ODOO_MODELS_BY_DOMAIN.items()},
        "records": lignes,
        "api_calls": client.appels,
    }


def odoo_health() -> dict[str, Any]:
    """Santé du connecteur, pour l'écran d'administration. Aucune donnée métier."""
    source, bloque = _guard()
    if bloque:
        return {"status": "disconnected", "source": bloque["source"], "detail": bloque["detail"]}
    client = build_client(source)
    debut = timezone.now()
    try:
        uid = client.uid()
    except OdooError as exc:
        return {"status": "auth_required" if exc.kind in ("auth", "config") else "error",
                "source": source.name or "Odoo RH", "detail": str(exc), "cause": exc.kind}
    latence = int((timezone.now() - debut).total_seconds() * 1000)
    return {"status": "connected", "source": source.name or "Odoo RH",
            "detail": "Authentification Odoo acceptée.", "uid_present": bool(uid),
            "latency_ms": latence}
