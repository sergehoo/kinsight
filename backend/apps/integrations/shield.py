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
from .shield_client import ShieldClient, ShieldError

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
    On privilégie donc le token/clé API, puis le plus ancien, et on ignore les vides.
    """
    preferred = [CredentialKind.API_TOKEN, CredentialKind.API_KEY]
    queryset = connector.credentials.order_by("created_at")
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
    secret = _pick_secret(connector) or (getattr(settings, "SHIELD_API_TOKEN", "") or "")
    if not secret:
        return headers
    if connector.auth_method in (AuthMethod.BEARER, AuthMethod.OAUTH2):
        headers["Authorization"] = f"Bearer {secret}"
    elif connector.auth_method == AuthMethod.API_KEY:
        name = (connector.config or {}).get("api_key_header", "X-API-Key")
        headers[name] = secret
    elif connector.auth_method == AuthMethod.HEADER:
        name = (connector.config or {}).get("auth_header", "Authorization")
        headers[name] = secret
    return headers


# ── Client ───────────────────────────────────────────────────────────────────
def build_client(source: DataSource) -> ShieldClient:
    return ShieldClient(_base_url(source), _auth_headers(source))


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
    ("acces_refuses", "Accès refusés (24 h)", "", MEASURED, "", "access.events[decision=deny]"),
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


def _site_row(client: ShieldClient, raw: dict[str, Any], date: str) -> dict[str, Any]:
    """Une ligne de répartition par site, montée sur des relations RÉELLES.

    `employees` reste `unknown` : l'endpoint employés de Shield n'accepte aucun
    filtre `site`. Le répartir au prorata donnerait un chiffre crédible et faux.
    """
    site_id = raw.get("id")
    workers, w_err = _safe(lambda: client.count(EP.WORKERS, {"site": site_id}))
    present, p_err = _safe(lambda: client.count(EP.ATTENDANCE_DAYS, {"site": site_id, "date": date, "present": "true"}))
    absent, a_err = _safe(lambda: client.count(EP.ATTENDANCE_DAYS, {"site": site_id, "date": date, "absent": "true"}))
    late, l_err = _safe(lambda: client.count(EP.ATTENDANCE_DAYS, {"site": site_id, "date": date, "late": "true"}))
    alerts, al_err = _safe(lambda: client.count(EP.ALERTS, {"site": site_id, "status": "open"}))

    rate = R.taux_presence(present, absent)
    errs = [w_err, p_err, a_err, l_err, al_err]
    return {
        "site": {"id": site_id, "code": raw.get("code") or "", "name": raw.get("name") or raw.get("code") or "Site",
                 "type": raw.get("type") or "", "status": raw.get("status") or "",
                 "company": raw.get("company_name") or ""},
        "employees": None,
        "employees_status": UNKNOWN,
        "employees_reason": "L'API employés de Shield n'expose pas de filtre par site.",
        "workers": workers,
        "total": None,          # employés inconnus → total non calculable
        "total_status": UNKNOWN,
        "present": present,
        "absent": absent,
        "late": late,
        "attendance_rate": rate,
        "alerts": alerts,
        # Route existante du sous-module Présence : pas de route inventée par site.
        "drilldown_url": "/dashboard/capital-humain/presence",
        "status": _state_of(errs, [workers, present, absent, late, alerts]),
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

    # Répartition par site : bornée, et détaillée uniquement sur les sites actifs.
    site_rows, sr_err = _safe(lambda: client.results(EP.SITES, {"status": "active"}, limit=MAX_SITES_DETAILED))
    if sr_err or not site_rows:
        by_site = {"status": "error" if sr_err else "disconnected",
                   "detail": str(sr_err) if sr_err else "Aucun site actif publié par Shield.",
                   "sites": []}
    else:
        rows = [_site_row(client, r, date) for r in site_rows]
        oks = [r for r in rows if r["status"] == "connected"]
        by_site = {
            "status": "connected" if len(oks) == len(rows) else ("partial" if oks else "error"),
            "detail": "Effectif employés par site non exposé par Shield ; ouvriers et présence le sont.",
            "date": date,
            "truncated": len(site_rows) >= MAX_SITES_DETAILED,
            "sites": rows,
        }

    by_kind = _presence_by_kind(client, date)

    status = _state_of([e_err, o_err, s_err, sum_err], [employes, ouvriers, sites_count, summary])
    insights = (R.evaluer_presence_globale(present, absent, late, src, date)
                + R.evaluer_sites(by_site.get("sites", []), src, date))
    return _envelope(status, src, kpis, by_site=by_site, by_kind=by_kind, insights=insights)


# ── Série de présence ────────────────────────────────────────────────────────
# `holder_kind` est la SEULE ventilation documentée (employee | worker).
# `person_kind` existe comme filtre mais le Swagger n'en documente aucune valeur :
# on ne s'en sert pas plutôt que de deviner.
HOLDER_KINDS = ("employee", "worker")


def _day_counts(client: ShieldClient, date: str, extra: dict | None = None) -> tuple[dict, list]:
    """Compteurs d'une journée, via les filtres DOCUMENTÉS de /attendance/days/.

    On interroge `present`, `absent` et `late` séparément plutôt que d'agréger les
    enregistrements bruts : le champ `status` existe, mais le Swagger n'en publie
    pas les valeurs — en déduire « présent » serait une supposition.
    """
    base = {"date": date, **(extra or {})}
    present, e1 = _safe(lambda: client.count(EP.ATTENDANCE_DAYS, {**base, "present": "true"}))
    absent, e2 = _safe(lambda: client.count(EP.ATTENDANCE_DAYS, {**base, "absent": "true"}))
    late, e3 = _safe(lambda: client.count(EP.ATTENDANCE_DAYS, {**base, "late": "true"}))
    return {"present": present, "absent": absent, "late": late}, [e1, e2, e3]


def fetch_attendance_series(days: int = 30) -> dict[str, Any]:
    """Série journalière de présence sur une fenêtre glissante.

    Un jour sans mesure exploitable reste à `null` : le mettre à 0 le ferait
    passer pour une journée sans personne, ce qui est un tout autre message.
    """
    window = days if days in R.FENETRES_JOURS else R.MAX_JOURS
    source, blocked = _guard("series")
    if blocked:
        return {**blocked, "days": window, "points": [], "insights": []}

    client = build_client(source)
    src = source.name or "Kaydan Shield"
    today = timezone.localdate()
    points: list[dict[str, Any]] = []
    failures = 0

    for offset in range(window - 1, -1, -1):
        date = (today - timedelta(days=offset)).isoformat()
        counts, errs = _day_counts(client, date)
        failed = [e for e in errs if e is not None]
        failures += len(failed)
        points.append({
            "date": date,
            "present": counts["present"],
            "absent": counts["absent"],
            "late": counts["late"],
            "taux_presence": R.taux_presence(counts["present"], counts["absent"]),
            # `unknown` distingue « aucune mesure ce jour-là » de « zéro personne ».
            "status": "unknown" if failed else "measured",
        })

    mesures = sum(1 for p in points if p["status"] == "measured")
    status = "connected" if mesures == len(points) else ("partial" if mesures else "error")
    return _envelope(status, src, [], days=window, points=points,
                     measured_days=mesures,
                     insights=R.evaluer_tendance(points, src))


def _presence_by_kind(client: ShieldClient, date: str) -> dict[str, Any]:
    """Présents du jour ventilés employés / ouvriers, via `holder_kind`."""
    out: dict[str, Any] = {}
    errs: list[Any] = []
    for kind in HOLDER_KINDS:
        value, err = _safe(lambda k=kind: client.count(
            EP.ATTENDANCE_DAYS, {"date": date, "present": "true", "holder_kind": k}))
        out[kind] = value
        errs.append(err)
    ok = [v for v, e in zip(out.values(), errs) if e is None and v is not None]
    total = sum(ok) if len(ok) == len(HOLDER_KINDS) else None
    return {
        "status": "connected" if len(ok) == len(HOLDER_KINDS) else ("partial" if ok else "error"),
        "date": date,
        "employees": out.get("employee"),
        "workers": out.get("worker"),
        "total": total,
        "employees_share": R._pct(out.get("employee"), total) if total else None,
        "workers_share": R._pct(out.get("worker"), total) if total else None,
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
    denied, d_err = _safe(lambda: client.count(EP.ACCESS_EVENTS, {"decision": "deny"}))
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
    ok, message = build_client(source).healthcheck()
    return {
        "status": "connected" if ok else "error",
        "source": source.name or "Kaydan Shield",
        "reachable": ok,
        "detail": message,
        "checked_at": timezone.now().isoformat(),
    }
