"""Tests auth/me : profil + RBAC autoritative par rôle."""

from django.contrib.auth import get_user_model
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
