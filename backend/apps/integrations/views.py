from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
        probe = request.query_params.get("probe") == "1" or bool(getattr(request, "data", {}).get("probe"))
        ok, message = run_test(source, probe=probe)
        _audit(request, "integration.source.test", source, {"ok": ok})
        return Response({"ok": ok, "message": message, "status": source.status})

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
        sources = self.get_queryset()
        by_status: dict[str, int] = {}
        for s in sources:
            by_status[s.status] = by_status.get(s.status, 0) + 1
        return Response(
            {
                "total": sources.count(),
                "active": sources.filter(is_active=True).count(),
                "connected": sources.filter(status=SourceStatus.CONNECTED).count(),
                "error": sources.filter(status=SourceStatus.ERROR).count(),
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
