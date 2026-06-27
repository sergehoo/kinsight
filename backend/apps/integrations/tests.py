"""Tests du control-plane d'intégration (CRUD, chiffrement, test/sync, permissions, webhook)."""

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .encryption import decrypt, encrypt, mask
from .models import ConnectorCredential, DataSource, SyncJob, SyncLog, WebhookEvent

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
