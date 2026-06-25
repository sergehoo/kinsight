"""Utilisateurs, rôles et périmètres (RBAC multi-filiales, ADR-0005).

Le périmètre d'un utilisateur est soit le **groupe** (toutes les filiales), soit un
ensemble explicite de filiales. La méthode `scope()` produit le `Scope` du domaine pur
qui sera appliqué à toute requête au mart.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models

from k_insight.access import Scope


class Role(models.TextChoices):
    ADMIN_CA = "ADMIN_CA", "Administrateur / Conseil d'administration"
    DG_GROUP = "DG_GROUP", "Directeur général groupe"
    CODIR = "CODIR", "Membre du CODIR"
    DAF = "DAF", "Directeur administratif & financier"
    DRH = "DRH", "Directeur des ressources humaines"
    DIR_OPS = "DIR_OPS", "Directeur opérationnel"
    RESP_METIER = "RESP_METIER", "Responsable métier"
    READER = "READER", "Lecteur"


# Rôles habilités à voir des données nominatives (ex. salaire individuel). Les autres
# n'accèdent qu'aux agrégats (masquage, ADR-0005).
_NOMINATIVE_ROLES = {Role.DRH, Role.DAF, Role.DG_GROUP, Role.ADMIN_CA}


class User(AbstractUser):
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.READER)
    is_group_scope = models.BooleanField(
        default=False, help_text="Accès à toutes les filiales du groupe."
    )
    subsidiaries = models.ManyToManyField(
        "organizations.Subsidiary", blank=True, related_name="users"
    )

    def scope(self) -> Scope:
        """Périmètre de visibilité (domaine pur)."""
        if self.is_group_scope:
            return Scope.group()
        codes = list(self.subsidiaries.values_list("code", flat=True))
        return Scope.of(*codes) if codes else Scope.none()

    @property
    def can_see_nominative(self) -> bool:
        return self.role in _NOMINATIVE_ROLES
