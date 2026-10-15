"""Endpoint générique de données par module (gabarit data réelle).

GET /api/v1/governance/module/<key>/?year=&quarter=
- clé liée (cf. `hr_registry.LIAISONS`) → chaque carte résolue par identifiant de
  métrique depuis Shield ou Odoo, avec provenance, définition et motif d'absence
- clé non liée → `available: false` (le frontend garde N/D gouverné)
Filtré par périmètre RBAC, journalisé (audit).
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

from django.http import HttpResponse

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.rbac import can_access_domain

from k_insight.access import filter_by_scope
from k_insight.kpi.alerts import SCORE_RULES, SEVERITY_ORDER, TREND_DROP_RULES, most_severe
from k_insight.kpi.domain_scores import DOMAIN_SCORES, domain_score
from k_insight.semantic.grounding import answer as ground_answer
from k_insight.semantic.registry import CATALOG
from k_insight.kpi.group_score import GROUP_DOMAINS, group_governance_index
from k_insight.kpi.hr_score import HC_DIMENSIONS, human_capital_score
from k_insight.kpi.hr_mart import (
    payroll_by_subsidiary,
    total_entries,
    total_exits,
    total_payroll_mass,
)

from apps.audit.middleware import audit_source
from apps.audit.models import AccessLog

from .exports import scores_pdf, scores_workbook
from .gateway import fetch_or_unavailable, get_mart_gateway
from django.utils import timezone

from . import filtres as F
from . import score_rh
from .hr_registry import REGISTRE, liaisons, resoudre
from .lecture_rh import valeur_du_jour, valeur_periode
from .hr_sources import contexte_pour
from .services import period_from_quarter


def _governed(key: str) -> Response:
    return Response({"key": key, "available": False, "source": None, "values": {}, "series": []})


def _forbidden(domain: str) -> Response:
    return Response(
        {"detail": f"Accès au domaine « {domain} » non autorisé pour votre rôle."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _dims_avg(rows):
    """Moyenne par dimension sur un ensemble de lignes (month, sub, dim, score)."""
    buckets = defaultdict(list)
    for (_m, _s, key, score) in rows:
        buckets[key].append(score)
    return {key: mean(vals) for key, vals in buckets.items()}


def aggregate_score(all_rows, period, dim_meta, score_fn):
    """Agrégation commune des scores (HR & domaines).

    `all_rows` : lignes (month, sub, dim, score) déjà filtrées périmètre + filiale.
    `dim_meta` : liste de dicts {key, label, weight, ...} dans l'ordre d'affichage.
    `score_fn` : { dim_key -> moyenne } -> score global pondéré renormalisé (ou None).
    Retourne (global_score, dimensions, by_subsidiary, trend) — gouverné N/D si vide.
    """
    period_rows = [r for r in all_rows if period.contains(r[0])]
    avgs = _dims_avg(period_rows)
    dimensions = [
        {**meta, "score": round(avgs[meta["key"]], 1) if meta["key"] in avgs else None}
        for meta in dim_meta
    ]
    by_sub = defaultdict(list)
    for r in period_rows:
        by_sub[r[1]].append(r)
    by_subsidiary = [{"code": code, "score": score_fn(_dims_avg(rs))} for code, rs in sorted(by_sub.items())]
    by_month = defaultdict(list)
    for r in all_rows:
        by_month[r[0]].append(r)
    trend = [{"month": m.isoformat(), "score": score_fn(_dims_avg(rs))} for m, rs in sorted(by_month.items())][-12:]
    return score_fn(avgs), dimensions, by_subsidiary, trend


def _domain_rows(gateway, domain: str) -> list[tuple]:
    """Lignes de score brutes d'un domaine : RH via mart.hr_score, autres via mart.domain_score."""
    return gateway.fetch_hr_score() if domain == "capital-humain" else gateway.fetch_domain_score(domain)


def _domain_score_fn(domain: str):
    """Fonction de score global d'un domaine (pondérations propres au domaine)."""
    if domain == "capital-humain":
        return human_capital_score
    return lambda avgs: domain_score(domain, avgs)


def build_group_report(user, year: int, quarter: int, sub_param: Optional[str]) -> dict:
    """Indice de Gouvernance Groupe consolidé (réutilisé par l'API et l'export).

    Agrège chaque domaine via son cadre puis pondère par domaine ; renormalise sur les
    domaines/filiales disponibles (gouverné N/D, ADR-0007). Filtré par périmètre RBAC.
    """
    period = period_from_quarter(year, quarter)
    scope = user.scope()

    def allowed(code: str) -> bool:
        return scope.allows(code) and (not sub_param or sub_param == "all" or code == sub_param)

    gateway = get_mart_gateway()
    per_domain = []
    for domain, label, weight in GROUP_DOMAINS:
        rows = [r for r in _domain_rows(gateway, domain) if allowed(r[1])]
        g, _dims, by_sub, trend = aggregate_score(rows, period, [], _domain_score_fn(domain))
        per_domain.append(
            {
                "domain": domain,
                "label": label,
                "weight": weight,
                "score": g,
                "_by_sub": {s["code"]: s["score"] for s in by_sub},
                "_trend": {t["month"]: t["score"] for t in trend},
            }
        )

    domain_globals = {d["domain"]: d["score"] for d in per_domain if d["score"] is not None}
    group_global = group_governance_index(domain_globals)

    # Indice par filiale : renormalisé sur les domaines DISPONIBLES de cette filiale (ADR-0007).
    codes = sorted({c for d in per_domain for c in d["_by_sub"]})
    by_subsidiary = []
    for code in codes:
        dg = {d["domain"]: d["_by_sub"][code] for d in per_domain if d["_by_sub"].get(code) is not None}
        by_subsidiary.append({"code": code, "score": group_governance_index(dg)})

    months = sorted({m for d in per_domain for m in d["_trend"]})[-12:]
    trend = []
    for month in months:
        dg = {d["domain"]: d["_trend"][month] for d in per_domain if d["_trend"].get(month) is not None}
        trend.append({"month": month, "score": group_governance_index(dg)})

    return {
        "available": group_global is not None,
        "global": group_global,
        "domains": [
            {"domain": d["domain"], "label": d["label"], "weight": d["weight"], "score": d["score"]}
            for d in per_domain
        ],
        "by_subsidiary": by_subsidiary,
        "trend": trend,
        "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
        "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
    }


# Domaine(s) d'un module hors Capital Humain qui porte des métriques RH. L'accès au
# MODULE se décide par l'un de ses domaines ; chaque métrique RH garde ensuite sa
# propre exigence Capital Humain (`hr_registry.resoudre`).
MODULE_DOMAINES: dict[str, tuple[str, ...]] = {
    "chantier-resources": ("immobilier",),
    "security": ("immobilier", "risques-conformite"),
}


class ModuleDataView(APIView):
    """Valeurs réelles d'un module, résolues par IDENTIFIANT de métrique, sous filtres.

    Pour chaque carte :
      - `value` / `status` / `reason` : la valeur de la PÉRIODE filtrée, tirée de
        l'historique, avec sa couverture et l'écart à la période précédente ;
      - `aujourd_hui` : la mesure live du jour, sous les mêmes filtres quand la
        source le permet, marquée comme telle.
    Un filtre qui ne peut pas s'appliquer à une carte la rend N/D avec son motif :
    il n'est jamais ignoré au profit du total Groupe.

    Aucune lecture du mart : il n'est plus une condition des écrans RH (ADR-0009).
    """

    def get(self, request, key: str):
        lies = liaisons(key)
        if not lies:
            return _governed(key)
        domaines = MODULE_DOMAINES.get(key, ("capital-humain",))
        if not any(can_access_domain(request.user, d) for d in domaines):
            return _forbidden(domaines[0])

        try:
            filtres = F.lire(request.query_params, timezone.localdate())
        except F.FiltreInvalide as refus:
            if refus.code_http != status.HTTP_200_OK:
                return Response({"detail": refus.motif}, status=refus.code_http)
            filtres = None
            motif_periode = refus.motif
        scope = request.user.scope()
        contexte = contexte_pour(request.user)

        values = {}
        for libelle, metric_id in lies.items():
            live = (valeur_du_jour(metric_id, contexte, filtres) if filtres
                    else resoudre(metric_id, contexte))
            carte = {k: v for k, v in live.items() if k not in ("value", "status", "reason", "as_of")}
            if REGISTRE[metric_id].source not in ("shield", "odoo") or not contexte.peut_voir(REGISTRE[metric_id].domaine):
                carte.update(value=None, status=live.get("status"), reason=live.get("reason"))
            elif filtres is None:
                carte.update(value=None, status="disconnected", reason=motif_periode)
            else:
                try:
                    periode = valeur_periode(request.user, metric_id, filtres)
                except F.FiltreInvalide as refus:
                    return Response({"detail": refus.motif}, status=refus.code_http)
                carte.update(value=periode.get("value"), status=periode.get("status"),
                             periode={k: periode.get(k) for k in ("libelle", "debut", "fin", "couverture")},
                             precedente=periode.get("precedente"))
                if periode.get("value") is None:
                    # Sans historique ET sans live, c'est la SOURCE qu'il faut
                    # nommer : « historique en constitution » masquerait la cause.
                    carte["reason"] = (live.get("reason") if live.get("value") is None and live.get("reason")
                                       else periode.get("reason"))
            if REGISTRE[metric_id].instant:
                carte["aujourd_hui"] = {"value": live.get("value"), "status": live.get("status"),
                                        "reason": live.get("reason"), "as_of": live.get("as_of")}
            values[libelle] = carte

        AccessLog.record(
            user=request.user,
            action="query_module",
            metric_key=key,
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={**(filtres.comme_trace() if filtres else {}),
                     "metrics": sorted(set(lies.values()))},
            **audit_source(request),
        )

        servies = [v for v in values.values()
                   if v.get("value") is not None or (v.get("aujourd_hui") or {}).get("value") is not None]
        return Response(
            {
                "key": key,
                "available": bool(servies),
                "source": "registre RH (Shield + Odoo)",
                "period": ({"start": filtres.periode.debut.isoformat(), "end": filtres.periode.fin.isoformat(),
                            "label": filtres.libelle} if filtres else None),
                "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
                "values": values,
                "series": [],
            }
        )


class HrScoreView(APIView):
    """Human Capital Score calculé sur données RÉELLES (`score_rh`), sous filtres.

    Lisait `mart.hr_score`, qu'un seul jeu de démonstration alimentait, affiché
    « Données EDW — réel ». Désormais : chaque dimension scorée si ses données le
    permettent (règle de conversion écrite), N/D motivé sinon ; global publié
    seulement si les dimensions scorées couvrent assez du poids total.
    """

    def get(self, request):
        if not can_access_domain(request.user, "capital-humain"):
            return _forbidden("capital-humain")
        try:
            filtres = F.lire(request.query_params, timezone.localdate())
        except F.FiltreInvalide as refus:
            if refus.code_http != status.HTTP_200_OK:
                return Response({"detail": refus.motif}, status=refus.code_http)
            return Response({"available": False, "global": None, "motif_global": refus.motif,
                             "dimensions": [], "by_subsidiary": [], "trend": []})
        try:
            resultat = score_rh.calculer(request.user, filtres)
        except F.FiltreInvalide as refus:
            return Response({"detail": refus.motif}, status=refus.code_http)

        scope = request.user.scope()
        AccessLog.record(
            user=request.user, action="query_hr_score", metric_key="hr.human_capital_score",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload=filtres.comme_trace(), **audit_source(request),
        )
        return Response({
            "available": resultat["global"] is not None,
            "source": "historique K-Insight (Kaydan Shield + Odoo)",
            "source_state": "connected" if any(d["score"] is not None for d in resultat["dimensions"])
                            else "disconnected",
            "global": resultat["global"],
            "motif_global": resultat["motif_global"],
            "couverture": resultat["couverture"],
            "dimensions": resultat["dimensions"],
            # Aucun score PAR FILIALE : Shield ne rattache pas ses sites aux
            # filiales. Le dire vaut mieux que des cartes KRE/KSH/MYK à N/D.
            "by_subsidiary": [],
            "by_subsidiary_motif": "Non rattaché : la présence Shield n'est pas ventilée par filiale.",
            "trend": resultat["tendance"],
            "period": {"start": filtres.periode.debut.isoformat(), "end": filtres.periode.fin.isoformat(),
                       "label": filtres.libelle},
            "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
        })


class DomainScoreView(APIView):
    """Score de Gouvernance générique par domaine métier.

    GET /api/v1/governance/score/<domain>/?year&quarter&subsidiary
    Lit `mart.domain_score` filtré sur le domaine. Cadre (dimensions + poids) = domaine pur
    `kpi/domain_scores.py`. Gouverné N/D si une dimension n'est pas alimentée (ADR-0007).
    """

    def get(self, request, domain: str):
        framework = DOMAIN_SCORES.get(domain)
        if framework is None:
            return Response(
                {"detail": f"Aucun cadre de score pour le domaine « {domain} »."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not can_access_domain(request.user, domain):
            return _forbidden(domain)
        try:
            year = int(request.query_params.get("year") or timezone.localdate().year)
            quarter = int(request.query_params.get("quarter") or F.trimestre_courant(timezone.localdate()))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quarter <= 4:
            return Response({"detail": "'quarter' doit être entre 1 et 4."}, status=status.HTTP_400_BAD_REQUEST)

        period = period_from_quarter(year, quarter)
        scope = request.user.scope()
        sub_param = request.query_params.get("subsidiary")

        def allowed(code: str) -> bool:
            return scope.allows(code) and (not sub_param or sub_param == "all" or code == sub_param)

        raw, mart_ok = fetch_or_unavailable(lambda: get_mart_gateway().fetch_domain_score(domain), [])
        rows = [r for r in raw if allowed(r[1])]
        dim_meta = [
            {
                "key": d.key,
                "label": d.label,
                "weight": d.weight,
                "mart_source": d.mart_source,
                "rationale": d.rationale,
            }
            for d in framework.dimensions
        ]
        global_score, dimensions, by_subsidiary, trend = aggregate_score(
            rows, period, dim_meta, lambda avgs: domain_score(domain, avgs)
        )

        AccessLog.record(
            user=request.user,
            action="query_domain_score",
            **audit_source(request),
            metric_key=f"{domain}.governance_score",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter, "domain": domain},
        )
        return Response(
            {
                "domain": domain,
                "label": framework.label,
                "available": global_score is not None,
                "source_state": "connected" if mart_ok else "error",
                "global": global_score,
                "dimensions": dimensions,
                "by_subsidiary": by_subsidiary,
                "trend": trend,
                "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
                "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
            }
        )


class GroupScoreView(APIView):
    """Indice de Gouvernance Groupe consolidé : moyenne pondérée des scores par domaine.

    GET /api/v1/governance/score-group/?year&quarter&subsidiary
    Agrège RH (mart.hr_score) + domaines métier (mart.domain_score) via leurs cadres
    respectifs, puis pondère par domaine (kpi/group_score.py). Gouverné N/D : un domaine
    sans donnée est exclu et l'indice renormalisé (ADR-0007).
    """

    def get(self, request):
        # Indice consolidé Groupe → réservé aux profils ayant l'accès « Groupe / Overview ».
        if not can_access_domain(request.user, "overview"):
            return _forbidden("overview")
        try:
            year = int(request.query_params.get("year") or timezone.localdate().year)
            quarter = int(request.query_params.get("quarter") or F.trimestre_courant(timezone.localdate()))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quarter <= 4:
            return Response({"detail": "'quarter' doit être entre 1 et 4."}, status=status.HTTP_400_BAD_REQUEST)

        scope = request.user.scope()
        report = build_group_report(request.user, year, quarter, request.query_params.get("subsidiary"))
        AccessLog.record(
            user=request.user,
            action="query_group_score",
            **audit_source(request),
            metric_key="group.governance_index",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter},
        )
        return Response(report)


class AiQueryView(APIView):
    """IA de gouvernance ANCRÉE : répond uniquement depuis le catalogue + le mart.

    POST /api/v1/governance/ai/query/  body {"question": "..."}
    Garantie (ADR-0007) : aucune métrique inventée (refus si hors catalogue), aucune valeur
    inventée (N/D tant que la source n'est pas branchée). Journalisé (audit).
    """

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        if not question:
            return Response({"detail": "'question' est requise."}, status=status.HTTP_400_BAD_REQUEST)

        # value_lookup gouverné : aucune métrique du catalogue n'est encore liée au mart
        # (les bindings arrivent domaine par domaine) → valeur None = N/D, jamais inventée.
        result = ground_answer(CATALOG, question, lambda _key: None)

        scope = request.user.scope()
        AccessLog.record(
            user=request.user,
            action="query_ai",
            **audit_source(request),
            metric_key=(result["metric"]["key"] if result["metric"] else ""),
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"grounded": result["grounded"], "question": question[:200]},
        )
        return Response(result)


class AlertsView(APIView):
    """Centre d'alertes : règles à seuils évaluées sur les scores de gouvernance réels.

    GET /api/v1/governance/alerts/?year&quarter&subsidiary
    Gouverné (ADR-0007) : une valeur N/D ne déclenche aucune alerte. Périmètre RBAC appliqué.
    """

    def get(self, request):
        if not can_access_domain(request.user, "overview"):
            return _forbidden("overview")
        try:
            year = int(request.query_params.get("year") or timezone.localdate().year)
            quarter = int(request.query_params.get("quarter") or F.trimestre_courant(timezone.localdate()))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quarter <= 4:
            return Response({"detail": "'quarter' doit être entre 1 et 4."}, status=status.HTTP_400_BAD_REQUEST)

        scope = request.user.scope()
        report = build_group_report(request.user, year, quarter, request.query_params.get("subsidiary"))
        alerts: list[dict] = []

        def add(alert, scope_label: str, source: str, kind: str = "score"):
            if alert is None:
                return
            alerts.append(
                {
                    "severity": alert.severity,
                    "label": alert.label,
                    "scope": scope_label,
                    "source": source,
                    "kind": kind,
                    "value": round(alert.value, 1),
                    "threshold": alert.threshold,
                }
            )

        add(most_severe(SCORE_RULES, report["global"]), "Groupe", "group.governance_index")
        for d in report["domains"]:
            add(most_severe(SCORE_RULES, d["score"]), d["label"], f"{d['domain']}.governance_score")
        for s in report["by_subsidiary"]:
            add(most_severe(SCORE_RULES, s["score"]), f"Filiale {s['code']}", "group.governance_index")

        # Chute de tendance Groupe sur le dernier mois (points perdus).
        pts = [t["score"] for t in report["trend"] if t["score"] is not None]
        if len(pts) >= 2:
            add(most_severe(TREND_DROP_RULES, pts[-2] - pts[-1]), "Groupe", "tendance", kind="trend")

        alerts.sort(key=lambda a: SEVERITY_ORDER[a["severity"]], reverse=True)
        counts = {sev: sum(1 for a in alerts if a["severity"] == sev) for sev in SEVERITY_ORDER}

        AccessLog.record(
            user=request.user,
            action="query_alerts",
            **audit_source(request),
            metric_key="governance.alerts",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter, "count": len(alerts)},
        )
        return Response(
            {
                "available": report["available"],
                "count": len(alerts),
                "counts": counts,
                "alerts": alerts,
                "period": report["period"],
                "scope": report["scope"],
            }
        )


class ExportGroupScoreView(APIView):
    """Export du tableau de bord Indice Groupe en XLSX ou PDF (périmètre RBAC appliqué).

    GET /api/v1/governance/export/groupe.<xlsx|pdf>?year&quarter&subsidiary
    """

    _RENDERERS = {
        "xlsx": (scores_workbook, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "pdf": (scores_pdf, "application/pdf"),
    }

    def get(self, request, ext: str):
        if not can_access_domain(request.user, "overview"):
            return _forbidden("overview")
        if ext not in self._RENDERERS:
            return Response({"detail": "Format non supporté (xlsx, pdf)."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            year = int(request.query_params.get("year") or timezone.localdate().year)
            quarter = int(request.query_params.get("quarter") or F.trimestre_courant(timezone.localdate()))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quarter <= 4:
            return Response({"detail": "'quarter' doit être entre 1 et 4."}, status=status.HTTP_400_BAD_REQUEST)

        scope = request.user.scope()
        report = build_group_report(request.user, year, quarter, request.query_params.get("subsidiary"))
        renderer, content_type = self._RENDERERS[ext]
        payload = renderer(report)

        AccessLog.record(
            user=request.user,
            action="export_group_score",
            **audit_source(request),
            metric_key="group.governance_index",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter, "format": ext},
        )
        resp = HttpResponse(payload, content_type=content_type)
        resp["Content-Disposition"] = f'attachment; filename="k-insight-gouvernance-{year}-T{quarter}.{ext}"'
        return resp
