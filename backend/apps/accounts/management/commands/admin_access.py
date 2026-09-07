"""Pourquoi ce compte n'entre-t-il pas dans l'admin Django ?

    docker compose exec backend python manage.py admin_access ogah
    docker compose exec backend python manage.py admin_access ogah --accorder

Django refuse l'accès à son administration avec un message unique — « Veuillez
compléter correctement les champs nom d'utilisateur et mot de passe d'un compte
autorisé » — qu'il affiche AUSSI BIEN pour un mot de passe erroné que pour un
compte valide dépourvu de `is_staff`. Impossible de distinguer les deux depuis la
page de connexion, ce qui envoie chercher un problème de mot de passe là où il
manque un drapeau.

Deux niveaux de droits se confondent facilement dans ce projet :

  `role` (ADMIN_CA, ADMIN_INTEGRATION…) gouverne l'application K-Insight — les
     domaines visibles et l'accès au centre de connecteurs. C'est ce que l'en-tête
     du tableau de bord affiche, « Super Admin » compris.
  `is_staff` / `is_superuser` gouvernent l'administration DJANGO, et rien d'autre.

Un compte peut donc être administrateur de la plateforme sans pouvoir ouvrir
/manage/app/back/, et réciproquement.

`--accorder` ne donne que `is_staff` : le passage en superutilisateur reste un geste
explicite, parce qu'il contourne toute vérification de permission.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

OK, KO, INFO = "  OK  ", " ÉCHEC", " INFO "


class Command(BaseCommand):
    help = "Explique si un compte peut ouvrir l'admin Django, et peut lui en donner le droit."

    def add_arguments(self, parser):
        parser.add_argument("identifiant", help="Nom d'utilisateur du compte à examiner.")
        parser.add_argument("--accorder", action="store_true",
                            help="Accorde `is_staff` (accès à l'admin), sans toucher au reste.")
        parser.add_argument("--superutilisateur", action="store_true",
                            help="Accorde AUSSI `is_superuser` : contourne toute permission.")

    def _ligne(self, marqueur: str, titre: str, detail: str = "") -> None:
        self.stdout.write(f"[{marqueur}] {titre}" + (f"\n         {detail}" if detail else ""))

    def handle(self, *args, **options):
        modele = get_user_model()
        identifiant = options["identifiant"]
        try:
            compte = modele.objects.get(**{modele.USERNAME_FIELD: identifiant})
        except modele.DoesNotExist:
            connus = list(modele.objects.values_list(modele.USERNAME_FIELD, flat=True)[:15])
            raise CommandError(
                f"Aucun compte « {identifiant} ». Comptes existants : {', '.join(connus) or 'aucun'}"
            )

        self.stdout.write(f"Compte     : {getattr(compte, modele.USERNAME_FIELD)}")
        self.stdout.write(f"Rôle       : {getattr(compte, 'role', '—')}  (droits APPLICATIFS)")
        self.stdout.write(f"actif      : {compte.is_active}")
        self.stdout.write(f"is_staff   : {compte.is_staff}      (droit d'ouvrir l'admin Django)")
        self.stdout.write(f"is_superuser: {compte.is_superuser}\n")

        if options["accorder"] or options["superutilisateur"]:
            self._accorder(compte, superutilisateur=options["superutilisateur"])

        self._verdict(compte)

    def _accorder(self, compte, *, superutilisateur: bool) -> None:
        change = []
        if not compte.is_active:
            compte.is_active = True
            change.append("is_active")
        if not compte.is_staff:
            compte.is_staff = True
            change.append("is_staff")
        if superutilisateur and not compte.is_superuser:
            compte.is_superuser = True
            change.append("is_superuser")
        if change:
            compte.save(update_fields=[*change])
            self._ligne(OK, "Droits modifiés", ", ".join(f"{c} → True" for c in change))
        else:
            self._ligne(INFO, "Rien à modifier", "Le compte avait déjà ces droits.")

    def _verdict(self, compte) -> None:
        if not compte.is_active:
            self._ligne(KO, "Connexion impossible : compte désactivé",
                        "Django refuse avant même de regarder le mot de passe.")
            return
        if not compte.is_staff:
            self._ligne(KO, "Connexion impossible : `is_staff` est faux",
                        "C'est la cause du message « compte autorisé », qui ressemble à tort à un "
                        "mot de passe erroné. Relancer avec --accorder pour ouvrir l'accès.")
            return
        if compte.is_superuser:
            self._ligne(OK, "Accès complet à l'admin Django",
                        "Superutilisateur : toutes les permissions, sans vérification.")
            return
        nb = compte.user_permissions.count() + sum(g.permissions.count() for g in compte.groups.all())
        self._ligne(OK, "Accès à l'admin Django autorisé",
                    f"{nb} permission(s) attribuée(s). Sans permission, l'admin s'ouvre mais "
                    f"n'affiche aucun modèle — les accorder par groupe est plus tenable "
                    f"qu'un superutilisateur de plus.")
