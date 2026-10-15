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
    ADMIN_INTEGRATION = "ADMIN_INTEGRATION", "Administrateur intégrations"
    DG_GROUP = "DG_GROUP", "Directeur général groupe"
    CODIR = "CODIR", "Membre du CODIR"
    DAF = "DAF", "Directeur administratif & financier"
    DRH = "DRH", "Directeur des ressources humaines"
    DIR_OPS = "DIR_OPS", "Directeur opérationnel"
    RESP_METIER = "RESP_METIER", "Responsable métier"
    DIR_FILIALE = "DIR_FILIALE", "Directeur de filiale"
    ASSISTANT_RH = "ASSISTANT_RH", "Assistant RH"
    READER = "READER", "Lecteur"


# Rôles dont le périmètre est TOUJOURS restreint à leurs filiales : un drapeau
# « groupe » coché par erreur ne leur ouvre pas les autres filiales.
ROLES_TOUJOURS_RESTREINTS = {Role.DIR_FILIALE}


# Rôles habilités à voir des données nominatives (ex. salaire individuel). Les autres
# n'accèdent qu'aux agrégats (masquage, ADR-0005).
_NOMINATIVE_ROLES = {Role.DRH, Role.DAF, Role.DG_GROUP, Role.ADMIN_CA}


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.READER)
    is_group_scope = models.BooleanField(
        default=False, help_text="Accès à toutes les filiales du groupe."
    )
    subsidiaries = models.ManyToManyField(
        "organizations.Subsidiary", blank=True, related_name="users"
    )
    # Assistant RH : les pages Capital Humain EXPLICITEMENT affectées (clés de
    # module, ex. « hr-attendance »). Vide = aucune page. Ignoré pour les autres rôles.
    affectations_rh = models.JSONField(default=list, blank=True)

    def scope(self) -> Scope:
        """Périmètre de visibilité (domaine pur). L'ordre est la règle :

        1. Un rôle toujours restreint (directeur de filiale) : ses filiales, rien
           d'autre — même superutilisateur, même case « groupe » cochée.
        2. Case « groupe » cochée : le Groupe.
        3. Filiales cochées : ces filiales — un compte rattaché à une filiale reste
           restreint, même superutilisateur (sinon un RH de KRE à qui l'on ouvre
           l'admin Django recevrait les totaux Groupe).
        4. AUCUN périmètre explicite et accès total (superutilisateur, ADMIN_CA) :
           le Groupe. C'est le compte créé par `createsuperuser` (case décochée par
           défaut) ; il recevait un périmètre VIDE, donc N/D et « Non rattaché »
           partout alors que la source était connectée — régression prod du
           2026-10-15, depuis la règle ADR-0009 « total Shield = Groupe seulement ».
        5. Sinon : aucun périmètre.
        """
        if self.is_group_scope and self.role not in ROLES_TOUJOURS_RESTREINTS:
            return Scope.group()   # sans requête : le cas courant d'un compte Groupe
        codes = list(self.subsidiaries.values_list("code", flat=True))
        if self.role in ROLES_TOUJOURS_RESTREINTS:
            return Scope.of(*codes) if codes else Scope.none()
        if codes:
            return Scope.of(*codes)
        if self.is_superuser or self.role == Role.ADMIN_CA:
            return Scope.group()
        return Scope.none()

    @property
    def can_see_nominative(self) -> bool:
        return self.role in _NOMINATIVE_ROLES
