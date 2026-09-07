"""Connecteur lecture Kaydan Shield → KPIs RH normalisés (ADR-0004).

Architecture imposée : Shield → CE backend → normalisation → API K-Insight → React.
React n'appelle JAMAIS Shield directement. Aucun endpoint n'est inventé : seuls les
chemins réels documentés dans l'OpenAPI Shield (/api/v1/...) sont utilisés.

Gouvernance « aucune donnée inventée » (ADR-0007) : tant que la source `kaydan-shield`
n'existe pas ou n'est pas connectée, on renvoie un état explicite `disconnected`
(valeurs nulles), jamais des chiffres fabriqués.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from datetime import timedelta

from django.utils import timezone

from . import shield_endpoints as EP
from .models import AuthMethod, CredentialKind, DataSource, SourceStatus, SourceType
from . import shield_rules as R
from . import shield_auth
from .shield_client import MAX_ATTEMPTS, ShieldClient, ShieldError

SHIELD_SOURCE_SLUG = "kaydan-shield"

# Les chemins RÉELS vivent dans shield_endpoints.py (source unique).



# ── Résolution source / configuration ────────────────────────────────────────
def get_shield_source() -> DataSource | None:
    return (
        DataSource.objects.filter(source_type=SourceType.KAYDAN_SHIELD, is_active=True)
        .select_related("connector")
        .first()
        or DataSource.objects.filter(slug=SHIELD_SOURCE_SLUG).select_related("connector").first()
    )


def _base_url(source: DataSource) -> str:
    connector = getattr(source, "connector", None)
    url = (getattr(connector, "base_url", "") or "").rstrip("/")
    if not url:
        url = (getattr(settings, "SHIELD_BASE_URL", "") or "").rstrip("/")
    return url


def _pick_secret(connector) -> str:
    """Sélectionne le credential porteur du secret, de façon DÉTERMINISTE.

    `credentials.first()` seul est non déterministe (aucun `ordering` sur le modèle) :
    avec plusieurs identifiants (client_id + api_token…), on risquait d'envoyer le mauvais.
    On privilégie donc le token/clé API, puis le PLUS RÉCENT, et on ignore les vides.

    Le tri est descendant, et ce détail a coûté cher : en prenant le plus ancien, le
    connecteur envoyait indéfiniment le premier jeton jamais enregistré. Chaque
    rotation de secret restait donc sans effet, et Shield répondait 401 quel que
    soit le jeton fraîchement saisi. Un secret qu'on vient de déposer est, par
    construction, celui qu'on veut utiliser.
    """
    preferred = [CredentialKind.API_TOKEN, CredentialKind.API_KEY]
    queryset = connector.credentials.order_by("-created_at")
    for cred in list(queryset.filter(kind__in=preferred)) + list(queryset.exclude(kind__in=preferred)):
        if cred.is_set:
            return cred.secret
    return ""


def _auth_headers(source: DataSource) -> dict[str, str]:
    """Construit les en-têtes d'auth depuis le connecteur (secrets chiffrés) ou l'env.

    HMAC Shield n'est pas encore implémenté ici (squelette) : on gère bearer / api_key /
    header personnalisé, sinon on retombe sur les headers non secrets déclarés.
    """
    headers: dict[str, str] = {"Accept": "application/json", "User-Agent": "k-insight"}
    connector = getattr(source, "connector", None)
    if connector is None:
        token = getattr(settings, "SHIELD_API_TOKEN", "") or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers
    headers.update({k: str(v) for k, v in (connector.headers or {}).items()})
    if connector.auth_method in (AuthMethod.BEARER, AuthMethod.OAUTH2):
        # Session JWT : on passe par le magasin de jetons, qui renouvelle AVANT
        # l'expiration plutôt que d'attendre le 401. Un jeton absent ou une session
        # morte rendent une chaîne vide : pas d'en-tête, et Shield répondra 401,
        # qualifié en `auth_required` par la santé du connecteur.
        jeton, _message = shield_auth.jeton_pour_appel(connector)
        if jeton:
            headers["Authorization"] = f"Bearer {jeton}"
        return headers

    secret = _pick_secret(connector) or (getattr(settings, "SHIELD_API_TOKEN", "") or "")
    if not secret:
        return headers
    elif connector.auth_method == AuthMethod.API_KEY:
        name = (connector.config or {}).get("api_key_header", "X-API-Key")
        headers[name] = secret
    elif connector.auth_method == AuthMethod.HEADER:
        name = (connector.config or {}).get("auth_header", "Authorization")
        headers[name] = secret
    return headers


# ── Client ───────────────────────────────────────────────────────────────────
def build_client(source: DataSource, max_attempts: int = MAX_ATTEMPTS) -> ShieldClient:
    """Client Shield, capable de rattraper UN 401 par renouvellement de session.

    Le rappel force le renouvellement : on n'arrive ici que parce que Shield vient
    de refuser le jeton, donc l'échéance lue localement était optimiste — la
    contrôler une seconde fois ne servirait qu'à ne rien faire.
    """
    connector = getattr(source, "connector", None)

    def reauthentifier():
        if connector is None or connector.auth_method not in (AuthMethod.BEARER, AuthMethod.OAUTH2):
            return None
        ok, _message = shield_auth.renouveler(connector, force=True)
        return _auth_headers(source) if ok else None

    return ShieldClient(
        _base_url(source), _auth_headers(source),
        max_attempts=max_attempts,
        on_auth_failure=reauthentifier if connector is not None else None,
    )


def _today() -> str:
    return timezone.localdate().isoformat()


# ── Normalisation ────────────────────────────────────────────────────────────
MEASURED = "measured"
COMPUTED = "computed"
UNKNOWN = "unknown"


def _kpi(key, title, value, unit="", status="connected", level=MEASURED, formula="", source_field=""):
    return {
        "key": key, "title": title, "value": value, "unit": unit, "status": status,
        "level": level, "formula": formula, "source_field": source_field,
    }


# (clé, libellé, unité, niveau, formule, champ source)
KPI_SPECS: list[tuple[str, str, str, str, str, str]] = [
    ("effectif_total", "Effectif total", "", COMPUTED, "employés + ouvriers", ""),
    ("employes", "Employés", "", MEASURED, "", "employees.count"),
    ("ouvriers", "Ouvriers", "", MEASURED, "", "ouvriers.count"),
    ("presents", "Présents aujourd'hui", "", MEASURED, "", "attendance.present_count"),
    ("absents", "Absents", "", MEASURED, "", "attendance.absent_count"),
    ("retards", "Retards", "", MEASURED, "", "attendance.late_count"),
    ("taux_presence", "Taux de présence", "%", COMPUTED, "présents ÷ (présents + absents) × 100", ""),
    ("sites", "Sites", "", MEASURED, "", "sites.count"),
]
KPI_META = {k: (t, u, lv, f, sf) for k, t, u, lv, f, sf in KPI_SPECS}

SECURITY_SPECS: list[tuple[str, str, str, str, str, str]] = [
    ("alertes_critiques", "Alertes critiques ouvertes", "", MEASURED, "", "antifraud.alerts[severity=critical,status=open]"),
    ("alertes_ouvertes", "Alertes ouvertes", "", MEASURED, "", "antifraud.alerts[status=open]"),
    ("acces_refuses", "Accès refusés (24 h)", "", MEASURED, "", "access.events[decision=denied]"),
    ("terminaux_hs", "Terminaux hors service", "", COMPUTED, "terminaux inactifs + en maintenance + perdus", ""),
    ("terminaux_total", "Terminaux déclarés", "", MEASURED, "", "devices.count"),
    ("visiteurs_attente", "Visiteurs en attente", "", MEASURED, "", "visitors.requests[status=pending]"),
]
SECURITY_META = {k: (t, u, lv, f, sf) for k, t, u, lv, f, sf in SECURITY_SPECS}


def _from_spec(meta, key, value, status):
    title, unit, level, formula, source_field = meta[key]
    return _kpi(key, title, value, unit, status, level, formula, source_field)


def _disconnected(meta, specs):
    return [_from_spec(meta, k, None, "disconnected") for k, *_ in specs]


def _state_of(errors: list[ShieldError | None], values: list[Any]) -> str:
    """État consolidé HONNÊTE d'un lot de lectures.

    `partial` dès qu'une mesure manque : annoncer `connected` alors qu'une partie
    des appels a échoué donnerait l'illusion d'un tableau complet.
    """
    ok = sum(1 for v, e in zip(values, errors) if e is None and v is not None)
    if ok == len(values):
        return "connected"
    if ok:
        return "partial"
    return "error"


def _envelope(status: str, source: str, kpis: list[dict], **extra) -> dict[str, Any]:
    return {
        "status": status,
        "source": source,
        "updated_at": timezone.now().isoformat(),
        "kpis": kpis,
        **extra,
    }


def _guard(kind: str):
    """Contexte commun à toutes les lectures : source absente ou non connectée."""
    source = get_shield_source()
    label = "Kaydan Shield"
    if source is None:
        return None, {"status": "disconnected", "source": label,
                      "detail": "Source kaydan-shield non configurée."}
    if not _base_url(source) or source.status != SourceStatus.CONNECTED:
        return None, {"status": "disconnected", "source": source.name or label,
                      "detail": "Source non connectée — configurez et testez la connexion."}
    return source, None


def _safe(fn):
    """Exécute une lecture ; renvoie (valeur, erreur) sans jamais laisser fuir."""
    try:
        return fn(), None
    except ShieldError as exc:
        return None, exc
    except Exception as exc:  # noqa: BLE001 — un bug de normalisation ne doit pas rendre 500
        return None, ShieldError("payload", f"{type(exc).__name__}: {exc}")


# ── Capital Humain ───────────────────────────────────────────────────────────
MAX_SITES_DETAILED = 12   # borne le fan-out : ~4 appels par site


def _site_row(client: ShieldClient, raw: dict[str, Any], date: str,
              tallies: dict[str, dict[Any, int]], period_failed: set) -> dict[str, Any]:
    """Une ligne de répartition par site.

    Présence, absences et retards viennent de la collecte de période DÉJÀ faite :
    aucun appel supplémentaire. Seuls l'effectif ouvriers et les alertes exigent
    d'autres endpoints, qui n'acceptent pas de regroupement par site.

    `employees` reste `unknown` : l'endpoint employés de Shield n'accepte aucun
    filtre `site`. Le répartir au prorata donnerait un chiffre crédible et faux.
    """
    site_id = raw.get("id")
    workers, w_err = _safe(lambda: client.count(EP.WORKERS, {"site": site_id}))
    alerts, al_err = _safe(lambda: client.count(EP.ALERTS, {"site": site_id, "status": "open"}))

    def from_period(flag):
        return None if flag in period_failed else tallies[flag].get(site_id, 0)

    present, absent, late = from_period("present"), from_period("absent"), from_period("late")
    rate = R.taux_presence(present, absent)
    errs = [w_err, al_err] + [ShieldError("http", "période") if period_failed else None]

    return {
        "site": {"id": site_id, "code": raw.get("code") or "",
                 "name": raw.get("name") or raw.get("code") or "Site",
                 "type": raw.get("type") or "", "status": raw.get("status") or "",
                 "company": raw.get("company_name") or ""},
        "employees": None,
        "employees_status": UNKNOWN,
        "employees_reason": "L'API employés de Shield n'expose pas de filtre par site.",
        "workers": workers,
        "total": None,
        "total_status": UNKNOWN,
        "present": present,
        "absent": absent,
        "late": late,
        "attendance_rate": rate,
        "alerts": alerts,
        "drilldown_url": "/dashboard/capital-humain/presence",
        "status": _state_of(errs, [workers, alerts, present]),
        "updated_at": timezone.now().isoformat(),
    }


def fetch_hr_kpis() -> dict[str, Any]:
    """KPIs RH gouvernés + répartition par site réelle."""
    source, blocked = _guard("hr")
    if blocked:
        label = blocked["source"]
        return {**blocked, "kpis": _disconnected(KPI_META, KPI_SPECS),
                "by_site": {"status": "disconnected", "sites": []}}

    client = build_client(source)
    src = source.name or "Kaydan Shield"
    date = _today()

    employes, e_err = _safe(lambda: client.count(EP.EMPLOYEES))
    ouvriers, o_err = _safe(lambda: client.count(EP.WORKERS))
    sites_count, s_err = _safe(lambda: client.count(EP.SITES))
    summary, sum_err = _safe(lambda: client.get_json(EP.ATTENDANCE_TODAY))

    effectif = employes + ouvriers if isinstance(employes, int) and isinstance(ouvriers, int) else None
    present = absent = late = None
    if isinstance(summary, dict):
        present, absent, late = summary.get("present_count"), summary.get("absent_count"), summary.get("late_count")

    taux = R.taux_presence(present, absent)

    def st(err, value=...):
        return "error" if err else "connected"

    kpis = [
        _from_spec(KPI_META, "effectif_total", effectif, st(e_err or o_err)),
        _from_spec(KPI_META, "employes", employes, st(e_err)),
        _from_spec(KPI_META, "ouvriers", ouvriers, st(o_err)),
        _from_spec(KPI_META, "presents", present, st(sum_err)),
        _from_spec(KPI_META, "absents", absent, st(sum_err)),
        _from_spec(KPI_META, "retards", late, st(sum_err)),
        _from_spec(KPI_META, "taux_presence", taux, st(sum_err)),
        _from_spec(KPI_META, "sites", sites_count, st(s_err)),
    ]

    # UNE collecte de la journée, partagée par la répartition par site ET par
    # la ventilation employés/ouvriers : trois lectures au lieu de 3 par site + 2.
    today_period = collect_period(client, date, date)
    period_failed = set(today_period["errors"])
    tallies = {f: _tally(today_period["rows"][f], lambda r: r.get("site")) for f in FLAGS}

    # Répartition par site : bornée, et détaillée uniquement sur les sites actifs.
    site_rows, sr_err = _safe(lambda: client.results(EP.SITES, {"status": "active"}, limit=MAX_SITES_DETAILED))
    if sr_err or not site_rows:
        by_site = {"status": "error" if sr_err else "disconnected",
                   "detail": str(sr_err) if sr_err else "Aucun site actif publié par Shield.",
                   "sites": []}
    else:
        rows = [_site_row(client, r, date, tallies, period_failed) for r in site_rows]
        oks = [r for r in rows if r["status"] == "connected"]
        by_site = {
            "status": "connected" if len(oks) == len(rows) else ("partial" if oks else "error"),
            "detail": "Effectif employés par site non exposé par Shield ; ouvriers et présence le sont.",
            "date": date,
            "truncated": len(site_rows) >= MAX_SITES_DETAILED,
            "sites": rows,
        }

    by_kind = _presence_by_kind_from(today_period, date)

    status = _state_of([e_err, o_err, s_err, sum_err], [employes, ouvriers, sites_count, summary])
    insights = (R.evaluer_presence_globale(present, absent, late, src, date)
                + R.evaluer_sites(by_site.get("sites", []), src, date))
    return _envelope(status, src, kpis, by_site=by_site, by_kind=by_kind,
                     insights=insights, api_calls=client.metrics.calls)


# ── Période de présence : UNE récupération, agrégée localement ────────────────
# Le schéma live confirme que /attendance/days/ accepte `date_from`/`date_to`,
# pagine (count/next/previous/results) et que chaque enregistrement porte `date`,
# `site` et `holder_kind`. On récupère donc la période entière une fois par
# indicateur (présent / absent / retard) et on agrège ici, au lieu d'interroger
# chaque jour séparément : 3 lectures paginées remplacent 3 appels PAR JOUR.
HOLDER_KINDS = ("employee", "worker")
FLAGS = ("present", "absent", "late")
PAGE_SIZE = 200
MAX_PAGES_PERIOD = 12          # plafond dur : 2 400 enregistrements par indicateur


def _collect_flag(client: ShieldClient, date_from: str, date_to: str, flag: str):
    """Tous les enregistrements de la période portant `flag`, du plus récent au plus ancien.

    L'ordre décroissant est délibéré : si le plafond de pages est atteint, ce sont
    les jours les PLUS ANCIENS qui manquent. On sait alors exactement à partir de
    quelle date la série cesse d'être fiable, au lieu d'avoir des trous au hasard.
    """
    params = {"date_from": date_from, "date_to": date_to, flag: "true", "ordering": "-date"}
    rows: list[dict] = []
    total = None
    for page in range(MAX_PAGES_PERIOD):
        data = client.get_json(EP.ATTENDANCE_DAYS, {**params, "limit": PAGE_SIZE, "offset": page * PAGE_SIZE})
        if not isinstance(data, dict):
            raise ShieldError("payload", "Réponse de période inattendue")
        if total is None:
            total = data.get("count")
        batch = [r for r in (data.get("results") or []) if isinstance(r, dict)]
        rows.extend(batch)
        if len(batch) < PAGE_SIZE or not data.get("next"):
            break
    complete = total is None or len(rows) >= total
    return rows, total, complete


def _oldest_reliable(rows: list[dict], complete: bool) -> str | None:
    """Date à partir de laquelle les comptages sont fiables.

    Si la collecte a été tronquée, la journée la plus ancienne rapportée est
    elle-même potentiellement incomplète : on la considère non fiable aussi.
    """
    if complete or not rows:
        return None
    dates = sorted({r.get("date") for r in rows if r.get("date")})
    if not dates:
        return None
    return dates[1] if len(dates) > 1 else dates[0]


def collect_period(client: ShieldClient, date_from: str, date_to: str) -> dict[str, Any]:
    """Les trois jeux d'enregistrements de la période, avec leur fiabilité."""
    out: dict[str, Any] = {"rows": {}, "errors": {}, "cutoff": None, "truncated": False}
    cutoffs = []
    for flag in FLAGS:
        try:
            rows, total, complete = _collect_flag(client, date_from, date_to, flag)
            out["rows"][flag] = rows
            if not complete:
                out["truncated"] = True
                cutoff = _oldest_reliable(rows, complete)
                if cutoff:
                    cutoffs.append(cutoff)
        except ShieldError as exc:
            out["rows"][flag] = []
            out["errors"][flag] = exc
    out["cutoff"] = max(cutoffs) if cutoffs else None
    return out


def _tally(rows: list[dict], key) -> dict[Any, int]:
    counts: dict[Any, int] = {}
    for r in rows:
        k = key(r)
        if k is None:
            continue
        counts[k] = counts.get(k, 0) + 1
    return counts


def fetch_attendance_series(days: int = 30) -> dict[str, Any]:
    """Série journalière de présence, bâtie sur UNE lecture de période par indicateur.

    Un jour sans mesure exploitable reste à `null` : le mettre à 0 le ferait passer
    pour une journée sans personne, ce qui est un tout autre message.
    """
    window = days if days in R.FENETRES_JOURS else R.MAX_JOURS
    source, blocked = _guard("series")
    if blocked:
        return {**blocked, "days": window, "points": [], "insights": []}

    client = build_client(source)
    src = source.name or "Kaydan Shield"
    today = timezone.localdate()
    start = today - timedelta(days=window - 1)
    period = collect_period(client, start.isoformat(), today.isoformat())

    per_day = {flag: _tally(period["rows"][flag], lambda r: r.get("date")) for flag in FLAGS}
    failed_flags = set(period["errors"])
    cutoff = period["cutoff"]

    points = []
    for offset in range(window - 1, -1, -1):
        date = (today - timedelta(days=offset)).isoformat()
        # Au-delà du point de troncature, on ne SAIT pas : on ne compte pas 0.
        unreliable = bool(failed_flags) or (cutoff is not None and date < cutoff)
        present = None if unreliable else per_day["present"].get(date, 0)
        absent = None if unreliable else per_day["absent"].get(date, 0)
        late = None if unreliable else per_day["late"].get(date, 0)
        points.append({
            "date": date, "present": present, "absent": absent, "late": late,
            "taux_presence": R.taux_presence(present, absent),
            "status": "unknown" if unreliable else "measured",
        })

    mesures = sum(1 for p in points if p["status"] == "measured")
    status = "connected" if mesures == len(points) else ("partial" if mesures else "error")
    detail = None
    if period["truncated"]:
        detail = (f"Volume supérieur au plafond de collecte : les jours antérieurs au "
                  f"{cutoff} ne sont pas comptabilisés.")
    elif failed_flags:
        detail = f"Indicateur(s) indisponible(s) : {', '.join(sorted(failed_flags))}."
    return _envelope(status, src, [], days=window, points=points, measured_days=mesures,
                     detail=detail, api_calls=client.metrics.calls,
                     insights=R.evaluer_tendance(points, src))


def _presence_by_kind_from(period: dict, date: str) -> dict[str, Any]:
    """Présents du jour par `holder_kind`, déduits de la période déjà collectée."""
    if "present" in period["errors"]:
        return {"status": "error", "date": date, "employees": None, "workers": None,
                "total": None, "employees_share": None, "workers_share": None}
    rows = [r for r in period["rows"]["present"] if r.get("date") == date]
    counts = _tally(rows, lambda r: r.get("holder_kind"))
    employees, workers = counts.get("employee", 0), counts.get("worker", 0)
    total = employees + workers
    return {
        "status": "connected", "date": date,
        "employees": employees, "workers": workers, "total": total,
        "employees_share": R._pct(employees, total) if total else None,
        "workers_share": R._pct(workers, total) if total else None,
    }


# ── Risques & Conformité ─────────────────────────────────────────────────────
def fetch_security_kpis() -> dict[str, Any]:
    source, blocked = _guard("security")
    if blocked:
        return {**blocked, "kpis": _disconnected(SECURITY_META, SECURITY_SPECS), "by_site": {"status": "disconnected", "sites": []}}

    client = build_client(source)
    src = source.name or "Kaydan Shield"

    crit, c_err = _safe(lambda: client.count(EP.ALERTS, {"severity": "critical", "status": "open"}))
    open_alerts, oa_err = _safe(lambda: client.count(EP.ALERTS, {"status": "open"}))
    denied, d_err = _safe(lambda: client.count(EP.ACCESS_EVENTS, {"decision": "denied"}))
    devices_total, dt_err = _safe(lambda: client.count(EP.DEVICES))
    # « Hors service » = somme des états non opérationnels documentés.
    down_parts, down_err = [], None
    for state in ("inactive", "maintenance", "lost"):
        value, err = _safe(lambda s=state: client.count(EP.DEVICES, {"status": s}))
        down_parts.append(value)
        down_err = down_err or err
    devices_down = sum(v for v in down_parts if isinstance(v, int)) if all(isinstance(v, int) for v in down_parts) else None
    visitors, v_err = _safe(lambda: client.count(EP.VISITOR_REQUESTS, {"status": "pending"}))

    def st(err):
        return "error" if err else "connected"

    kpis = [
        _from_spec(SECURITY_META, "alertes_critiques", crit, st(c_err)),
        _from_spec(SECURITY_META, "alertes_ouvertes", open_alerts, st(oa_err)),
        _from_spec(SECURITY_META, "acces_refuses", denied, st(d_err)),
        _from_spec(SECURITY_META, "terminaux_hs", devices_down, st(down_err)),
        _from_spec(SECURITY_META, "terminaux_total", devices_total, st(dt_err)),
        _from_spec(SECURITY_META, "visiteurs_attente", visitors, st(v_err)),
    ]
    errors = [c_err, oa_err, d_err, down_err, dt_err, v_err]
    values = [crit, open_alerts, denied, devices_down, devices_total, visitors]
    return _envelope(_state_of(errors, values), src, kpis,
                     insights=security_insights(kpis, src))


# ── Overview Groupe ──────────────────────────────────────────────────────────
def fetch_overview_kpis() -> dict[str, Any]:
    """Agrégats Shield pour la vue Groupe : effectif, présence, sites, alertes.

    Volontairement plus court que les cockpits RH et Risques : la vue Groupe
    donne le pouls, elle ne duplique pas le détail métier.
    """
    source, blocked = _guard("overview")
    specs = [("workforce", "Effectif Shield", "", COMPUTED, "employés + ouvriers", ""),
             ("presents", "Présents aujourd'hui", "", MEASURED, "", "attendance.present_count"),
             ("sites_actifs", "Sites actifs", "", MEASURED, "", "sites[status=active].count"),
             ("alertes_critiques", "Alertes critiques", "", MEASURED, "", "antifraud.alerts[severity=critical,status=open]")]
    meta = {k: (t, u, lv, f, sf) for k, t, u, lv, f, sf in specs}
    if blocked:
        return {**blocked, "kpis": _disconnected(meta, specs)}

    client = build_client(source)
    src = source.name or "Kaydan Shield"

    employes, e_err = _safe(lambda: client.count(EP.EMPLOYEES))
    ouvriers, o_err = _safe(lambda: client.count(EP.WORKERS))
    sites_actifs, s_err = _safe(lambda: client.count(EP.SITES, {"status": "active"}))
    summary, sum_err = _safe(lambda: client.get_json(EP.ATTENDANCE_TODAY))
    crit, c_err = _safe(lambda: client.count(EP.ALERTS, {"severity": "critical", "status": "open"}))

    workforce = employes + ouvriers if isinstance(employes, int) and isinstance(ouvriers, int) else None
    present = summary.get("present_count") if isinstance(summary, dict) else None

    def st(err):
        return "error" if err else "connected"

    kpis = [
        _from_spec(meta, "workforce", workforce, st(e_err or o_err)),
        _from_spec(meta, "presents", present, st(sum_err)),
        _from_spec(meta, "sites_actifs", sites_actifs, st(s_err)),
        _from_spec(meta, "alertes_critiques", crit, st(c_err)),
    ]
    errors = [e_err or o_err, sum_err, s_err, c_err]
    values = [workforce, present, sites_actifs, crit]
    return _envelope(_state_of(errors, values), src, kpis)


# ── Aide à la décision (déterministe) ────────────────────────────────────────
# Aucun modèle, aucune inférence : des seuils explicites appliqués à des mesures
# réelles. Chaque constat porte sa justification chiffrée et sa période.


def _value(kpis: list[dict], key: str):
    for k in kpis:
        if k["key"] == key and k["status"] == "connected":
            return k["value"]
    return None


def security_insights(kpis: list[dict], source: str) -> list[dict]:
    out: list[dict] = []
    crit = _value(kpis, "alertes_critiques")
    if isinstance(crit, int) and crit > 0:
        out.append({
            "id": "sec.alertes_critiques", "severity": "critical",
            "title": f"{crit} alerte(s) critique(s) ouverte(s)",
            "finding": f"Kaydan Shield signale {crit} alerte(s) de sévérité critique non traitée(s).",
            "impact": "Risque de fraude ou d'intrusion non couvert.",
            "level": MEASURED, "source": source, "period": "maintenant", "confidence": 1.0,
            "action": {"label": "Voir les alertes", "to": "/dashboard/risques-conformite/alertes-critiques"},
        })
    down, total = _value(kpis, "terminaux_hs"), _value(kpis, "terminaux_total")
    if isinstance(down, int) and isinstance(total, int) and total > 0 and down > 0:
        part = round(down * 100 / total, 1)
        out.append({
            "id": "sec.terminaux_hs",
            "severity": "critical" if part >= 20 else "warning",
            "title": f"{down} terminal(aux) hors service",
            "finding": f"{down} terminaux sur {total} ne sont pas opérationnels, soit {part} % du parc.",
            "impact": "Contrôle d'accès dégradé sur les points concernés.",
            "level": COMPUTED, "formula": "terminaux (inactifs + maintenance + perdus) ÷ total × 100",
            "source": source, "period": "maintenant", "confidence": 1.0,
            "action": {"label": "Voir les terminaux", "to": "/dashboard/risques-conformite/controle-acces"},
        })
    return out


def shield_health() -> dict[str, Any]:
    """Santé du connecteur, pour SourceHealth et l'écran d'administration."""
    source, blocked = _guard("health")
    if blocked:
        return {**blocked, "reachable": False}
    connector = getattr(source, "connector", None)
    client = build_client(source)
    ok, message = client.healthcheck()

    # Un jeton d'accès expiré alors qu'un renouvellement est possible N'EST PAS une
    # panne : `build_client` vient justement de renouveler avant l'appel. Ce qui est
    # une panne, c'est un refresh mort — et cela mérite son propre état, parce que le
    # geste attendu n'est pas le même : réauthentifier, et non attendre que la source
    # revienne.
    auth = shield_auth.etat_auth(connector) if connector is not None else {}
    if ok:
        statut = "connected"
    elif auth.get("etat") == "auth_required":
        statut = "auth_required"
    else:
        statut = "error"

    return {
        "status": statut,
        "source": source.name or "Kaydan Shield",
        "reachable": ok,
        "detail": message,
        "auth": auth,
        "checked_at": timezone.now().isoformat(),
        # Compteurs d'usage : chemins, durées, types d'erreur. Jamais de jeton,
        # jamais de filtre (un filtre peut porter un identifiant de personne).
        "metrics": client.metrics.as_dict(),
    }
