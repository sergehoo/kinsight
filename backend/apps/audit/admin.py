"""Consultation du journal d'accès.

Ce journal est une PISTE D'AUDIT : l'admin l'ouvre en lecture, jamais en écriture.
Ajout, modification et suppression sont refusés — pouvoir retoucher une ligne
reviendrait à falsifier la trace qu'elle est censée constituer, et pouvoir la
supprimer à l'effacer. La purge relève d'une politique de rétention exécutée par le
code, pas d'un clic dans une interface.
"""

from django.contrib import admin

from .models import AccessLog


@admin.register(AccessLog)
class JournalAccesAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "user", "user_role", "action", "metric_key", "ip_address")
    list_filter = ("action", "user_role", "occurred_at")
    search_fields = ("action", "metric_key", "user__username")
    date_hierarchy = "occurred_at"
    ordering = ("-occurred_at",)
    list_select_related = ("user",)
    # `payload` et le périmètre restent consultables dans le détail, pas en liste :
    # ce sont des JSON qui rendraient le tableau illisible.
    readonly_fields = ("occurred_at", "user", "user_role", "action", "metric_key",
                       "subsidiary_scope", "payload", "ip_address")
    # Cette table grossit sans cesse. Le COUNT(*) global que Django affiche par
    # défaut coûte un balayage complet à chaque page.
    show_full_result_count = False
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
