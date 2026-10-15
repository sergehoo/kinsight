from django.apps import AppConfig


class GovernanceConfig(AppConfig):
    name = "apps.governance"
    verbose_name = "Gouvernance (catalogue & accès mart)"

    def ready(self):
        # Les seuils arbitrés par la direction remplacent les valeurs par défaut de
        # `shield_rules` partout où elles s'appliquent (constats du jour, cartes).
        from apps.integrations import shield_rules

        from .seuils_rh import surcharges_shield

        shield_rules.brancher_configuration(surcharges_shield)
