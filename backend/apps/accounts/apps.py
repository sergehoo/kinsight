from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Comptes & RBAC"

    def ready(self):
        from . import checks  # noqa: F401 — enregistre le contrôle des périmètres
