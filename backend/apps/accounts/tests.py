"""Droits d'un compte : côté application, et côté admin Django.

Deux niveaux que la page de connexion ne distingue pas. `role` gouverne
l'application K-Insight — c'est ce que `auth/me` renvoie et ce que l'en-tête du
tableau de bord affiche. `is_staff` gouverne l'admin Django, et rien d'autre : un
superutilisateur sans ce drapeau se fait refuser avec le même message que pour un
mot de passe erroné.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class MeApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _me(self, **kw):
        u = User.objects.create_user(password="x", **kw)
        self.client.force_authenticate(u)
        return self.client.get("/api/v1/auth/me/")

    def test_authentification_requise(self):
        self.assertIn(self.client.get("/api/v1/auth/me/").status_code, (401, 403))

    def test_superuser_acces_total(self):
        resp = self._me(username="root", is_superuser=True, is_staff=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("SUPER_ADMIN", resp.data["permissions"])
        self.assertEqual(resp.data["landing"], "/dashboard/overview-groupe")

    def test_drh_capital_humain(self):
        resp = self._me(username="drh", role="DRH")
        self.assertEqual(resp.data["permissions"], ["view_hr"])
        self.assertEqual(resp.data["landing"], "/dashboard/capital-humain")

    def test_daf_finance(self):
        resp = self._me(username="daf", role="DAF")
        self.assertIn("view_finance", resp.data["permissions"])
        self.assertIn("view_reports", resp.data["permissions"])
        self.assertEqual(resp.data["landing"], "/dashboard/finance")

    def test_dg_voit_tout(self):
        resp = self._me(username="dg", role="DG_GROUP", is_group_scope=True)
        self.assertIn("view_all_dashboards", resp.data["permissions"])
        self.assertEqual(resp.data["scope"], "GROUP")

    def test_admin_integration_landing(self):
        resp = self._me(username="adm", role="ADMIN_INTEGRATION")
        self.assertEqual(resp.data["landing"], "/admin/integrations")

    def test_profil_complet(self):
        resp = self._me(username="r", role="READER", first_name="Awa", last_name="Koné")
        self.assertEqual(resp.data["full_name"], "Awa Koné")
        self.assertEqual(resp.data["role"], "READER")
        self.assertFalse(resp.data["can_see_nominative"])


class AdminAccessTest(TestCase):
    def _lancer(self, *args):
        sortie = StringIO()
        call_command("admin_access", *args, stdout=sortie)
        return sortie.getvalue()

    def test_un_superutilisateur_sans_is_staff_est_refuse_et_on_le_dit(self):
        """Le cas réellement rencontré : tous les droits applicatifs, aucun accès
        à l'admin Django, et un message de Django qui laisse croire à un mot de
        passe erroné."""
        User.objects.create_user(username="ogah", password="x", email="o@k.co",
                                 role="DG_GROUP", is_superuser=True, is_staff=False)
        sortie = self._lancer("ogah")
        self.assertIn("`is_staff` est faux", sortie)
        self.assertIn("ressemble à tort à un mot de passe erroné", sortie)

    def test_accorder_ne_donne_que_is_staff(self):
        """Le passage en superutilisateur doit rester un geste explicite : il
        contourne toute vérification de permission."""
        compte = User.objects.create_user(username="chef", password="x", email="c@k.co")
        sortie = self._lancer("chef", "--accorder")
        compte.refresh_from_db()
        self.assertTrue(compte.is_staff)
        self.assertFalse(compte.is_superuser, "superutilisateur accordé sans qu'on le demande")
        self.assertIn("is_staff → True", sortie)

    def test_superutilisateur_est_explicite(self):
        compte = User.objects.create_user(username="chef2", password="x", email="c2@k.co")
        self._lancer("chef2", "--superutilisateur")
        compte.refresh_from_db()
        self.assertTrue(compte.is_staff)
        self.assertTrue(compte.is_superuser)

    def test_un_compte_desactive_est_diagnostique_avant_le_reste(self):
        User.objects.create_user(username="parti", password="x", email="p@k.co",
                                 is_staff=True, is_active=False)
        self.assertIn("compte désactivé", self._lancer("parti"))

    def test_un_compte_staff_sans_permission_est_averti(self):
        """L'admin s'ouvre mais n'affiche aucun modèle : mieux vaut le dire que
        laisser conclure à une page cassée."""
        User.objects.create_user(username="staff", password="x", email="s@k.co", is_staff=True)
        sortie = self._lancer("staff")
        self.assertIn("Accès à l'admin Django autorisé", sortie)
        self.assertIn("n'affiche aucun modèle", sortie)

    def test_un_superutilisateur_staff_a_tout(self):
        User.objects.create_superuser(username="root", password="x", email="r@k.co")
        self.assertIn("Accès complet", self._lancer("root"))

    def test_un_compte_inconnu_liste_les_comptes_existants(self):
        User.objects.create_user(username="present", password="x", email="pr@k.co")
        with self.assertRaises(CommandError) as ctx:
            self._lancer("absent")
        self.assertIn("present", str(ctx.exception))

    def test_accorder_deux_fois_ne_change_rien_la_seconde(self):
        User.objects.create_user(username="idem", password="x", email="i@k.co")
        self._lancer("idem", "--accorder")
        self.assertIn("Rien à modifier", self._lancer("idem", "--accorder"))
