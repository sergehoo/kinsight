from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from datetime import timedelta

from django.utils import timezone

from apps.audit.models import AccessLog

from .models import (
    ConnectorCredential,
    ConnectorEndpoint,
    DataConnector,
    DataSource,
    FieldMapping,
    SourceStatus,
    SyncError,
    SyncJob,
    SyncLog,
    SyncTrigger,
    WebhookEvent,
)
from .permissions import IsIntegrationAdmin
from .serializers import (
    ConnectorCredentialSerializer,
    ConnectorEndpointSerializer,
    DataConnectorSerializer,
    DataSourceListSerializer,
    DataSourceSerializer,
    FieldMappingSerializer,
    SyncErrorSerializer,
    SyncJobSerializer,
    SyncLogSerializer,
    WebhookEventSerializer,
)
from .services import run_sync, run_test
from .shield import (
    fetch_attendance_series,
    fetch_hr_kpis,
    fetch_overview_kpis,
    fetch_security_kpis,
    shield_health,
)
from .shield_rules import FENETRES_JOURS, MAX_JOURS

# Au-delà de ce délai sans test, une source « connectée » est considérée périmée.
STALE_AFTER_HOURS = 24


class ShieldHrKpiView(APIView):
    """KPIs RH normalisés depuis Kaydan Shield (backend → normalisation → API).

    React consomme UNIQUEMENT cet endpoint, jamais Shield en direct. Réponse gouvernée :
    status = connected | disconnected | error, chaque KPI portant son propre statut.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(fetch_hr_kpis())


class ShieldAttendanceSeriesView(APIView):
    """Série journalière de présence, sur une fenêtre glissante.

    Endpoint distinct de `hr-kpi/` à dessein : la série se construit par comptages
    journaliers (3 appels Shield par jour), elle ne doit pas alourdir le
    chargement des cartes KPI.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 30))
        except (TypeError, ValueError):
            days = 30
        if days not in FENETRES_JOURS:
            days = MAX_JOURS
        return Response(fetch_attendance_series(days))


class ShieldSecurityView(APIView):
    """Indicateurs Sécurité & Conformité issus de Kaydan Shield.

    Alimente le cockpit Risques. Comme pour les KPI RH, React ne voit jamais la
    forme d'une réponse Shield : tout est normalisé ici.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(fetch_security_kpis())


class ShieldOverviewView(APIView):
    """Agrégats Shield pour la vue Groupe : le pouls, pas le détail métier."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(fetch_overview_kpis())


class ShieldHealthView(APIView):
    """Santé du connecteur Shield, lisible par tout utilisateur authentifié.

    Volontairement distinct de `/integrations/sources/health/`, réservé aux
    administrateurs d'intégration : un décideur doit pouvoir savoir si la source
    qui alimente son tableau de bord répond, sans avoir accès au control-plane.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(shield_health())


def _audit(request, action_name: str, source: DataSource | None = None, payload=None):
    AccessLog.record(
        user=request.user,
        action=action_name,
        metric_key=source.slug if source else "",
        payload=payload or {},
        ip=request.META.get("REMOTE_ADDR"),
    )


class DataSourceViewSet(viewsets.ModelViewSet):
    queryset = DataSource.objects.all().select_related("connector")
    permission_classes = [IsAuthenticated, IsIntegrationAdmin]

    def get_serializer_class(self):
        return DataSourceListSerializer if self.action in {"list", "health"} else DataSourceSerializer

    def perform_create(self, serializer):
        source = serializer.save(created_by=self.request.user)
        DataConnector.objects.get_or_create(source=source)
        source.set_status(SourceStatus.CONFIGURED)
        _audit(self.request, "integration.source.create", source)

    def perform_update(self, serializer):
        source = serializer.save()
        _audit(self.request, "integration.source.update", source)

    def perform_destroy(self, instance):
        _audit(self.request, "integration.source.delete", instance)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        source = self.get_object()
        # La sonde réelle est le DÉFAUT : un test de connexion qui ne quitte pas
        # le processus ne teste rien. `?probe=0` reste disponible pour se limiter
        # à la validation de configuration, sans appel sortant.
        probe = request.query_params.get("probe") != "0"
        ok, message = run_test(source, probe=probe)
        _audit(request, "integration.source.test", source, {"ok": ok})
        connector = getattr(source, "connector", None)
        # La latence mesurée est renvoyée avec le verdict : l'assistant de création
        # affiche « connecté en 240 ms » sans avoir à relire la source ensuite.
        return Response(
            {
                "ok": ok,
                "message": message,
                "status": source.status,
                "latency_ms": connector.last_latency_ms if connector else None,
                "tested_at": connector.last_tested_at.isoformat() if connector and connector.last_tested_at else None,
            }
        )

    @action(detail=True, methods=["post"], url_path="sync-now")
    def sync_now(self, request, pk=None):
        source = self.get_object()
        job = run_sync(source, trigger=SyncTrigger.MANUAL)
        _audit(request, "integration.source.sync", source, {"job": str(job.id), "status": job.status})
        return Response(SyncJobSerializer(job).data, status=http_status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        source = self.get_object()
        source.is_active = not source.is_active
        source.status = SourceStatus.DISABLED if not source.is_active else SourceStatus.CONFIGURED
        source.save(update_fields=["is_active", "status", "updated_at"])
        _audit(request, "integration.source.toggle", source, {"is_active": source.is_active})
        return Response({"is_active": source.is_active, "status": source.status})

    @action(detail=False, methods=["get"])
    def health(self, request):
        """Santé consolidée du parc de connecteurs.

        `stale` mérite une explication : une source déclarée connectée mais dont
        le dernier test remonte à plus de 24 h n'est pas fiable pour autant. On
        la compte à part plutôt que de la présenter comme opérationnelle.
        """
        sources = list(self.get_queryset())
        now = timezone.now()
        seuil_stale = now - timedelta(hours=STALE_AFTER_HOURS)

        by_status: dict[str, int] = {}
        latences: list[int] = []
        derniere_sync = None
        stale = 0

        for source in sources:
            by_status[source.status] = by_status.get(source.status, 0) + 1
            connector = getattr(source, "connector", None)
            if connector is None:
                continue
            if connector.last_latency_ms is not None:
                latences.append(connector.last_latency_ms)
            if source.status == SourceStatus.CONNECTED and (
                connector.last_tested_at is None or connector.last_tested_at < seuil_stale
            ):
                stale += 1

        last_job = SyncJob.objects.order_by("-finished_at").first()
        if last_job and last_job.finished_at:
            derniere_sync = last_job.finished_at.isoformat()

        connected = by_status.get(SourceStatus.CONNECTED, 0)
        return Response(
            {
                "total": len(sources),
                "active": sum(1 for s in sources if s.is_active),
                "connected": connected,
                # `partial` : le parc est partiellement opérationnel dès qu'au moins
                # une source répond sans que toutes le fassent.
                "partial": 0 if connected in (0, len(sources)) else len(sources) - connected,
                "error": by_status.get(SourceStatus.ERROR, 0),
                "stale": stale,
                "disabled": by_status.get(SourceStatus.DISABLED, 0),
                "avg_latency_ms": round(sum(latences) / len(latences)) if latences else None,
                "last_sync": derniere_sync,
                "stale_after_hours": STALE_AFTER_HOURS,
                "by_status": by_status,
                "sources": DataSourceListSerializer(sources, many=True).data,
            }
        )


class DataConnectorViewSet(viewsets.ModelViewSet):
    queryset = DataConnector.objects.all()
    serializer_class = DataConnectorSerializer
    permission_classes = [IsAuthenticated, IsIntegrationAdmin]


class ConnectorEndpointViewSet(viewsets.ModelViewSet):
    serializer_class = ConnectorEndpointSerializer
    permission_classes = [IsAuthenticated, IsIntegrationAdmin]

    def get_queryset(self):
        qs = ConnectorEndpoint.objects.all()
        connector = self.request.query_params.get("connector")
        return qs.filter(connector_id=connector) if connector else qs


class ConnectorCredentialViewSet(viewsets.ModelViewSet):
    serializer_class = ConnectorCredentialSerializer
    permission_classes = [IsAuthenticated, IsIntegrationAdmin]

    def get_queryset(self):
        qs = ConnectorCredential.objects.all()
        connector = self.request.query_params.get("connector")
        return qs.filter(connector_id=connector) if connector else qs


class FieldMappingViewSet(viewsets.ModelViewSet):
    serializer_class = FieldMappingSerializer
    permission_classes = [IsAuthenticated, IsIntegrationAdmin]

    def get_queryset(self):
        qs = FieldMapping.objects.all()
        endpoint = self.request.query_params.get("endpoint")
        return qs.filter(endpoint_id=endpoint) if endpoint else qs


class _SourceScopedReadOnly(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated, IsIntegrationAdmin]
    model = None

    def get_queryset(self):
        qs = self.model.objects.all()
        source = self.request.query_params.get("source")
        return qs.filter(source_id=source) if source else qs


class SyncJobViewSet(_SourceScopedReadOnly):
    model = SyncJob
    serializer_class = SyncJobSerializer


class SyncLogViewSet(_SourceScopedReadOnly):
    model = SyncLog
    serializer_class = SyncLogSerializer


class SyncErrorViewSet(_SourceScopedReadOnly):
    model = SyncError
    serializer_class = SyncErrorSerializer


class WebhookEventViewSet(_SourceScopedReadOnly):
    model = WebhookEvent
    serializer_class = WebhookEventSerializer


class WebhookReceiver(APIView):
    """Réception des webhooks sources. Public mais signature vérifiée + journalisée."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request, slug):
        try:
            source = DataSource.objects.select_related("connector").get(slug=slug)
        except DataSource.DoesNotExist:
            return Response({"detail": "Source inconnue."}, status=http_status.HTTP_404_NOT_FOUND)

        connector = getattr(source, "connector", None)
        expected = (connector.config or {}).get("webhook_token") if connector else None
        provided = request.headers.get("X-Webhook-Token", "")
        signature_valid = bool(expected) and provided == expected

        WebhookEvent.objects.create(
            source=source,
            headers={"content-type": request.headers.get("Content-Type", ""), "user-agent": request.headers.get("User-Agent", "")},
            payload=request.data if isinstance(request.data, (dict, list)) else {},
            processed=False,
            signature_valid=signature_valid,
        )
        if not signature_valid and expected:
            return Response({"detail": "Signature invalide."}, status=http_status.HTTP_401_UNAUTHORIZED)
        return Response({"received": True}, status=http_status.HTTP_202_ACCEPTED)
