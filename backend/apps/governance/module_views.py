"""Endpoint générique de données par module (gabarit data réelle).

GET /api/v1/governance/module/<key>/?year=&quarter=
- clé liée (cf. bindings) → valeurs réelles depuis le mart + séries, `available: true`
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

from apps.audit.models import AccessLog

from .bindings import HR_MART_SOURCE, hr_binding
from .exports import scores_pdf, scores_workbook
from .gateway import get_mart_gateway
from .services import period_from_quarter


def _governed(key: str) -> Response:
    return Response({"key": key, "available": False, "source": None, "values": {}, "series": []})


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


class ModuleDataView(APIView):
    def get(self, request, key: str):
        binding = hr_binding(key)
        if not binding:
            return _governed(key)

        try:
            year = int(request.query_params.get("year", "2026"))
            quarter = int(request.query_params.get("quarter", "1"))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quarter <= 4:
            return Response({"detail": "'quarter' doit être entre 1 et 4."}, status=status.HTTP_400_BAD_REQUEST)

        period = period_from_quarter(year, quarter)
        scope = request.user.scope()
        rows = get_mart_gateway().fetch_hr_kpi()
        scoped = filter_by_scope(rows, scope, key=lambda r: r.subsidiary)
        # Filtre filiale (intersecté avec le périmètre RBAC déjà appliqué).
        subsidiary = request.query_params.get("subsidiary")
        if subsidiary and subsidiary != "all":
            scoped = [r for r in scoped if r.subsidiary == subsidiary]

        entries = total_entries(scoped, period)
        exits = total_exits(scoped, period)
        metrics = {
            "payroll": (total_payroll_mass(scoped, period), "XOF", "currency"),
            "entries": (entries, "personnes", "int"),
            "exits": (exits, "personnes", "int"),
            "net": (entries - exits, "personnes", "int"),
        }
        values = {
            label: {"value": metrics[m][0], "unit": metrics[m][1], "format": metrics[m][2]}
            for label, m in binding.items()
            if m in metrics
        }
        series = [
            {
                "name": "Masse salariale par filiale",
                "type": "bar",
                "unit": "XOF",
                "points": [{"label": code, "value": amount} for code, amount in payroll_by_subsidiary(scoped, period).items()],
            }
        ]

        AccessLog.record(
            user=request.user,
            action="query_module",
            metric_key=key,
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter},
            ip=request.META.get("REMOTE_ADDR"),
        )

        return Response(
            {
                "key": key,
                "available": True,
                "source": HR_MART_SOURCE,
                "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
                "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
                "values": values,
                "series": series,
            }
        )


class HrScoreView(APIView):
    """Human Capital Score : global, dimensions, par filiale, tendance 12 mois.

    Lit `mart.hr_score`. Gouverné : si une dimension/filiale n'a pas de donnée → None (N/D).
    """

    def get(self, request):
        try:
            year = int(request.query_params.get("year", "2026"))
            quarter = int(request.query_params.get("quarter", "1"))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)

        period = period_from_quarter(year, quarter)
        scope = request.user.scope()
        sub_param = request.query_params.get("subsidiary")

        def allowed(code: str) -> bool:
            return scope.allows(code) and (not sub_param or sub_param == "all" or code == sub_param)

        rows = [r for r in get_mart_gateway().fetch_hr_score() if allowed(r[1])]
        dim_meta = [{"key": d.key, "label": d.label, "weight": d.weight} for d in HC_DIMENSIONS]
        global_score, dimensions, by_subsidiary, trend = aggregate_score(
            rows, period, dim_meta, human_capital_score
        )

        AccessLog.record(
            user=request.user,
            action="query_hr_score",
            ip=request.META.get("REMOTE_ADDR"),
            metric_key="hr.human_capital_score",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter},
        )
        return Response(
            {
                "available": global_score is not None,
                "global": global_score,
                "dimensions": dimensions,
                "by_subsidiary": by_subsidiary,
                "trend": trend,
                "period": {"start": period.start.isoformat(), "end": period.end.isoformat()},
                "scope": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
            }
        )


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
        try:
            year = int(request.query_params.get("year", "2026"))
            quarter = int(request.query_params.get("quarter", "1"))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quarter <= 4:
            return Response({"detail": "'quarter' doit être entre 1 et 4."}, status=status.HTTP_400_BAD_REQUEST)

        period = period_from_quarter(year, quarter)
        scope = request.user.scope()
        sub_param = request.query_params.get("subsidiary")

        def allowed(code: str) -> bool:
            return scope.allows(code) and (not sub_param or sub_param == "all" or code == sub_param)

        rows = [r for r in get_mart_gateway().fetch_domain_score(domain) if allowed(r[1])]
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
            ip=request.META.get("REMOTE_ADDR"),
            metric_key=f"{domain}.governance_score",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter, "domain": domain},
        )
        return Response(
            {
                "domain": domain,
                "label": framework.label,
                "available": global_score is not None,
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
        try:
            year = int(request.query_params.get("year", "2026"))
            quarter = int(request.query_params.get("quarter", "1"))
        except (TypeError, ValueError):
            return Response({"detail": "Paramètres 'year'/'quarter' invalides."}, status=status.HTTP_400_BAD_REQUEST)
        if not 1 <= quarter <= 4:
            return Response({"detail": "'quarter' doit être entre 1 et 4."}, status=status.HTTP_400_BAD_REQUEST)

        scope = request.user.scope()
        report = build_group_report(request.user, year, quarter, request.query_params.get("subsidiary"))
        AccessLog.record(
            user=request.user,
            action="query_group_score",
            ip=request.META.get("REMOTE_ADDR"),
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
            ip=request.META.get("REMOTE_ADDR"),
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
        try:
            year = int(request.query_params.get("year", "2026"))
            quarter = int(request.query_params.get("quarter", "1"))
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
            ip=request.META.get("REMOTE_ADDR"),
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
        if ext not in self._RENDERERS:
            return Response({"detail": "Format non supporté (xlsx, pdf)."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            year = int(request.query_params.get("year", "2026"))
            quarter = int(request.query_params.get("quarter", "1"))
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
            ip=request.META.get("REMOTE_ADDR"),
            metric_key="group.governance_index",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"year": year, "quarter": quarter, "format": ext},
        )
        resp = HttpResponse(payload, content_type=content_type)
        resp["Content-Disposition"] = f'attachment; filename="k-insight-gouvernance-{year}-T{quarter}.{ext}"'
        return resp
