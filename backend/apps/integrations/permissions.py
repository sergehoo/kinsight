from rest_framework.permissions import BasePermission

INTEGRATION_ADMIN_ROLES = {"ADMIN_INTEGRATION", "ADMIN_CA"}


class IsIntegrationAdmin(BasePermission):
    """Accès réservé aux SUPER_ADMIN (superuser) et ADMIN_INTÉGRATION."""

    message = "Réservé aux administrateurs d'intégration."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return bool(user.is_superuser or getattr(user, "role", "") in INTEGRATION_ADMIN_ROLES)
