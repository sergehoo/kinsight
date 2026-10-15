"""Administration de l'historique RH : consultation seule.

Un instantané ne se corrige pas à la main. Une valeur fausse se répare en
rejouant la collecte de sa journée (`manage.py historiser`), qui met la ligne à
jour au même grain ; une retouche manuelle, elle, ferait coexister dans la même
série des mesures et une saisie, sans que rien ne les distingue.
"""

from django.contrib import admin

from .models import KpiSnapshot, SeuilRh


@admin.register(KpiSnapshot)
class KpiSnapshotAdmin(admin.ModelAdmin):
    list_display = ("jour", "metric_id", "dimension", "code", "libelle", "valeur", "statut", "source")
    list_filter = ("source", "dimension", "statut", "metric_id")
    search_fields = ("metric_id", "code", "libelle")
    date_hierarchy = "jour"
    readonly_fields = [f.name for f in KpiSnapshot._meta.fields]
    show_full_result_count = False
    list_per_page = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeuilRh)
class SeuilRhAdmin(admin.ModelAdmin):
    """Consultation seule : un seuil se modifie par l'API, qui valide l'ordre des
    paliers et trace l'arbitrage (avant / après) dans le journal d'accès."""

    list_display = ("signal", "surveillance", "critique", "modifie_par", "modifie_le")
    readonly_fields = [f.name for f in SeuilRh._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
