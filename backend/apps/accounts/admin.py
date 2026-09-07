"""Administration des comptes et de leur périmètre.

On étend `UserAdmin` de Django plutôt que d'écrire un `ModelAdmin` nu : lui seul
apporte le formulaire de mot de passe qui HACHE la saisie. Un ModelAdmin ordinaire
écrirait la valeur telle quelle dans le champ `password`, produisant un compte dont
personne ne pourrait se connecter — et un mot de passe stocké en clair.

Le champ `role` est mis en avant : c'est lui qui ouvre ou ferme le centre
d'intégrations (`IsIntegrationAdmin`), et jusqu'ici l'attribuer exigeait un shell.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Role, User


@admin.register(User)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "email", "role", "perimetre", "is_active", "is_staff", "is_superuser")
    list_filter = ("role", "is_group_scope", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    # Le périmètre est un many-to-many : le charger en une requête évite une
    # requête par ligne sur la liste.
    filter_horizontal = ("groups", "user_permissions", "subsidiaries")

    # `UserAdmin.fieldsets` est un tuple de classe : on le recopie pour y insérer la
    # section propre au projet, sans muter la valeur héritée (qui est partagée).
    fieldsets = UserAdmin.fieldsets + (
        (
            "Gouvernance K-Insight",
            {
                "fields": ("role", "is_group_scope", "subsidiaries"),
                "description": (
                    "Le rôle gouverne l'accès aux domaines et au centre d'intégrations. "
                    "Un périmètre « groupe » donne accès à toutes les filiales ; sinon, "
                    "seules les filiales cochées sont visibles."
                ),
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Gouvernance K-Insight", {"fields": ("role", "is_group_scope")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("subsidiaries")

    @admin.display(description="Périmètre")
    def perimetre(self, obj):
        """Ce que l'utilisateur voit réellement, en une colonne.

        Afficher la liste des filiales plutôt que le booléen seul évite la question
        « groupe coché ou pas ? » à chaque vérification de droits.
        """
        if obj.is_group_scope:
            return "Groupe (toutes filiales)"
        codes = [s.code for s in obj.subsidiaries.all()]
        return ", ".join(codes) if codes else "Aucun"

    @admin.display(description="Rôle")
    def role_libelle(self, obj):
        return Role(obj.role).label if obj.role in Role.values else obj.role
