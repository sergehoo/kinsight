"""API governance (DRF). Lecture seule, filtrée par périmètre, journalisée."""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from k_insight.semantic import CATALOG

from apps.accounts.rbac import can_access_domain
from apps.audit.models import AccessLog


def _forbidden(domain: str) -> Response:
    return Response(
        {"detail": f"Accès au domaine « {domain} » non autorisé pour votre rôle."},
        status=status.HTTP_403_FORBIDDEN,
    )

from .gateway import fetch_or_unavailable, get_mart_gateway
from .services import blank_hr_summary, governance_overview, hr_kpi_summary, period_from_quarter


class CatalogView(APIView):
    """Catalogue des métriques (source de vérité pour le frontend et l'IA, ADR-0007)."""

    def get(self, request):
        domain = request.query_params.get("domain")
        metrics = CATALOG.by_domain(domain) if domain else CATALOG.all()
        data = [
            {
                "key": m.key,
                "domain": m.domain,
                "label": m.label,
                "unit": m.unit,
                "grain": m.grain,
                "direction": m.direction.value,
                "description": m.description,
                "mart": m.mart,
                "dimensions": list(m.dimensions),
            }
            for m in metrics
        ]
        scope = request.user.scope()
        AccessLog.record(
            user=request.user,
            action="view_catalog",
            metric_key=f"catalog:{domain}" if domain else "catalog",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"domain": domain, "count": len(data)},
            ip=request.META.get("REMOTE_ADDR"),
        )
        return Response({"count": len(data), "metrics": data})


class HrKpiView(APIView):
    """Synthèse RH (filiale × période), filtrée par le périmètre de l'utilisateur."""

    def get(self, request):
        if not can_access_domain(request.user, "capital-humain"):
            return _forbidden("capital-humain")
        try:
            year = int(request.query_params["year"])
            quarter = int(request.query_params["quarter"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "Paramètres requis : 'year' et 'quarter' (entiers)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= quarter <= 4:
            return Response(
                {"detail": "'quarter' doit être compris entre 1 et 4."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = period_from_quarter(year, quarter)
        scope = request.user.scope()
        rows, mart_ok = fetch_or_unavailable(lambda: get_mart_gateway().fetch_hr_kpi(), [])
        summary = hr_kpi_summary(rows, scope, period)
        if not mart_ok or not rows:
            summary = blank_hr_summary(summary, source_state="error" if not mart_ok else "connected")
        else:
            summary["available"] = True
            summary["source_state"] = "connected"

        AccessLog.record(
            user=request.user,
            action="query_metric",
            metric_key="hr.*",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"period": summary["period"]},
            ip=request.META.get("REMOTE_ADDR"),
        )
        return Response(summary)


class GovernanceOverviewView(APIView):
    """Vue agrégée consommée par le dashboard React."""

    def get(self, request):
        if not can_access_domain(request.user, "overview"):
            return _forbidden("overview")
        try:
            year = int(request.query_params["year"])
            quarter = int(request.query_params["quarter"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "Paramètres requis : 'year' et 'quarter' (entiers)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 1 <= quarter <= 4:
            return Response(
                {"detail": "'quarter' doit être compris entre 1 et 4."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        period = period_from_quarter(year, quarter)
        scope = request.user.scope()
        hr_summary = None
        hr_error = ""
        try:
            rows = get_mart_gateway().fetch_hr_kpi()
            hr_summary = hr_kpi_summary(rows, scope, period)
        except Exception:
            hr_error = "mart.hr_kpi indisponible"

        payload = governance_overview(
            year=year,
            quarter=quarter,
            scope=scope,
            hr_summary=hr_summary,
            hr_error=hr_error,
        )
        AccessLog.record(
            user=request.user,
            action="view_dashboard",
            metric_key="governance.overview",
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"period": payload["period"]},
            ip=request.META.get("REMOTE_ADDR"),
        )
        return Response(payload)
