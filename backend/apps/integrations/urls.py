from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ConnectorCredentialViewSet,
    ConnectorEndpointViewSet,
    DataConnectorViewSet,
    DataSourceViewSet,
    FieldMappingViewSet,
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
    path("webhook/<slug:slug>/", WebhookReceiver.as_view(), name="integration-webhook"),
]
