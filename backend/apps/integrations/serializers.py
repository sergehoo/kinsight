from rest_framework import serializers

from .models import (
    ConnectorCredential,
    ConnectorEndpoint,
    DataConnector,
    DataSource,
    FieldMapping,
    SyncError,
    SyncJob,
    SyncLog,
    WebhookEvent,
)


class ConnectorCredentialSerializer(serializers.ModelSerializer):
    # Secret : ÉCRITURE seule. La lecture ne renvoie jamais le clair (is_set + masked).
    secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    is_set = serializers.BooleanField(read_only=True)
    masked = serializers.CharField(read_only=True)

    class Meta:
        model = ConnectorCredential
        fields = ["id", "connector", "kind", "label", "secret", "is_set", "masked", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated):
        secret = validated.pop("secret", "")
        cred = ConnectorCredential(**validated)
        cred.set_secret(secret)
        cred.save()
        return cred

    def update(self, instance, validated):
        secret = validated.pop("secret", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if secret:
            instance.set_secret(secret)
        instance.save()
        return instance


class FieldMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldMapping
        fields = ["id", "endpoint", "source_field", "target_field", "target_table", "transform", "is_key"]
        read_only_fields = ["id"]


class ConnectorEndpointSerializer(serializers.ModelSerializer):
    mappings = FieldMappingSerializer(many=True, read_only=True)

    class Meta:
        model = ConnectorEndpoint
        fields = ["id", "connector", "name", "path", "http_method", "params", "incremental", "cursor_field", "is_active", "mappings"]
        read_only_fields = ["id"]


class DataConnectorSerializer(serializers.ModelSerializer):
    endpoints = ConnectorEndpointSerializer(many=True, read_only=True)
    credentials = ConnectorCredentialSerializer(many=True, read_only=True)

    class Meta:
        model = DataConnector
        fields = [
            "id", "source", "base_url", "auth_method", "headers", "config",
            "last_tested_at", "last_test_ok", "last_test_message", "endpoints", "credentials",
        ]
        read_only_fields = ["id", "last_tested_at", "last_test_ok", "last_test_message"]


class DataSourceSerializer(serializers.ModelSerializer):
    connector = DataConnectorSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source_type_label = serializers.CharField(source="get_source_type_display", read_only=True)
    target_module_label = serializers.CharField(source="get_target_module_display", read_only=True)
    jobs_count = serializers.SerializerMethodField()
    errors_count = serializers.SerializerMethodField()

    class Meta:
        model = DataSource
        fields = [
            "id", "name", "slug", "source_type", "source_type_label", "target_module", "target_module_label",
            "status", "status_label", "is_active", "demo_mode", "sync_frequency", "description",
            "connector", "jobs_count", "errors_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]

    def get_jobs_count(self, obj):
        return obj.jobs.count()

    def get_errors_count(self, obj):
        return obj.errors.filter(resolved=False).count()


class DataSourceListSerializer(serializers.ModelSerializer):
    """Version allégée pour la liste / santé."""

    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source_type_label = serializers.CharField(source="get_source_type_display", read_only=True)
    target_module_label = serializers.CharField(source="get_target_module_display", read_only=True)
    environment_label = serializers.CharField(source="get_environment_display", read_only=True)
    # Champs du connecteur remontés à plat : la carte a besoin de l'état de la
    # connexion, pas de la structure interne du modèle.
    base_url = serializers.CharField(source="connector.base_url", read_only=True, default="")
    last_tested_at = serializers.DateTimeField(source="connector.last_tested_at", read_only=True, default=None)
    last_test_ok = serializers.BooleanField(source="connector.last_test_ok", read_only=True, default=None)
    last_test_message = serializers.CharField(source="connector.last_test_message", read_only=True, default="")
    last_latency_ms = serializers.IntegerField(source="connector.last_latency_ms", read_only=True, default=None)
    last_sync_at = serializers.SerializerMethodField()
    recent_errors = serializers.SerializerMethodField()

    def get_last_sync_at(self, obj):
        """Fin de la dernière synchronisation réellement terminée."""
        job = obj.jobs.filter(finished_at__isnull=False).order_by("-finished_at").first()
        return job.finished_at.isoformat() if job else None

    def get_recent_errors(self, obj):
        """Erreurs non résolues les plus récentes. Le message vient du connecteur,
        jamais d'un secret : `SyncError.message` est écrit par nos soins."""
        return [
            {"code": e.code, "message": e.message[:200], "at": e.created_at.isoformat()}
            for e in obj.errors.filter(resolved=False).order_by("-created_at")[:3]
        ]

    class Meta:
        model = DataSource
        fields = ["id", "name", "slug", "source_type", "source_type_label", "target_module",
            "target_module_label", "status", "status_label", "environment",
            "environment_label", "is_active", "demo_mode", "sync_frequency",
            "base_url", "last_tested_at", "last_test_ok", "last_test_message",
            "last_latency_ms", "last_sync_at", "recent_errors", "updated_at"]


class SyncJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncJob
        fields = ["id", "source", "trigger", "status", "started_at", "finished_at", "rows_ingested", "incremental", "cursor_value", "message", "created_at"]


class SyncLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncLog
        fields = ["id", "source", "job", "level", "message", "context", "created_at"]


class SyncErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncError
        fields = ["id", "source", "job", "code", "message", "payload", "resolved", "created_at"]


class WebhookEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEvent
        fields = ["id", "source", "received_at", "processed", "signature_valid"]
