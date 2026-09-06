from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ConnectorCredentialViewSet,
    ConnectorEndpointViewSet,
    DataConnectorViewSet,
    DataSourceViewSet,
    FieldMappingViewSet,
    ShieldAttendanceSeriesView,
    ShieldHealthView,
    ShieldHrKpiView,
    ShieldOverviewView,
    ShieldSecurityView,
    SyncErrorViewSet,
    SyncJobViewSet,
    SyncLogViewSet,
    WebhookEventViewSet,
    WebhookReceiver,
)

router = DefaultRouter()
router.register("sources", DataSourceViewSet, basename="datasource")
router.register("connectors", DataConnectorViewSet, basename="dataconnector")
router.register("endpoints", ConnectorEndpointViewSet, basename="endpoint")
router.register("credentials", ConnectorCredentialViewSet, basename="credential")
router.register("mappings", FieldMappingViewSet, basename="mapping")
router.register("jobs", SyncJobViewSet, basename="syncjob")
router.register("logs", SyncLogViewSet, basename="synclog")
router.register("errors", SyncErrorViewSet, basename="syncerror")
router.register("webhook-events", WebhookEventViewSet, basename="webhookevent")

urlpatterns = router.urls + [
    path("shield/hr-kpi/", ShieldHrKpiView.as_view(), name="shield-hr-kpi"),
    path("shield/attendance-series/", ShieldAttendanceSeriesView.as_view(), name="shield-attendance-series"),
    path("shield/security/", ShieldSecurityView.as_view(), name="shield-security"),
    path("shield/overview/", ShieldOverviewView.as_view(), name="shield-overview"),
    path("shield/health/", ShieldHealthView.as_view(), name="shield-health"),
    path("webhook/<slug:slug>/", WebhookReceiver.as_view(), name="integration-webhook"),
]
