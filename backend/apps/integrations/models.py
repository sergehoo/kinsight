"""Control-plane d'intégration source-agnostic (ADR-0003/0004).

Une source externe se configure ENTIÈREMENT depuis l'API/admin (aucun code à changer).
Le flux de données reste : source → connecteur → Airbyte/ETL → EDW → Django → React.
Ces modèles décrivent la *configuration* et l'*état* des connecteurs, pas la donnée analytique.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from .encryption import decrypt, encrypt, mask


class SourceType(models.TextChoices):
    REST = "rest", "API REST"
    GRAPHQL = "graphql", "API GraphQL"
    WEBHOOK = "webhook", "Webhook"
    POSTGRES = "postgres", "PostgreSQL (lecture seule)"
    MYSQL = "mysql", "MySQL (lecture seule)"
    CSV = "csv", "Fichier CSV"
    EXCEL = "excel", "Excel"
    GSHEETS = "gsheets", "Google Sheets"
    AIRBYTE = "airbyte", "Connecteur Airbyte"
    KAYDAN_SHIELD = "kaydan_shield", "Kaydan Shield (contrôle d'accès / RH)"
    ODOO_HR = "odoo_hr", "Odoo RH"
    SAP = "sap", "SAP"
    EDW = "edw", "Entrepôt de données (mart)"


class TargetModule(models.TextChoices):
    RH = "rh", "Capital Humain"
    IMMOBILIER = "immobilier", "Immobilier"
    FINANCE = "finance", "Finance"
    STOCKS = "stocks", "Stocks & Logistique"
    FLOTTE = "flotte", "Flotte"
    SECURITE = "securite", "Sécurité"
    COMMERCIAL = "commercial", "Commercial & Clients"
    RISQUES = "risques", "Risques & Conformité"
    GROUPE = "groupe", "Groupe / Transverse"
    AUTRE = "autre", "Autre"


class Environment(models.TextChoices):
    """Environnement visé par une source. Distinguer production et recette évite
    qu'un connecteur de test alimente silencieusement un tableau de bord réel."""

    PRODUCTION = "production", "Production"
    STAGING = "staging", "Recette"
    SANDBOX = "sandbox", "Bac à sable"


class SourceStatus(models.TextChoices):
    NOT_CONFIGURED = "not_configured", "Non configurée"
    CONFIGURED = "configured", "Configurée"
    TESTING = "testing", "En test"
    CONNECTED = "connected", "Connectée"
    SYNCING = "syncing", "Synchronisation en cours"
    ERROR = "error", "Erreur"
    DISABLED = "disabled", "Désactivée"


class AuthMethod(models.TextChoices):
    NONE = "none", "Aucune"
    API_KEY = "api_key", "Clé API"
    BEARER = "bearer", "Bearer token"
    BASIC = "basic", "Basic auth"
    OAUTH2 = "oauth2", "OAuth2"
    HEADER = "header", "Header personnalisé"


class CredentialKind(models.TextChoices):
    API_TOKEN = "api_token", "Token API"
    API_KEY = "api_key", "Clé API"
    CLIENT_ID = "client_id", "Client ID"
    CLIENT_SECRET = "client_secret", "Client Secret"
    PASSWORD = "password", "Mot de passe"
    OAUTH_REFRESH = "oauth_refresh", "OAuth refresh token"


class SyncTrigger(models.TextChoices):
    MANUAL = "manual", "Manuelle"
    SCHEDULED = "scheduled", "Planifiée"
    WEBHOOK = "webhook", "Webhook"


class SyncStatus(models.TextChoices):
    QUEUED = "queued", "En file"
    RUNNING = "running", "En cours"
    SUCCESS = "success", "Succès"
    PARTIAL = "partial", "Partielle"
    ERROR = "error", "Erreur"


class LogLevel(models.TextChoices):
    INFO = "info", "Info"
    WARN = "warn", "Avertissement"
    ERROR = "error", "Erreur"


class TimestampedUUID(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DataSource(TimestampedUUID):
    """Une plateforme source (K-Shield, K-Express, CRM, Odoo…)."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    target_module = models.CharField(max_length=16, choices=TargetModule.choices, default=TargetModule.AUTRE)
    status = models.CharField(max_length=16, choices=SourceStatus.choices, default=SourceStatus.NOT_CONFIGURED)
    environment = models.CharField(max_length=12, choices=Environment.choices, default=Environment.PRODUCTION)
    is_active = models.BooleanField(default=True)
    demo_mode = models.BooleanField(
        default=False,
        help_text="Mode dégradé, désactivé par défaut : une source non connectée doit "
                  "afficher son état, jamais des données simulées.",
    )
    sync_frequency = models.CharField(max_length=64, blank=True, default="manual", help_text="cron ou 'manual'")
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["name"]
        verbose_name = "Source de données"
        verbose_name_plural = "Sources de données"

    def __str__(self) -> str:
        return f"{self.name} ({self.get_source_type_display()})"

    def set_status(self, status: str) -> None:
        self.status = status
        self.save(update_fields=["status", "updated_at"])


class DataConnector(TimestampedUUID):
    """Configuration de connexion d'une source (1-1)."""

    source = models.OneToOneField(DataSource, on_delete=models.CASCADE, related_name="connector")
    base_url = models.URLField(blank=True)
    auth_method = models.CharField(max_length=16, choices=AuthMethod.choices, default=AuthMethod.NONE)
    headers = models.JSONField(default=dict, blank=True, help_text="Headers HTTP personnalisés (non secrets).")
    config = models.JSONField(default=dict, blank=True, help_text="Config spécifique : host/port/dbname, file_path, sheet_id, airbyte_connection_id…")
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_ok = models.BooleanField(null=True)
    last_test_message = models.CharField(max_length=300, blank=True)
    # Latence du dernier test, en millisecondes. Une source qui répond en 4 s
    # n'est pas dans le même état qu'une source qui répond en 80 ms, même si les
    # deux sont « connectées ».
    last_latency_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Connecteur"
        verbose_name_plural = "Connecteurs"

    def __str__(self) -> str:
        return f"Connecteur {self.source.slug}"


class ConnectorEndpoint(TimestampedUUID):
    """Un point d'accès (endpoint REST, requête GraphQL, table, fichier…)."""

    connector = models.ForeignKey(DataConnector, on_delete=models.CASCADE, related_name="endpoints")
    name = models.CharField(max_length=120)
    path = models.CharField(max_length=500, blank=True, help_text="Chemin relatif / table / nom de feuille / requête.")
    http_method = models.CharField(max_length=8, default="GET")
    params = models.JSONField(default=dict, blank=True)
    incremental = models.BooleanField(default=False)
    cursor_field = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Endpoint"
        verbose_name_plural = "Endpoints"

    def __str__(self) -> str:
        return self.name


class ConnectorCredential(TimestampedUUID):
    """Secret chiffré at-rest. Jamais exposé en clair par l'API."""

    connector = models.ForeignKey(DataConnector, on_delete=models.CASCADE, related_name="credentials")
    kind = models.CharField(max_length=20, choices=CredentialKind.choices)
    label = models.CharField(max_length=120, blank=True)
    secret_ciphertext = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Identifiant chiffré"
        verbose_name_plural = "Identifiants chiffrés"
        # Un connecteur n'a qu'UN secret par type. Sans cette contrainte, la règle
        # posée dans le sérialiseur se contournerait par l'admin, une commande ou
        # un futur endpoint — et l'empilement recommencerait.
        constraints = [
            models.UniqueConstraint(fields=["connector", "kind"], name="uniq_connector_kind")
        ]

    def set_secret(self, value: str) -> None:
        self.secret_ciphertext = encrypt(value)

    @property
    def secret(self) -> str:
        return decrypt(self.secret_ciphertext)

    @property
    def is_set(self) -> bool:
        return bool(self.secret_ciphertext)

    @property
    def masked(self) -> str:
        return mask(self.secret) if self.secret_ciphertext else ""

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.connector.source.slug})"


class FieldMapping(TimestampedUUID):
    """Correspondance champ source → champ cible (vers le mart)."""

    endpoint = models.ForeignKey(ConnectorEndpoint, on_delete=models.CASCADE, related_name="mappings")
    source_field = models.CharField(max_length=200)
    target_field = models.CharField(max_length=200)
    target_table = models.CharField(max_length=200, blank=True)
    transform = models.CharField(max_length=200, blank=True, help_text="Transformation optionnelle (ex. to_int, trim, date).")
    is_key = models.BooleanField(default=False)

    class Meta:
        ordering = ["source_field"]
        verbose_name = "Correspondance de champs"
        verbose_name_plural = "Correspondances de champs"


class SyncJob(TimestampedUUID):
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="jobs")
    trigger = models.CharField(max_length=12, choices=SyncTrigger.choices, default=SyncTrigger.MANUAL)
    status = models.CharField(max_length=12, choices=SyncStatus.choices, default=SyncStatus.QUEUED)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    rows_ingested = models.PositiveIntegerField(default=0)
    incremental = models.BooleanField(default=False)
    cursor_value = models.CharField(max_length=200, blank=True)
    message = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Synchronisation"
        verbose_name_plural = "Synchronisations"


class SyncLog(TimestampedUUID):
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="logs")
    job = models.ForeignKey(SyncJob, null=True, blank=True, on_delete=models.CASCADE, related_name="logs")
    level = models.CharField(max_length=8, choices=LogLevel.choices, default=LogLevel.INFO)
    message = models.TextField()
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Journal de synchronisation"
        verbose_name_plural = "Journaux de synchronisation"


class SyncError(TimestampedUUID):
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="errors")
    job = models.ForeignKey(SyncJob, null=True, blank=True, on_delete=models.CASCADE, related_name="errors")
    code = models.CharField(max_length=64, blank=True)
    message = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Erreur de synchronisation"
        verbose_name_plural = "Erreurs de synchronisation"


class Person(TimestampedUUID):
    """Personne réelle (référentiel identité transverse).

    Squelette volontairement minimal : on ne réconcilie pas encore les IDs des
    différentes sources (Shield, Odoo à venir). Une `Person` agrège une ou plusieurs
    `ExternalIdentity`. On ne couple JAMAIS en dur avec de futurs IDs Odoo.
    """

    class Kind(models.TextChoices):
        EMPLOYEE = "employee", "Employé"
        WORKER = "worker", "Ouvrier"
        OTHER = "other", "Autre"

    display_name = models.CharField(max_length=200, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.OTHER)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_name"]
        verbose_name = "Personne"
        verbose_name_plural = "Personnes"

    def __str__(self) -> str:
        return self.display_name or f"Person {self.pk}"


class ExternalIdentity(TimestampedUUID):
    """Lien 1 personne ↔ 1 identifiant dans une source externe.

    `source` = code de la plateforme (ex. 'kaydan_shield', 'odoo_hr').
    `external_id` = identifiant natif dans cette source. Unicité (source, external_id).
    """

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="identities")
    source = models.CharField(max_length=32, help_text="Code source, ex. 'kaydan_shield'.")
    external_id = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True, help_text="Snapshot brut non normalisé (audit).")

    class Meta:
        ordering = ["source", "external_id"]
        constraints = [models.UniqueConstraint(fields=["source", "external_id"], name="uniq_source_external_id")]
        verbose_name = "Identité externe"
        verbose_name_plural = "Identités externes"

    def __str__(self) -> str:
        return f"{self.source}:{self.external_id}"


class WebhookEvent(TimestampedUUID):
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="webhook_events")
    received_at = models.DateTimeField(auto_now_add=True)
    headers = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False)
    signature_valid = models.BooleanField(default=False)

    class Meta:
        ordering = ["-received_at"]
        verbose_name = "Événement webhook"
        verbose_name_plural = "Événements webhook"
