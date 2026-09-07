"""Administration du Copilot IA.

Aucune clé d'API ne vit dans ces modèles : `AIProvider` ne porte qu'une URL et un
nom de modèle, le secret venant de l'environnement. Il n'y a donc rien à masquer ici
— la vigilance porte ailleurs, sur deux points.

Le premier est le CIRCUIT D'APPROBATION. `AIActionRequest` n'exécute rien avant
d'avoir réuni `required_confirmations` décisions enregistrées dans
`AIActionApproval`. Laisser un administrateur basculer `status` à « approuvée »
depuis un formulaire contournerait ce circuit sans laisser la moindre trace de qui
a approuvé quoi. Le statut et le résultat sont donc en lecture seule, et les
décisions elles-mêmes ne se saisissent pas ici.

Le second est le CONTENU. Messages, arguments d'outils et résultats portent des
données métier. On en montre un aperçu court en liste, jamais le corps entier.
"""

from django.contrib import admin

from .models import (
    AIActionApproval,
    AIActionRequest,
    AIAuditLog,
    AIAutomation,
    AIConversation,
    AIMessage,
    AIProvider,
    AITool,
    AIToolExecution,
)


def _apercu(texte: str, limite: int = 110) -> str:
    """Début d'un texte long, sur une seule ligne."""
    plat = (texte or "").replace("\n", " ").strip()
    if not plat:
        return "—"
    return plat if len(plat) <= limite else plat[: limite - 1] + "…"


class TraceAdmin(admin.ModelAdmin):
    """Socle des tables produites par le système : consultation seule."""

    show_full_result_count = False
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ── Configuration ────────────────────────────────────────────────────────────


@admin.register(AIProvider)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "model_name", "priority", "enabled")
    list_filter = ("kind", "enabled")
    search_fields = ("name", "model_name", "base_url")
    ordering = ("priority", "name")
    list_editable = ("priority", "enabled")


@admin.register(AITool)
class OutilAdmin(admin.ModelAdmin):
    list_display = ("name", "mode", "sensitive", "required_role", "enabled")
    # `sensitive` en filtre répond à « quels outils exigent une approbation ? »,
    # qui est la question de gouvernance de cette table.
    list_filter = ("mode", "sensitive", "enabled")
    search_fields = ("name", "description", "required_role")
    ordering = ("name",)
    list_editable = ("enabled",)


@admin.register(AIAutomation)
class AutomatisationAdmin(admin.ModelAdmin):
    list_display = ("name", "tool_name", "interval_minutes", "enabled",
                    "last_run_at", "created_by")
    list_filter = ("enabled", "tool_name")
    search_fields = ("name", "tool_name")
    ordering = ("name",)
    list_select_related = ("created_by",)
    autocomplete_fields = ("created_by",)
    # `last_run_at` est posé par l'ordonnanceur : le saisir à la main ferait sauter
    # ou rejouer une exécution.
    readonly_fields = ("last_run_at", "created_at")


# ── Conversations ────────────────────────────────────────────────────────────


class MessageInline(admin.TabularInline):
    model = AIMessage
    extra = 0
    max_num = 0
    can_delete = False
    fields = ("created_at", "role", "provider", "grounded", "latency_ms", "apercu")
    readonly_fields = fields

    @admin.display(description="Contenu")
    def apercu(self, obj):
        return _apercu(obj.content)


@admin.register(AIConversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "titre", "mode", "nombre_messages", "archived")
    list_filter = ("mode", "archived")
    search_fields = ("title", "user__username")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("user",)
    autocomplete_fields = ("user",)
    readonly_fields = ("id", "user", "context", "created_at", "updated_at")
    inlines = (MessageInline,)
    show_full_result_count = False

    def get_queryset(self, request):
        from django.db.models import Count

        return super().get_queryset(request).annotate(_messages=Count("messages"))

    @admin.display(description="Titre")
    def titre(self, obj):
        return obj.title or "(sans titre)"

    @admin.display(description="Messages", ordering="_messages")
    def nombre_messages(self, obj):
        return obj._messages


@admin.register(AIMessage)
class MessageAdmin(TraceAdmin):
    list_display = ("created_at", "conversation", "role", "provider", "grounded",
                    "latency_ms", "apercu")
    # `grounded` distingue une réponse sourcée sur le mart d'une réponse libre :
    # c'est l'indicateur de gouvernance de cette table.
    list_filter = ("role", "grounded", "provider")
    search_fields = ("content", "metric_key", "conversation__title")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("conversation",)
    readonly_fields = ("conversation", "role", "content", "provider", "latency_ms",
                       "grounded", "metric_key", "payload", "created_at")

    @admin.display(description="Contenu")
    def apercu(self, obj):
        return _apercu(obj.content)


# ── Outils et circuit d'approbation ──────────────────────────────────────────


@admin.register(AIToolExecution)
class ExecutionAdmin(TraceAdmin):
    list_display = ("created_at", "tool_name", "user", "status", "latency_ms", "apercu_erreur")
    list_filter = ("status", "tool_name")
    search_fields = ("tool_name", "error", "user__username")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("user",)
    readonly_fields = ("tool_name", "user", "args", "status", "result", "error",
                       "latency_ms", "created_at")

    @admin.display(description="Erreur")
    def apercu_erreur(self, obj):
        return _apercu(obj.error, 80)


class ApprobationInline(admin.TabularInline):
    """Les décisions déjà enregistrées, en lecture.

    Elles ne se saisissent pas ici : une approbation doit passer par le circuit qui
    vérifie l'identité de l'approbateur et le compte des confirmations requises.
    """

    model = AIActionApproval
    extra = 0
    max_num = 0
    can_delete = False
    fields = ("decided_at", "approver", "decision", "note")
    readonly_fields = fields


@admin.register(AIActionRequest)
class DemandeActionAdmin(admin.ModelAdmin):
    list_display = ("created_at", "tool_name", "user", "resume", "destructive",
                    "status", "confirmations")
    list_filter = ("status", "destructive", "tool_name")
    search_fields = ("tool_name", "summary", "user__username")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("user", "conversation")
    # Tout est figé : approuver depuis l'admin contournerait le décompte des
    # confirmations et ne dirait pas QUI a approuvé.
    readonly_fields = ("id", "user", "conversation", "tool_name", "args", "summary",
                       "destructive", "required_confirmations", "status", "result",
                       "created_at")
    inlines = (ApprobationInline,)
    show_full_result_count = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Résumé")
    def resume(self, obj):
        return _apercu(obj.summary, 90)

    @admin.display(description="Confirmations")
    def confirmations(self, obj):
        """Combien de décisions sur combien d'exigées — la question qu'on se pose
        devant une demande en attente."""
        return f"{obj.approvals.count()} / {obj.required_confirmations}"


@admin.register(AIActionApproval)
class ApprobationAdmin(TraceAdmin):
    list_display = ("decided_at", "request", "approver", "decision", "note")
    list_filter = ("decision",)
    search_fields = ("approver__username", "note", "request__tool_name")
    date_hierarchy = "decided_at"
    ordering = ("-decided_at",)
    list_select_related = ("request", "approver")
    readonly_fields = ("request", "approver", "decision", "note", "decided_at")


@admin.register(AIAuditLog)
class JournalIAAdmin(TraceAdmin):
    """Piste d'audit des interactions IA : consultation seule, comme le journal
    d'accès. La purge relève d'une politique de rétention, pas d'un clic."""

    list_display = ("occurred_at", "user", "action", "provider", "success", "latency_ms", "ip")
    list_filter = ("action", "success", "provider")
    search_fields = ("action", "provider", "user__username")
    date_hierarchy = "occurred_at"
    ordering = ("-occurred_at",)
    list_select_related = ("user",)
    # `detail` reste consultable dans la fiche, jamais étalé en liste : c'est un
    # JSON qui peut porter le contenu d'un échange.
    readonly_fields = ("user", "action", "provider", "latency_ms", "success",
                       "detail", "ip", "occurred_at")
