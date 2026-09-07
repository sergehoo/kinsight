"""Administration du control-plane d'intégration.

Trois familles d'objets, trois traitements différents — et c'est la distinction qui
compte ici :

  Configuration (sources, connecteurs, endpoints, mappings, personnes) : modifiable.
  Secrets (identifiants chiffrés) : consultables sous forme masquée, jamais
    modifiables. Un formulaire d'admin écrirait la saisie TELLE QUELLE dans
    `secret_ciphertext`, alors que ce champ n'accepte que du chiffré produit par
    `set_secret()`. On obtiendrait un secret en clair dans une colonne censée être
    chiffrée, et un connecteur qui échoue à l'authentification sans dire pourquoi.
  Traces (jobs, logs, erreurs, webhooks) : lecture seule. Les retoucher reviendrait
    à réécrire l'historique d'exécution.

Aucune action déclenchant un appel réseau sortant n'est exposée ici, volontairement.
Le test de connexion vit dans l'API et dans la fiche source du frontend, où il est
borné à un essai ; une action d'admin appliquée à une sélection de lignes
immobiliserait plusieurs workers gunicorn pendant des dizaines de secondes.
"""

from django.contrib import admin

from .models import (
    ConnectorCredential,
    ConnectorEndpoint,
    DataConnector,
    DataSource,
    ExternalIdentity,
    FieldMapping,
    Person,
    SyncError,
    SyncJob,
    SyncLog,
    WebhookEvent,
)

HORODATAGES = ("created_at", "updated_at")


class TraceAdmin(admin.ModelAdmin):
    """Socle des tables produites par le système : consultation seule.

    `created_at` et `updated_at` sont `auto_now_add`/`auto_now`, donc non éditables :
    Django refuse de les placer dans un formulaire s'ils ne sont pas déclarés en
    lecture seule (admin.E013).
    """

    show_full_result_count = False
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ── Configuration ────────────────────────────────────────────────────────────


class ConnecteurInline(admin.StackedInline):
    model = DataConnector
    can_delete = False
    extra = 0
    # Ces champs sont écrits par le test de connexion : les rendre saisissables
    # permettrait d'afficher « connectée » sur une source qui n'a jamais répondu.
    readonly_fields = ("last_tested_at", "last_test_ok", "last_test_message",
                       "last_latency_ms", *HORODATAGES)
    fields = ("base_url", "auth_method", "headers", "config",
              "last_tested_at", "last_test_ok", "last_test_message", "last_latency_ms")
    verbose_name = "Connecteur"
    verbose_name_plural = "Connecteur"


@admin.register(DataSource)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "source_type", "target_module", "environment",
                    "status", "is_active", "demo_mode", "updated_at")
    # `demo_mode` en filtre n'est pas cosmétique : il répond à « quelles sources
    # affichent aujourd'hui des données simulées ? », qui doit rester à un clic.
    list_filter = ("source_type", "target_module", "environment", "status",
                   "is_active", "demo_mode")
    search_fields = ("name", "slug", "description")
    ordering = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("created_by",)
    # Le statut est posé par `set_status()` au fil des tests et des synchronisations.
    readonly_fields = ("status", "created_by", *HORODATAGES)
    inlines = (ConnecteurInline,)

    def get_actions(self, request):
        """Retire la suppression en masse : elle ne consulte pas le contrôle par
        objet ci-dessous et emporterait l'historique sans le moindre avertissement."""
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def has_delete_permission(self, request, obj=None):
        """Une source ne se supprime que si elle n'a produit aucune trace.

        `on_delete=CASCADE` relie à cette table les jobs, journaux, erreurs et
        événements webhook : supprimer une source effacerait donc précisément
        l'historique que cet admin protège ligne à ligne. Retirer une source
        d'exploitation se fait en la DÉSACTIVANT (`is_active`), ce qui conserve
        la trace de ce qu'elle a fait. La suppression reste ouverte pour une
        source créée par erreur, qui n'a rien produit.
        """
        if obj is None:
            return True
        return not (obj.jobs.exists() or obj.logs.exists()
                    or obj.errors.exists() or obj.webhook_events.exists())

    def get_prepopulated_fields(self, request, obj=None):
        """Le code n'est proposé qu'à la CRÉATION.

        `prepopulated_fields` s'applique aussi au formulaire de modification :
        renommer une source régénérerait son code en silence. Or ce code est la
        clé de corrélation des traces d'audit (`metric_key=source.slug`) et c'est
        par lui que le connecteur Shield retrouve sa source — le réécrire couperait
        l'historique en deux et débrancherait le connecteur.
        """
        return {} if obj else {"slug": ("name",)}

    def save_model(self, request, obj, form, change):
        # `created_by` est une donnée observée : on la renseigne, on ne la saisit pas.
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    fieldsets = (
        ("Identité", {"fields": ("name", "slug", "source_type", "target_module", "environment")}),
        ("Exploitation", {"fields": ("status", "is_active", "sync_frequency", "demo_mode"),
                          "description": "Le statut est calculé par les tests de connexion, il ne se saisit pas."}),
        ("Contexte", {"fields": ("description", "created_by", *HORODATAGES)}),
    )


class EndpointInline(admin.TabularInline):
    model = ConnectorEndpoint
    extra = 0
    fields = ("name", "path", "http_method", "incremental", "cursor_field", "is_active")


class IdentifiantInline(admin.TabularInline):
    """Identifiants du connecteur, en consultation masquée uniquement.

    Ni ajout ni modification : `max_num=0` retire le formulaire vierge, et le
    contenu affiché passe par `masked`, jamais par le champ chiffré.
    """

    model = ConnectorCredential
    extra = 0
    max_num = 0
    can_delete = False
    fields = ("kind", "label", "secret_masque")
    readonly_fields = ("kind", "label", "secret_masque")
    verbose_name = "Identifiant chiffré"
    verbose_name_plural = "Identifiants chiffrés"

    # Les surcharges de permission du ModelAdmin parent ne descendent PAS sur ses
    # inlines : sans ces trois méthodes, la fermeture posée sur ConnectorCredential
    # serait contournable depuis la fiche du connecteur. Noter la signature d'un
    # inline : `has_add_permission(self, request, obj)`, avec `obj`.
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Secret")
    def secret_masque(self, obj):
        return _masque(obj)


@admin.register(DataConnector)
class ConnecteurAdmin(admin.ModelAdmin):
    list_display = ("source", "base_url", "auth_method", "last_test_ok",
                    "last_latency_ms", "last_tested_at")
    list_filter = ("auth_method", "last_test_ok")
    search_fields = ("source__name", "source__slug", "base_url")
    ordering = ("source__name",)
    list_select_related = ("source",)
    autocomplete_fields = ("source",)
    readonly_fields = ("last_tested_at", "last_test_ok", "last_test_message",
                       "last_latency_ms", *HORODATAGES)
    inlines = (EndpointInline, IdentifiantInline)

    def has_delete_permission(self, request, obj=None):
        """Le connecteur est créé d'office avec sa source et l'interface le suppose
        présent. Le supprimer laisserait une source impossible à configurer, et
        emporterait au passage ses endpoints, ses mappings et ses secrets."""
        return False


class MappingInline(admin.TabularInline):
    model = FieldMapping
    extra = 0
    fields = ("source_field", "target_field", "target_table", "transform", "is_key")


@admin.register(ConnectorEndpoint)
class EndpointAdmin(admin.ModelAdmin):
    list_display = ("name", "connector", "path", "http_method", "incremental", "is_active")
    list_filter = ("http_method", "incremental", "is_active")
    search_fields = ("name", "path", "connector__source__name", "connector__source__slug")
    ordering = ("connector__source__name", "name")
    list_select_related = ("connector", "connector__source")
    autocomplete_fields = ("connector",)
    readonly_fields = HORODATAGES
    inlines = (MappingInline,)


@admin.register(FieldMapping)
class MappingAdmin(admin.ModelAdmin):
    list_display = ("endpoint", "source_field", "target_field", "target_table", "is_key")
    list_filter = ("is_key",)
    search_fields = ("source_field", "target_field", "target_table", "endpoint__name")
    ordering = ("endpoint__name", "source_field")
    list_select_related = ("endpoint",)
    autocomplete_fields = ("endpoint",)
    readonly_fields = HORODATAGES


def _masque(obj) -> str:
    """Masque du secret, ou la raison de son absence.

    `masked` déchiffre pour ne montrer que les derniers caractères. Si la clé de
    chiffrement a changé depuis le dépôt, le déchiffrement échoue : mieux vaut le
    dire ici qu'afficher une page d'erreur 500 à l'administrateur.
    """
    if not obj.secret_ciphertext:
        return "— non défini —"
    try:
        return obj.masked or "— non défini —"
    except Exception:  # noqa: BLE001 — clé changée, chiffré corrompu…
        return "— illisible : la clé de chiffrement ne correspond plus —"


@admin.register(ConnectorCredential)
class IdentifiantAdmin(admin.ModelAdmin):
    """Consultation et révocation. Le dépôt d'un secret passe par l'API, qui chiffre.

    La suppression reste permise : révoquer un identifiant compromis est un geste
    d'administration légitime, et il n'efface aucune trace — les journaux de
    synchronisation, eux, restent intacts.
    """

    # `secret_masque` est délibérément ABSENT de la liste : `masked` déchiffre, et
    # une colonne le ferait une fois par ligne — soit une centaine de dérivations de
    # clé par page, rechargeables à volonté. `secret_defini` lit un booléen sans
    # déchiffrer ; le masque reste sur la fiche, où il n'y a qu'une ligne.
    list_display = ("connector", "kind", "label", "secret_defini", "created_at")
    list_filter = ("kind",)
    search_fields = ("label", "connector__source__name", "connector__source__slug")
    ordering = ("connector__source__name", "kind")
    list_select_related = ("connector", "connector__source")
    # `secret_ciphertext` n'apparaît nulle part : ni en liste, ni en formulaire, ni
    # en lecture seule. Un chiffré affiché n'est pas un clair, mais il n'apporte
    # rien et élargit la surface exposée.
    exclude = ("secret_ciphertext",)
    readonly_fields = ("connector", "kind", "label", "secret_defini", "secret_masque", *HORODATAGES)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Défini", boolean=True)
    def secret_defini(self, obj):
        return obj.is_set

    @admin.display(description="Secret")
    def secret_masque(self, obj):
        return _masque(obj)


@admin.register(Person)
class PersonneAdmin(admin.ModelAdmin):
    list_display = ("display_name", "kind", "is_active", "nombre_identites", "updated_at")
    list_filter = ("kind", "is_active")
    search_fields = ("display_name",)
    ordering = ("display_name",)
    readonly_fields = HORODATAGES

    def get_queryset(self, request):
        from django.db.models import Count

        return super().get_queryset(request).annotate(_identites=Count("identities"))

    @admin.display(description="Identités externes", ordering="_identites")
    def nombre_identites(self, obj):
        return obj._identites


@admin.register(ExternalIdentity)
class IdentiteExterneAdmin(admin.ModelAdmin):
    list_display = ("source", "external_id", "person", "instantane_present")
    list_filter = ("source",)
    search_fields = ("external_id", "person__display_name")
    ordering = ("source", "external_id")
    list_select_related = ("person",)
    autocomplete_fields = ("person",)
    readonly_fields = HORODATAGES
    # `payload` est un instantané brut de la source : il peut porter des données
    # nominatives. Consultable dans le détail, jamais étalé en liste.

    @admin.display(description="Instantané", boolean=True)
    def instantane_present(self, obj):
        return bool(obj.payload)


# ── Traces d'exécution ───────────────────────────────────────────────────────


@admin.register(SyncJob)
class JobAdmin(TraceAdmin):
    list_display = ("created_at", "source", "trigger", "status", "rows_ingested",
                    "incremental", "finished_at")
    list_filter = ("status", "trigger", "incremental")
    search_fields = ("source__name", "source__slug", "message")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("source",)
    readonly_fields = ("source", "trigger", "status", "started_at", "finished_at",
                       "rows_ingested", "incremental", "cursor_value", "message", *HORODATAGES)


@admin.register(SyncLog)
class LogAdmin(TraceAdmin):
    list_display = ("created_at", "source", "level", "extrait")
    list_filter = ("level",)
    search_fields = ("message", "source__name", "source__slug")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("source", "job")
    readonly_fields = ("source", "job", "level", "message", "context", *HORODATAGES)

    @admin.display(description="Message")
    def extrait(self, obj):
        """Un message de log peut faire plusieurs lignes : la liste n'en montre que
        le début, le détail porte le texte entier."""
        texte = (obj.message or "").replace("\n", " ")
        return texte if len(texte) <= 120 else texte[:117] + "…"


@admin.register(SyncError)
class ErreurAdmin(TraceAdmin):
    """Lecture seule, à une exception près : `resolved`.

    Marquer une erreur comme traitée est un acte d'administration, pas une
    falsification. On ouvre donc la modification pour ce seul champ, tout le reste
    du constat restant figé.
    """

    list_display = ("created_at", "source", "code", "extrait", "resolved")
    list_filter = ("resolved", "code")
    search_fields = ("code", "message", "source__name", "source__slug")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("source", "job")
    list_editable = ("resolved",)
    fields = ("source", "job", "code", "message", "payload", "resolved", *HORODATAGES)
    readonly_fields = ("source", "job", "code", "message", "payload", *HORODATAGES)
    actions = ("marquer_traitees", "marquer_non_traitees")

    def has_change_permission(self, request, obj=None):
        return True

    @admin.display(description="Message")
    def extrait(self, obj):
        texte = (obj.message or "").replace("\n", " ")
        return texte if len(texte) <= 100 else texte[:97] + "…"

    @admin.action(description="Marquer comme traitées")
    def marquer_traitees(self, request, queryset):
        n = queryset.update(resolved=True)
        self.message_user(request, f"{n} erreur(s) marquée(s) comme traitée(s).")

    @admin.action(description="Marquer comme non traitées")
    def marquer_non_traitees(self, request, queryset):
        n = queryset.update(resolved=False)
        self.message_user(request, f"{n} erreur(s) remise(s) en attente.")


@admin.register(WebhookEvent)
class WebhookAdmin(TraceAdmin):
    list_display = ("received_at", "source", "signature_valid", "processed", "charge_presente")
    list_filter = ("signature_valid", "processed")
    search_fields = ("source__name", "source__slug")
    date_hierarchy = "received_at"
    ordering = ("-received_at",)
    list_select_related = ("source",)
    # `payload` et `headers` viennent de l'extérieur et peuvent porter n'importe
    # quoi, données nominatives comprises : consultables dans le détail, jamais
    # déroulés dans un tableau.
    readonly_fields = ("source", "received_at", "headers", "payload", "processed",
                       "signature_valid", *HORODATAGES)

    @admin.display(description="Charge reçue", boolean=True)
    def charge_presente(self, obj):
        return bool(obj.payload)
