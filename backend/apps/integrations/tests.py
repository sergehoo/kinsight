"""Tests du control-plane d'intégration (CRUD, chiffrement, test/sync, permissions, webhook)."""

import urllib.error
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .encryption import decrypt, encrypt, mask
from . import odoo, shield
from .models import ConnectorCredential, DataConnector, DataSource, SyncJob, SyncLog, WebhookEvent

User = get_user_model()
BASE = "/api/v1/integrations"


class EncryptionTest(APITestCase):
    def test_roundtrip(self):
        token = encrypt("super-secret-token")
        self.assertNotEqual(token, "super-secret-token")
        self.assertEqual(decrypt(token), "super-secret-token")

    def test_tamper_detected(self):
        token = encrypt("abc")
        with self.assertRaises(ValueError):
            decrypt(token[:-2] + ("AA" if not token.endswith("AA") else "BB"))

    def test_mask(self):
        self.assertEqual(mask("abcd1234"), "••••1234")


class IntegrationApiTest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", password="x")
        self.admin.is_superuser = True
        self.admin.save()
        self.reader = User.objects.create_user("reader", password="x", role="READER")

    def _create_source(self, source_type="rest"):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"{BASE}/sources/",
            {"name": "K-Shield", "slug": "k-shield", "source_type": source_type, "target_module": "securite"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.data

    def test_create_source_autocreates_connector_and_status(self):
        data = self._create_source()
        source = DataSource.objects.get(slug="k-shield")
        self.assertTrue(hasattr(source, "connector"))
        self.assertEqual(source.status, "configured")
        self.assertEqual(data["status"], "configured")

    def test_permission_denied_for_non_admin(self):
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get(f"{BASE}/sources/").status_code, 403)

    def test_credential_encrypted_never_exposed(self):
        self._create_source()
        source = DataSource.objects.get(slug="k-shield")
        cid = str(source.connector.id)
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            f"{BASE}/credentials/",
            {"connector": cid, "kind": "api_token", "label": "Token", "secret": "TOPSECRET123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertTrue(resp.data["is_set"])
        self.assertEqual(resp.data["masked"], "••••T123")
        self.assertNotIn("secret", {k: v for k, v in resp.data.items() if v == "TOPSECRET123"})
        cred = ConnectorCredential.objects.get(id=resp.data["id"])
        self.assertNotIn("TOPSECRET123", cred.secret_ciphertext)
        self.assertEqual(cred.secret, "TOPSECRET123")

    def test_test_connection_incomplete_then_complete(self):
        self._create_source()
        source = DataSource.objects.get(slug="k-shield")
        # base_url manquant → erreur
        r1 = self.client.post(f"{BASE}/sources/{source.id}/test-connection/")
        self.assertEqual(r1.status_code, 200)
        self.assertFalse(r1.data["ok"])
        self.assertEqual(r1.data["status"], "error")
        # on renseigne base_url → connecté
        self.client.patch(f"{BASE}/connectors/{source.connector.id}/", {"base_url": "https://api.k-shield.io"}, format="json")
        r2 = self.client.post(f"{BASE}/sources/{source.id}/test-connection/")
        self.assertTrue(r2.data["ok"])
        self.assertEqual(r2.data["status"], "connected")

    def test_sync_now_creates_job_and_log(self):
        self._create_source()
        source = DataSource.objects.get(slug="k-shield")
        self.client.patch(f"{BASE}/connectors/{source.connector.id}/", {"base_url": "https://api.k-shield.io"}, format="json")
        self.client.post(f"{BASE}/sources/{source.id}/test-connection/")
        r = self.client.post(f"{BASE}/sources/{source.id}/sync-now/")
        self.assertEqual(r.status_code, 202, r.content)
        self.assertTrue(SyncJob.objects.filter(source=source).exists())
        self.assertTrue(SyncLog.objects.filter(source=source).exists())
        self.assertEqual(r.data["status"], "success")

    def test_health_endpoint(self):
        self._create_source()
        r = self.client.get(f"{BASE}/sources/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total"], 1)
        self.assertIn("by_status", r.data)

    def test_webhook_records_event(self):
        self._create_source(source_type="webhook")
        source = DataSource.objects.get(slug="k-shield")
        # public, sans auth
        self.client.force_authenticate(user=None)
        r = self.client.post(f"{BASE}/webhook/k-shield/", {"event": "ping"}, format="json")
        self.assertEqual(r.status_code, 202, r.content)
        self.assertTrue(WebhookEvent.objects.filter(source=source).exists())


class ShieldHrKpiTest(APITestCase):
    """KPIs RH Shield : gouvernance (aucune donnée inventée) + accès authentifié."""

    URL = f"{BASE}/shield/hr-kpi/"
    KEYS = {"effectif_total", "employes", "ouvriers", "presents", "absents", "retards", "taux_presence", "sites"}

    def setUp(self):
        self.user = User.objects.create_user(username="rh", password="x", email="rh@k.co")

    def test_requires_auth(self):
        self.assertEqual(self.client.get(self.URL).status_code, 401)

    def test_disconnected_when_no_source(self):
        self.client.force_authenticate(self.user)
        data = self.client.get(self.URL).json()
        self.assertEqual(data["status"], "disconnected")
        self.assertEqual(data["by_site"], {"status": "disconnected", "sites": []})
        keys = {k["key"] for k in data["kpis"]}
        self.assertEqual(keys, self.KEYS)
        # Aucune valeur fabriquée tant que non connecté.
        self.assertTrue(all(k["value"] is None and k["status"] == "disconnected" for k in data["kpis"]))

    def test_disconnected_when_source_not_connected(self):
        DataSource.objects.create(name="Kaydan Shield", slug="kaydan-shield", source_type="kaydan_shield")
        self.client.force_authenticate(self.user)
        data = self.client.get(self.URL).json()
        self.assertEqual(data["status"], "disconnected")
        self.assertTrue(all(k["value"] is None for k in data["kpis"]))


class ShieldConnectorUnitTest(APITestCase):
    """Connecteur Shield : sélection du secret, normalisation, dégradation par KPI."""

    def _source(self, status="connected"):
        source = DataSource.objects.create(name="Kaydan Shield", slug="kaydan-shield", source_type="kaydan_shield", status=status)
        connector = DataConnector.objects.create(source=source, base_url="https://api.kaydanshield.com", auth_method="bearer")
        return source, connector

    def test_secret_selection_is_deterministic(self):
        """Un client_id créé en premier ne doit jamais masquer le vrai token API."""
        _, connector = self._source()
        first = ConnectorCredential(connector=connector, kind="client_id")
        first.set_secret("pas-le-bon")
        first.save()
        token = ConnectorCredential(connector=connector, kind="api_token")
        token.set_secret("le-bon-token")
        token.save()
        self.assertEqual(shield._pick_secret(connector), "le-bon-token")

    def test_empty_credential_is_skipped(self):
        _, connector = self._source()
        ConnectorCredential.objects.create(connector=connector, kind="api_token")  # secret vide
        self.assertEqual(shield._pick_secret(connector), "")

    SITES = [
        {"id": 1, "code": "KRE-01", "name": "Chantier Riviera", "type": "site", "status": "active", "company_name": "K-Express"},
        {"id": 2, "code": "SIEGE", "name": "Siège Abidjan", "type": "office", "status": "active", "company_name": "Groupe Kaydan"},
    ]

    def _payloads(self):
        return {
            shield.EP_EMPLOYEES: {"count": 120, "results": []},
            shield.EP_WORKERS: {"count": 80, "results": []},
            shield.EP_SITES: {"count": 6, "results": self.SITES},
            shield.EP_ATTENDANCE_TODAY: {"date": "2026-09-05", "present_count": 150, "absent_count": 50, "late_count": 7, "total_workers": 200},
        }

    def test_connected_normalises_real_shapes(self):
        self._source()
        payloads = self._payloads()
        with patch.object(shield, "_get_json", side_effect=lambda base, path, headers, params=None: payloads[path]):
            data = shield.fetch_hr_kpis()
        self.assertEqual(data["status"], "connected")
        kpis = {k["key"]: k for k in data["kpis"]}
        self.assertEqual(kpis["employes"]["value"], 120)
        self.assertEqual(kpis["ouvriers"]["value"], 80)
        self.assertEqual(kpis["effectif_total"]["value"], 200)
        self.assertEqual(kpis["presents"]["value"], 150)
        self.assertEqual(kpis["absents"]["value"], 50)
        self.assertEqual(kpis["retards"]["value"], 7)
        self.assertEqual(kpis["taux_presence"]["value"], 75.0)
        self.assertEqual(kpis["sites"]["value"], 6)
        self.assertTrue(all(k["status"] == "connected" for k in data["kpis"]))

    def test_by_site_liste_les_sites_reels_sans_inventer_de_presence(self):
        self._source()
        payloads = self._payloads()
        with patch.object(shield, "_get_json", side_effect=lambda base, path, headers, params=None: payloads[path]):
            data = shield.fetch_hr_kpis()
        by_site = data["by_site"]
        # `partial` : les sites sont réels, la présence par site ne l'est pas.
        self.assertEqual(by_site["status"], "partial")
        self.assertEqual([s["code"] for s in by_site["sites"]], ["KRE-01", "SIEGE"])
        self.assertEqual(by_site["sites"][0]["name"], "Chantier Riviera")
        # Shield n'expose aucun compteur de présence par site : on n'en fabrique pas.
        self.assertTrue(all(s["present_count"] is None for s in by_site["sites"]))
        self.assertTrue(all(s["presence_status"] == "disconnected" for s in by_site["sites"]))

    def test_niveaux_de_donnee_et_formules(self):
        """Un chiffre calculé par K-Insight doit porter sa formule ; une mesure, sa source."""
        self._source()
        payloads = self._payloads()
        with patch.object(shield, "_get_json", side_effect=lambda base, path, headers, params=None: payloads[path]):
            data = shield.fetch_hr_kpis()
        kpis = {k["key"]: k for k in data["kpis"]}
        # Calculés : formule obligatoire, pas de champ source.
        for key in ("effectif_total", "taux_presence"):
            self.assertEqual(kpis[key]["level"], "computed")
            self.assertTrue(kpis[key]["formula"], f"{key} sans formule documentée")
        # Mesurés : champ source obligatoire, pas de formule.
        for key in ("employes", "ouvriers", "presents", "absents", "retards", "sites"):
            self.assertEqual(kpis[key]["level"], "measured")
            self.assertEqual(kpis[key]["formula"], "")
            self.assertTrue(kpis[key]["source_field"], f"{key} sans champ source")

    def test_partial_failure_never_fabricates(self):
        """Si l'appel présence échoue, ses KPIs passent en error SANS valeur inventée."""
        self._source()
        payloads = self._payloads()

        def flaky(base, path, headers, params=None):
            if path == shield.EP_ATTENDANCE_TODAY:
                raise urllib.error.URLError("boom")
            return payloads[path]

        with patch.object(shield, "_get_json", side_effect=flaky):
            data = shield.fetch_hr_kpis()
        kpis = {k["key"]: k for k in data["kpis"]}
        self.assertEqual(data["status"], "partial")  # honnête : une partie des mesures manque
        for key in ("presents", "absents", "retards", "taux_presence"):
            self.assertEqual(kpis[key]["status"], "error")
            self.assertIsNone(kpis[key]["value"])
        self.assertEqual(kpis["employes"]["value"], 120)

    def test_zero_is_a_real_value_not_nd(self):
        """0 présent est une donnée réelle : elle doit rester 0 en statut success."""
        self._source()
        payloads = self._payloads()
        payloads[shield.EP_ATTENDANCE_TODAY] = {"present_count": 0, "absent_count": 0, "late_count": 0}
        with patch.object(shield, "_get_json", side_effect=lambda base, path, headers, params=None: payloads[path]):
            data = shield.fetch_hr_kpis()
        kpis = {k["key"]: k for k in data["kpis"]}
        self.assertEqual(kpis["presents"]["value"], 0)
        self.assertEqual(kpis["presents"]["status"], "connected")
        self.assertIsNone(kpis["taux_presence"]["value"])  # 0/0 : pas de taux inventé


class OdooHrSkeletonTest(APITestCase):
    """Squelette Odoo : jamais de donnée, état explicite uniquement."""

    def test_not_configured_without_source(self):
        data = odoo.fetch_hr_reference()
        self.assertEqual(data["status"], "not_configured")
        self.assertEqual(data["records"], [])

    def test_not_implemented_with_source(self):
        DataSource.objects.create(name="Odoo RH", slug="odoo-hr", source_type="odoo_hr", status="connected")
        data = odoo.fetch_hr_reference()
        self.assertEqual(data["status"], "not_implemented")
        self.assertEqual(data["records"], [])
        self.assertIn("hr.employee", data["models"])
