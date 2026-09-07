"""Administration du référentiel des filiales.

`search_fields` n'est pas décoratif : il est requis dès qu'un autre admin vise ce
modèle en `autocomplete_fields`, faute de quoi Django refuse de démarrer (admin.E039).
"""

from django.contrib import admin

from .models import Subsidiary


@admin.register(Subsidiary)
class FilialeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "entity_code", "country", "currency", "is_active")
    list_filter = ("is_active", "country", "currency")
    search_fields = ("code", "name", "entity_code")
    ordering = ("code",)
    list_editable = ("is_active",)
