"""Tests du control-plane d'intégration et du connecteur Kaydan Shield."""

import json
import time
import urllib.error
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient, APITestCase

from datetime import timedelta

from django.utils import timezone

from . import odoo, shield
from . import shield_rules as R
from . import shield_endpoints as EP
from .encryption import decrypt, encrypt, mask
from .models import (
    AuthMethod,
    ConnectorCredential,
    DataConnector,
    DataSource,
    SourceStatus,
    SourceType,
    SyncJob,
    SyncLog,
    WebhookEvent,
)
from .shield_client import ShieldClient, ShieldError

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
        # `probe=0` : on vérifie ici la COMPLÉTUDE de la configuration, pas la
        # joignabilité de l'hôte — le test réseau réel est couvert ailleurs.
        r1 = self.client.post(f"{BASE}/sources/{source.id}/test-connection/?probe=0")
        self.assertEqual(r1.status_code, 200)
        self.assertFalse(r1.data["ok"])
        self.assertEqual(r1.data["status"], "error")
        # on renseigne base_url → configuration complète
        self.client.patch(f"{BASE}/connectors/{source.connector.id}/", {"base_url": "https://api.k-shield.io"}, format="json")
        r2 = self.client.post(f"{BASE}/sources/{source.id}/test-connection/?probe=0")
        self.assertTrue(r2.data["ok"])
        self.assertEqual(r2.data["status"], "connected")

    def test_sync_now_creates_job_and_log(self):
        self._create_source()
        source = DataSource.objects.get(slug="k-shield")
        self.client.patch(f"{BASE}/connectors/{source.connector.id}/", {"base_url": "https://api.k-shield.io"}, format="json")
        self.client.post(f"{BASE}/sources/{source.id}/test-connection/?probe=0")
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


class ShieldClientTest(TestCase):
    """Transport : ce qui distingue « refus », « panne » et « lenteur »."""

    def _client(self):
        return ShieldClient("https://shield.test", {"Authorization": "Bearer x"}, timeout=1)

    def test_401_et_403_ne_sont_pas_rejoues(self):
        """Un refus est définitif : réessayer masquerait une erreur de configuration."""
        for code in (401, 403):
            with patch.object(ShieldClient, "_fetch", side_effect=urllib.error.HTTPError(
                    "u", code, "refus", {}, None)) as fetch:
                with self.assertRaises(ShieldError) as ctx:
                    self._client().get_json("/api/v1/sites/sites/", use_cache=False)
            self.assertEqual(ctx.exception.kind, "auth")
            self.assertEqual(ctx.exception.status, code)
            self.assertEqual(fetch.call_count, 1, f"HTTP {code} rejoué alors qu'il est définitif")

    def test_erreur_serveur_rejouee_puis_abandonnee(self):
        with patch.object(ShieldClient, "_fetch", side_effect=urllib.error.HTTPError(
                "u", 503, "indispo", {}, None)) as fetch, patch("time.sleep"):
            with self.assertRaises(ShieldError) as ctx:
                self._client().get_json("/api/v1/sites/sites/", use_cache=False)
        self.assertEqual(ctx.exception.kind, "http")
        self.assertEqual(fetch.call_count, 3, "la reprise doit être bornée à 3 tentatives")

    def test_timeout_qualifie(self):
        with patch.object(ShieldClient, "_fetch", side_effect=TimeoutError()), patch("time.sleep"):
            with self.assertRaises(ShieldError) as ctx:
                self._client().get_json("/api/v1/sites/sites/", use_cache=False)
        self.assertEqual(ctx.exception.kind, "timeout")

    def test_hote_injoignable_qualifie(self):
        with patch.object(ShieldClient, "_fetch", side_effect=urllib.error.URLError("dns")), patch("time.sleep"):
            with self.assertRaises(ShieldError) as ctx:
                self._client().get_json("/api/v1/sites/sites/", use_cache=False)
        self.assertEqual(ctx.exception.kind, "network")

    def test_count_lit_la_pagination_sans_rapatrier_les_lignes(self):
        with patch.object(ShieldClient, "_fetch", return_value={"count": 4213, "results": [{}]}) as fetch:
            total = self._client().count("/api/v1/employees/employees/")
        self.assertEqual(total, 4213)
        self.assertIn("limit=1", fetch.call_args[0][0], "count doit demander limit=1")

    def test_zero_reel_reste_zero(self):
        """0 mesuré est une information : il ne doit jamais devenir None."""
        with patch.object(ShieldClient, "_fetch", return_value={"count": 0, "results": []}):
            self.assertEqual(self._client().count("/api/v1/ouvriers/workers/"), 0)

    def test_jeu_de_donnees_vide(self):
        with patch.object(ShieldClient, "_fetch", return_value={"count": 0, "results": []}):
            self.assertEqual(self._client().results("/api/v1/sites/sites/"), [])

    def test_payload_inattendu_qualifie(self):
        with patch.object(ShieldClient, "_fetch", return_value="pas du JSON attendu"):
            with self.assertRaises(ShieldError) as ctx:
                self._client().count("/api/v1/sites/sites/")
        self.assertEqual(ctx.exception.kind, "payload")

    def test_pagination_bornee(self):
        page = {"count": 10_000, "results": [{"id": i} for i in range(200)]}
        with patch.object(ShieldClient, "_fetch", return_value=page) as fetch:
            rows = self._client().paginate("/api/v1/ouvriers/workers/", page_size=200, max_pages=3)
        self.assertEqual(len(rows), 600)
        self.assertEqual(fetch.call_count, 3, "la pagination doit s'arrêter au plafond")

    def test_cache_court_evite_la_rafale(self):
        with patch.object(ShieldClient, "_fetch", return_value={"count": 1}) as fetch:
            client = self._client()
            client.get_json("/api/v1/sites/sites/")
            client.get_json("/api/v1/sites/sites/")
        self.assertEqual(fetch.call_count, 1, "le second appel identique doit venir du cache")


class ShieldConnectorTest(TestCase):
    """Normalisation métier : états gouvernés, by_site réel, insights déterministes."""

    SITES = [
        {"id": 1, "code": "KRE-01", "name": "Chantier Riviera", "type": "site",
         "status": "active", "company_name": "K-Express"},
        {"id": 2, "code": "SIEGE", "name": "Siège Abidjan", "type": "office",
         "status": "active", "company_name": "Groupe Kaydan"},
    ]

    def _source(self, status=SourceStatus.CONNECTED):
        source = DataSource.objects.create(
            name="Kaydan Shield", slug="kaydan-shield",
            source_type=SourceType.KAYDAN_SHIELD, status=status)
        DataConnector.objects.create(source=source, base_url="https://shield.test",
                                     auth_method=AuthMethod.BEARER)
        return source

    def _routes(self, **overrides):
        """Fausse API Shield : répond selon le chemin ET les filtres reçus."""
        def handler(path, params=None, **kw):
            params = params or {}
            if path in overrides:
                value = overrides[path]
                return value(params) if callable(value) else value
            if path == EP.EMPLOYEES:
                return {"count": 120, "results": []}
            if path == EP.WORKERS:
                return {"count": 12 if params.get("site") else 80, "results": []}
            if path == EP.SITES:
                return {"count": 2, "results": self.SITES}
            if path == EP.ATTENDANCE_TODAY:
                return {"date": "2026-09-06", "present_count": 150, "absent_count": 50, "late_count": 7}
            if path == EP.ATTENDANCE_DAYS:
                if params.get("present"):
                    return {"count": 9, "results": []}
                if params.get("absent"):
                    return {"count": 3, "results": []}
                return {"count": 12, "results": []}
            if path == EP.ALERTS:
                return {"count": 2, "results": []}
            if path in (EP.ACCESS_EVENTS, EP.DEVICES, EP.VISITOR_REQUESTS):
                return {"count": 5, "results": []}
            raise AssertionError(f"Chemin non prévu par le test : {path}")
        return handler

    def test_source_absente_reste_disconnected(self):
        data = shield.fetch_hr_kpis()
        self.assertEqual(data["status"], "disconnected")
        self.assertTrue(all(k["value"] is None for k in data["kpis"]))
        self.assertEqual(data["by_site"], {"status": "disconnected", "sites": []})

    def test_source_non_connectee_reste_disconnected(self):
        self._source(status=SourceStatus.CONFIGURED)
        self.assertEqual(shield.fetch_hr_kpis()["status"], "disconnected")

    def test_kpis_rh_et_taux_calcule(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._routes()):
            data = shield.fetch_hr_kpis()
        kpis = {k["key"]: k for k in data["kpis"]}
        self.assertEqual(data["status"], "connected")
        self.assertEqual(kpis["employes"]["value"], 120)
        self.assertEqual(kpis["ouvriers"]["value"], 80)
        self.assertEqual(kpis["effectif_total"]["value"], 200)
        self.assertEqual(kpis["taux_presence"]["value"], 75.0)   # 150 / (150+50)
        self.assertEqual(kpis["taux_presence"]["level"], "computed")
        self.assertTrue(kpis["taux_presence"]["formula"])

    def test_effectif_employes_par_site_reste_unknown(self):
        """Shield n'expose aucun filtre `site` sur les employés : on ne l'invente pas."""
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._routes()):
            row = shield.fetch_hr_kpis()["by_site"]["sites"][0]
        self.assertIsNone(row["employees"])
        self.assertEqual(row["employees_status"], "unknown")
        self.assertIsNone(row["total"])
        self.assertEqual(row["total_status"], "unknown")
        self.assertIn("filtre par site", row["employees_reason"])

    def test_panne_partielle_rend_partial(self):
        self._source()
        def routes(path, params=None, **kw):
            if path == EP.ATTENDANCE_TODAY:
                raise ShieldError("timeout", "Délai dépassé")
            return self._routes()(path, params, **kw)
        with patch.object(ShieldClient, "get_json", side_effect=routes):
            data = shield.fetch_hr_kpis()
        kpis = {k["key"]: k for k in data["kpis"]}
        self.assertEqual(data["status"], "partial")
        self.assertEqual(kpis["employes"]["status"], "connected")
        self.assertEqual(kpis["presents"]["status"], "error")
        self.assertIsNone(kpis["presents"]["value"], "une mesure en échec ne doit porter aucun chiffre")

    def test_shield_totalement_indisponible_rend_error(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=ShieldError("network", "injoignable")):
            data = shield.fetch_hr_kpis()
        self.assertEqual(data["status"], "error")
        self.assertTrue(all(k["value"] is None for k in data["kpis"]))

    def test_zero_reel_conserve(self):
        self._source()
        def routes(path, params=None, **kw):
            if path == EP.ATTENDANCE_TODAY:
                return {"present_count": 0, "absent_count": 0, "late_count": 0}
            return self._routes()(path, params, **kw)
        with patch.object(ShieldClient, "get_json", side_effect=routes):
            kpis = {k["key"]: k for k in shield.fetch_hr_kpis()["kpis"]}
        self.assertEqual(kpis["presents"]["value"], 0)
        self.assertEqual(kpis["presents"]["status"], "connected")
        # 0 présent ET 0 absent : le taux est indéterminable, pas 0 %.
        self.assertIsNone(kpis["taux_presence"]["value"])

    def test_aucun_site_publie(self):
        self._source()
        def routes(path, params=None, **kw):
            if path == EP.SITES:
                return {"count": 0, "results": []}
            return self._routes()(path, params, **kw)
        with patch.object(ShieldClient, "get_json", side_effect=routes):
            by_site = shield.fetch_hr_kpis()["by_site"]
        self.assertEqual(by_site["status"], "disconnected")
        self.assertEqual(by_site["sites"], [])

    def test_securite_kpis(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._routes()):
            data = shield.fetch_security_kpis()
        kpis = {k["key"]: k for k in data["kpis"]}
        self.assertEqual(kpis["alertes_critiques"]["value"], 2)
        self.assertEqual(kpis["terminaux_hs"]["value"], 15)   # 5 inactifs + 5 maintenance + 5 perdus
        self.assertEqual(kpis["terminaux_hs"]["level"], "computed")

    def test_overview_reste_court(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._routes()):
            data = shield.fetch_overview_kpis()
        keys = [k["key"] for k in data["kpis"]]
        self.assertEqual(keys, ["workforce", "presents", "sites_actifs", "alertes_critiques"])
        self.assertEqual({k["key"]: k["value"] for k in data["kpis"]}["workforce"], 200)

    def test_insights_deterministes_et_justifies(self):
        self._source()
        def routes(path, params=None, **kw):
            if path == EP.ATTENDANCE_TODAY:
                return {"present_count": 60, "absent_count": 40, "late_count": 5}  # 60 % < seuil
            return self._routes()(path, params, **kw)
        with patch.object(ShieldClient, "get_json", side_effect=routes):
            insights = shield.fetch_hr_kpis()["insights"]
        self.assertTrue(insights, "un taux sous le seuil doit produire un constat")
        first = insights[0]
        self.assertEqual(first["severity"], "critical")
        self.assertIn("60", first["finding"])       # le constat cite la mesure
        self.assertTrue(first["formula"])           # et la façon dont elle est obtenue
        self.assertTrue(first["source"])
        self.assertTrue(first["period"])

    def test_aucun_insight_sans_donnee(self):
        """Ne rien avoir à dire est une information ; en inventer une ne l'est pas."""
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=ShieldError("network", "ko")):
            self.assertEqual(shield.fetch_hr_kpis()["insights"], [])

    def test_healthcheck(self):
        self._source()
        with patch.object(ShieldClient, "get_json", return_value={"count": 1}):
            self.assertTrue(shield.shield_health()["reachable"])
        with patch.object(ShieldClient, "get_json", side_effect=ShieldError("auth", "refus", 403)):
            health = shield.shield_health()
        self.assertFalse(health["reachable"])
        self.assertEqual(health["status"], "error")


class ShieldApiEndpointsTest(APITestCase):
    """Les trois endpoints exposés à React exigent une authentification."""

    def setUp(self):
        self.user = User.objects.create_user(username="rh2", password="x", email="rh2@k.co")

    def test_authentification_requise(self):
        for path in ("hr-kpi", "security", "overview", "health"):
            self.assertEqual(self.client.get(f"{BASE}/shield/{path}/").status_code, 401, path)

    def test_reponses_gouvernees_sans_source(self):
        self.client.force_authenticate(self.user)
        for path in ("hr-kpi", "security", "overview"):
            body = self.client.get(f"{BASE}/shield/{path}/").json()
            self.assertEqual(body["status"], "disconnected", path)
            self.assertTrue(all(k["value"] is None for k in body["kpis"]), path)


class ShieldRulesTest(TestCase):
    """Formules centralisées : ce qui distingue « zéro » de « indéterminable »."""

    def test_taux_presence(self):
        self.assertEqual(R.taux_presence(150, 50), 75.0)
        self.assertEqual(R.taux_presence(0, 10), 0.0, "0 présent sur 10 attendus vaut bien 0 %")

    def test_taux_indeterminable_sans_effectif(self):
        """Personne d'attendu : le taux n'existe pas, il ne vaut pas 0 %."""
        self.assertIsNone(R.taux_presence(0, 0))
        self.assertIsNone(R.taux_presence(None, 5))
        self.assertIsNone(R.taux_presence(5, None))

    def test_part_retards_rapportee_aux_presents(self):
        self.assertEqual(R.part_retards(3, 30), 10.0)
        self.assertIsNone(R.part_retards(3, 0), "aucun présent : la part de retards n'a pas de sens")

    def test_baisse_exige_assez_de_jours(self):
        courte = [{"date": f"2026-09-0{i}", "taux_presence": 90.0} for i in range(1, 4)]
        self.assertEqual(R.evaluer_tendance(courte, "Shield"), [],
                         "3 points ne suffisent pas à parler de tendance")

    def test_baisse_detectee_et_chiffree(self):
        points = [{"date": f"2026-09-{i:02d}", "taux_presence": 90.0} for i in range(1, 8)]
        points.append({"date": "2026-09-08", "taux_presence": 60.0})
        out = R.evaluer_tendance(points, "Shield")
        self.assertEqual(len(out), 1)
        self.assertIn("60.0", out[0]["finding"])
        self.assertIn("90.0", out[0]["finding"])
        self.assertTrue(out[0]["formula"])

    def test_pas_de_constat_sans_ecart(self):
        stables = [{"date": f"2026-09-{i:02d}", "taux_presence": 88.0} for i in range(1, 10)]
        self.assertEqual(R.evaluer_tendance(stables, "Shield"), [])


class ShieldAttendanceSeriesTest(TestCase):
    """Série journalière : UNE collecte paginée par indicateur, agrégée localement."""

    def _source(self):
        source = DataSource.objects.create(
            name="Kaydan Shield", slug="kaydan-shield",
            source_type=SourceType.KAYDAN_SHIELD, status=SourceStatus.CONNECTED)
        DataConnector.objects.create(source=source, base_url="https://shield.test",
                                     auth_method=AuthMethod.BEARER)
        return source

    def _records(self, days=7, present=4, absent=1, late=1, site=1):
        """Enregistrements AttendanceDay, à la forme réelle du schéma Shield."""
        today = timezone.localdate()
        out = {"present": [], "absent": [], "late": []}
        kinds = ("employee", "worker")
        for offset in range(days):
            date = (today - timedelta(days=offset)).isoformat()
            for flag, n in (("present", present), ("absent", absent), ("late", late)):
                for i in range(n):
                    out[flag].append({"id": f"{flag}-{date}-{i}", "date": date, "site": site,
                                      "site_name": "Riviera", "holder_kind": kinds[i % 2]})
        return out

    def _api(self, records, fail_flag=None):
        """Fausse API paginée : count / next / results, comme le fait DRF."""
        def handler(path, params=None, **kw):
            params = params or {}
            if path != EP.ATTENDANCE_DAYS:
                raise AssertionError(f"La série ne doit lire que /attendance/days/, pas {path}")
            flag = next((f for f in ("present", "absent", "late") if params.get(f)), None)
            if flag is None:
                raise AssertionError("Toute lecture de période doit porter un indicateur")
            if flag == fail_flag:
                raise ShieldError("timeout", "Délai dépassé")
            rows = sorted(records[flag], key=lambda r: r["date"], reverse=True)
            offset, limit = int(params.get("offset", 0)), int(params.get("limit", 200))
            page = rows[offset:offset + limit]
            return {"count": len(rows), "next": None if offset + limit >= len(rows) else "?",
                    "results": page}
        return handler

    def test_serie_7_jours_trois_lectures_seulement(self):
        self._source()
        with patch.object(ShieldClient, "get_json",
                          side_effect=self._api(self._records(days=7, present=4, absent=1))) as calls:
            data = shield.fetch_attendance_series(7)
        self.assertEqual(data["status"], "connected")
        self.assertEqual(len(data["points"]), 7)
        self.assertEqual(data["points"][0]["present"], 4)
        self.assertEqual(data["points"][0]["taux_presence"], 80.0)   # 4 / (4+1)
        self.assertEqual(calls.call_count, 3,
                         f"3 lectures paginées attendues, {calls.call_count} obtenues")

    def test_serie_30_jours_ne_coute_pas_plus(self):
        self._source()
        with patch.object(ShieldClient, "get_json",
                          side_effect=self._api(self._records(days=30, present=4, absent=1))) as calls:
            data = shield.fetch_attendance_series(30)
        self.assertEqual(len(data["points"]), 30)
        self.assertEqual(calls.call_count, 3, "30 jours ne doivent pas coûter plus que 7")

    def test_pagination_reelle_sur_gros_volume(self):
        self._source()
        with patch.object(ShieldClient, "get_json",
                          side_effect=self._api(self._records(days=30, present=20, absent=3))) as calls:
            data = shield.fetch_attendance_series(30)
        self.assertEqual(data["status"], "connected")
        self.assertEqual(data["points"][0]["present"], 20)
        self.assertEqual(calls.call_count, 5, "600 présents = 3 pages, + 1 absent + 1 retard")

    def test_fenetre_non_supportee_repliee(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._api(self._records(days=30))):
            self.assertEqual(shield.fetch_attendance_series(90)["days"], R.MAX_JOURS)

    def test_indicateur_en_echec_rend_la_serie_inconnue(self):
        """Sans les absents, aucun taux n'est calculable : on ne devine pas."""
        self._source()
        with patch.object(ShieldClient, "get_json",
                          side_effect=self._api(self._records(days=7), fail_flag="absent")):
            data = shield.fetch_attendance_series(7)
        self.assertEqual(data["status"], "error")
        self.assertTrue(all(p["status"] == "unknown" for p in data["points"]))
        self.assertIn("absent", data["detail"])

    def test_jour_sans_enregistrement_vaut_zero(self):
        """Journée couverte par la collecte mais sans ligne : 0 mesuré, pas unknown."""
        self._source()
        records = self._records(days=7)
        cible = (timezone.localdate() - timedelta(days=3)).isoformat()
        for flag in ("present", "absent", "late"):
            records[flag] = [r for r in records[flag] if r["date"] != cible]
        with patch.object(ShieldClient, "get_json", side_effect=self._api(records)):
            data = shield.fetch_attendance_series(7)
        point = next(p for p in data["points"] if p["date"] == cible)
        self.assertEqual(point["present"], 0)
        self.assertEqual(point["status"], "measured")
        self.assertIsNone(point["taux_presence"], "0 présent et 0 absent : le taux n'existe pas")

    def test_troncature_rend_les_jours_anciens_inconnus(self):
        """Au-delà du plafond de collecte, on ignore — on ne compte pas 0."""
        self._source()
        records = self._records(days=30, present=300, absent=1, late=1)
        def handler(path, params=None, **kw):
            params = params or {}
            flag = next(f for f in ("present", "absent", "late") if params.get(f))
            rows = sorted(records[flag], key=lambda r: r["date"], reverse=True)
            offset, limit = int(params.get("offset", 0)), int(params.get("limit", 200))
            return {"count": len(rows), "next": "?", "results": rows[offset:offset + limit]}
        with patch.object(ShieldClient, "get_json", side_effect=handler):
            data = shield.fetch_attendance_series(30)
        self.assertEqual(data["status"], "partial")
        self.assertIn("plafond", data["detail"])
        self.assertEqual(data["points"][0]["status"], "unknown", "les jours anciens sont inconnus")
        self.assertEqual(data["points"][-1]["status"], "measured", "les jours récents restent fiables")

    def test_serie_totalement_indisponible(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=ShieldError("network", "ko")):
            data = shield.fetch_attendance_series(7)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["insights"], [])

    def test_serie_sans_source(self):
        self.assertEqual(shield.fetch_attendance_series(7)["status"], "disconnected")

    def test_endpoint_serie_exige_authentification(self):
        self.assertEqual(APIClient().get(f"{BASE}/shield/attendance-series/?days=7").status_code, 401)


class ShieldAggregationTest(TestCase):
    """by_site et by_kind dérivés de la MÊME collecte : plus d'appels par site."""

    SITES = [{"id": 1, "code": "KRE", "name": "Riviera", "type": "site", "status": "active"},
             {"id": 2, "code": "SIEGE", "name": "Siege", "type": "office", "status": "active"}]

    def _source(self):
        source = DataSource.objects.create(
            name="Kaydan Shield", slug="kaydan-shield",
            source_type=SourceType.KAYDAN_SHIELD, status=SourceStatus.CONNECTED)
        DataConnector.objects.create(source=source, base_url="https://shield.test",
                                     auth_method=AuthMethod.BEARER)
        return source

    def _api(self):
        today = timezone.localdate().isoformat()
        def rec(site, kind, n, tag):
            return [{"id": f"{tag}{site}{kind}{i}", "date": today, "site": site,
                     "holder_kind": kind} for i in range(n)]
        present = rec(1, "employee", 6, "p") + rec(1, "worker", 3, "p") + rec(2, "employee", 10, "p")
        absent = rec(1, "worker", 3, "a") + rec(2, "employee", 2, "a")
        late = rec(1, "worker", 2, "l")
        def handler(path, params=None, **kw):
            params = params or {}
            if path == EP.ATTENDANCE_DAYS:
                flag = next(f for f in ("present", "absent", "late") if params.get(f))
                rows = {"present": present, "absent": absent, "late": late}[flag]
                return {"count": len(rows), "next": None, "results": rows}
            if path == EP.SITES:
                return {"count": 2, "next": None, "results": self.SITES}
            if path == EP.EMPLOYEES:
                return {"count": 214, "next": None, "results": []}
            if path == EP.WORKERS:
                return {"count": 12 if params.get("site") else 96, "next": None, "results": []}
            if path == EP.ALERTS:
                return {"count": 1, "next": None, "results": []}
            if path == EP.ATTENDANCE_TODAY:
                return {"present_count": 19, "absent_count": 5, "late_count": 2}
            raise AssertionError(path)
        return handler

    def test_by_site_derive_de_la_periode(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._api()):
            rows = {r["site"]["code"]: r for r in shield.fetch_hr_kpis()["by_site"]["sites"]}
        self.assertEqual(rows["KRE"]["present"], 9)      # 6 employés + 3 ouvriers
        self.assertEqual(rows["KRE"]["absent"], 3)
        self.assertEqual(rows["KRE"]["late"], 2)
        self.assertEqual(rows["KRE"]["attendance_rate"], 75.0)
        self.assertEqual(rows["SIEGE"]["present"], 10)
        self.assertEqual(rows["SIEGE"]["late"], 0, "aucun retard vaut 0, pas unknown")
        self.assertIsNone(rows["KRE"]["employees"])
        self.assertEqual(rows["KRE"]["employees_status"], "unknown")
        self.assertEqual(rows["KRE"]["total_status"], "unknown")

    def test_by_kind_derive_de_la_meme_collecte(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._api()):
            by_kind = shield.fetch_hr_kpis()["by_kind"]
        self.assertEqual(by_kind["employees"], 16)   # 6 + 10
        self.assertEqual(by_kind["workers"], 3)
        self.assertEqual(by_kind["total"], 19)
        self.assertEqual(by_kind["employees_share"], 84.2)

    def test_cout_en_appels_borne(self):
        """4 compteurs + 1 liste de sites + 3 lectures de période + 2 par site."""
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._api()) as calls:
            shield.fetch_hr_kpis()
        self.assertLessEqual(calls.call_count, 12,
                             f"coût trop élevé : {calls.call_count} appels pour 2 sites")


class ShieldObservabilityTest(TestCase):
    """Compteurs d'usage : ce qu'on mesure, et ce qu'on ne journalise jamais."""

    def _client(self):
        return ShieldClient("https://shield.test", {"Authorization": "Bearer secret-xyz"}, timeout=1)

    def test_compteurs_appels_et_cache(self):
        client = self._client()
        with patch.object(ShieldClient, "_fetch", return_value={"count": 3}) as fetch:
            client.get_json("/api/v1/sites/sites/")
            client.get_json("/api/v1/sites/sites/")     # servi par le cache
        m = client.metrics.as_dict()
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(m["calls"], 1)
        self.assertEqual(m["cache_hits"], 1)
        self.assertEqual(m["cache_misses"], 1)
        self.assertEqual(m["by_path"]["/api/v1/sites/sites/"], 1)
        self.assertIsNotNone(m["last_sync"])

    def test_compteurs_retries_et_erreurs(self):
        client = self._client()
        with patch.object(ShieldClient, "_fetch",
                          side_effect=urllib.error.HTTPError("u", 503, "ko", {}, None)), patch("time.sleep"):
            with self.assertRaises(ShieldError):
                client.get_json("/api/v1/sites/sites/", use_cache=False)
        m = client.metrics.as_dict()
        self.assertEqual(m["retries"], 2, "3 tentatives = 2 reprises")
        self.assertEqual(m["errors"], {"http": 1})
        # Sur l'accumulateur brut, pas sur sa version arrondie au dixième : avec
        # `time.sleep` neutralisé, trois tentatives peuvent tenir sous 0,05 ms et
        # `round(..., 1)` rendait alors 0.0 — un échec dû à la machine, pas au code.
        self.assertGreater(client.metrics.duration_ms, 0)
        self.assertGreaterEqual(m["duration_ms"], 0)

    def test_aucun_secret_dans_les_metriques(self):
        client = self._client()
        with patch.object(ShieldClient, "_fetch", return_value={"count": 1}):
            client.get_json("/api/v1/employees/employees/", {"department": 7})
        dump = json.dumps(client.metrics.as_dict())
        self.assertNotIn("secret-xyz", dump)
        self.assertNotIn("Bearer", dump)
        # Le chemin est conservé, pas les filtres : un filtre peut porter un identifiant.
        self.assertNotIn("department", dump)

    def test_429_respecte_retry_after_et_est_qualifie(self):
        client = self._client()
        err = urllib.error.HTTPError("u", 429, "trop de requêtes", {"Retry-After": "2"}, None)
        with patch.object(ShieldClient, "_fetch", side_effect=err), patch("time.sleep") as dodo:
            with self.assertRaises(ShieldError) as ctx:
                client.get_json("/api/v1/sites/sites/", use_cache=False)
        self.assertEqual(ctx.exception.kind, "rate_limit")
        self.assertEqual(ctx.exception.status, 429)
        self.assertIn(2.0, [c.args[0] for c in dodo.call_args_list],
                      "le délai demandé par la source doit être respecté")

    def test_requetes_identiques_dedupliquees(self):
        """Deux widgets demandant la même donnée ne doivent produire qu'un appel."""
        import threading
        client = self._client()
        def lent(url):
            time.sleep(0.25)
            return {"count": 1}
        resultats = []
        with patch.object(ShieldClient, "_fetch", side_effect=lent) as fetch:
            def lire():
                resultats.append(client.get_json("/api/v1/sites/sites/"))
            premier = threading.Thread(target=lire)
            premier.start()
            time.sleep(0.05)          # le second arrive pendant que le premier est en vol
            second = threading.Thread(target=lire)
            second.start()
            premier.join(timeout=5); second.join(timeout=5)
        self.assertEqual(len(resultats), 2, "les deux appelants doivent obtenir la donnée")
        self.assertEqual(fetch.call_count, 1, "l'appel identique concurrent doit être mutualisé")


class IntegrationCentreTest(APITestCase):
    """Centre d'intégrations : création, test réel, secrets, santé consolidée."""

    def setUp(self):
        self.admin = User.objects.create_user(username="int-admin", password="x",
                                              email="a@k.co", role="ADMIN_INTEGRATION")
        self.lecteur = User.objects.create_user(username="dg-lecteur", password="x",
                                                email="d@k.co", role="DG_GROUP")

    # ── Le blocage constaté : un 403, pas une panne ──────────────────────────
    def test_role_insuffisant_donne_403_et_non_500(self):
        """Le centre est réservé : la cause doit être un refus explicite."""
        self.client.force_authenticate(self.lecteur)
        for path in ("sources/", "sources/health/"):
            resp = self.client.get(f"{BASE}/{path}")
            self.assertEqual(resp.status_code, 403, path)
            self.assertIn("administrateurs", resp.json()["detail"].lower())

    def test_non_authentifie_donne_401(self):
        self.assertEqual(self.client.get(f"{BASE}/sources/").status_code, 401)

    def test_admin_integration_accede(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"{BASE}/sources/").status_code, 200)

    # ── Création ─────────────────────────────────────────────────────────────
    def _creer(self, **overrides):
        self.client.force_authenticate(self.admin)
        payload = {"name": "Kaydan Shield", "slug": "kaydan-shield",
                   "source_type": "kaydan_shield", "environment": "production",
                   "target_module": "rh", **overrides}
        return self.client.post(f"{BASE}/sources/", payload, format="json")

    def test_creation_source_avec_environnement(self):
        resp = self._creer()
        self.assertEqual(resp.status_code, 201)
        source = DataSource.objects.get(slug="kaydan-shield")
        self.assertEqual(source.environment, "production")
        self.assertEqual(source.status, SourceStatus.CONFIGURED)
        # Le connecteur est créé d'office : pas d'écran de config orphelin.
        self.assertTrue(hasattr(source, "connector"))

    def test_types_sap_et_edw_acceptes(self):
        for code, stype in (("sap-fi", "sap"), ("mart-edw", "edw")):
            resp = self._creer(name=stype.upper(), slug=code, source_type=stype)
            self.assertEqual(resp.status_code, 201, f"{stype} refusé : {resp.content[:120]}")

    # ── Secrets ──────────────────────────────────────────────────────────────
    def test_secret_chiffre_et_jamais_renvoye_en_clair(self):
        self._creer()
        source = DataSource.objects.get(slug="kaydan-shield")
        self.client.force_authenticate(self.admin)
        resp = self.client.post(f"{BASE}/credentials/", {
            "connector": str(source.connector.id), "kind": "api_token",
            "label": "Jeton Shield", "secret": "jeton-tres-secret-123",
        }, format="json")
        self.assertEqual(resp.status_code, 201)
        # Ni dans la réponse de création…
        self.assertNotIn("jeton-tres-secret-123", resp.content.decode())
        # …ni dans la relecture, ni dans la source sérialisée.
        listing = self.client.get(f"{BASE}/credentials/?connector={source.connector.id}").content.decode()
        self.assertNotIn("jeton-tres-secret-123", listing)
        detail = self.client.get(f"{BASE}/sources/{source.id}/").content.decode()
        self.assertNotIn("jeton-tres-secret-123", detail)
        # Mais il est bien stocké, chiffré, et relisible par le connecteur.
        cred = ConnectorCredential.objects.get(connector=source.connector)
        self.assertNotIn("jeton-tres-secret-123", cred.secret_ciphertext)
        self.assertEqual(cred.secret, "jeton-tres-secret-123")

    # ── Test de connexion ────────────────────────────────────────────────────
    def test_test_connexion_shield_utilise_le_vrai_healthcheck(self):
        self._creer()
        source = DataSource.objects.get(slug="kaydan-shield")
        source.connector.base_url = "https://shield.test"
        source.connector.auth_method = AuthMethod.BEARER
        source.connector.save()
        self.client.force_authenticate(self.admin)

        with patch.object(ShieldClient, "get_json", return_value={"count": 3}):
            resp = self.client.post(f"{BASE}/sources/{source.id}/test-connection/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        source.connector.refresh_from_db()
        self.assertTrue(source.connector.last_test_ok)
        self.assertIsNotNone(source.connector.last_tested_at)
        self.assertIsNotNone(source.connector.last_latency_ms, "la latence doit être mesurée")

    def test_test_connexion_refus_shield_est_signale(self):
        """Un jeton refusé ne doit pas passer pour « hôte joignable »."""
        self._creer()
        source = DataSource.objects.get(slug="kaydan-shield")
        source.connector.base_url = "https://shield.test"
        source.connector.save()
        self.client.force_authenticate(self.admin)
        with patch.object(ShieldClient, "get_json",
                          side_effect=ShieldError("auth", "Accès refusé", 403)):
            body = self.client.post(f"{BASE}/sources/{source.id}/test-connection/").json()
        self.assertFalse(body["ok"])
        self.assertIn("auth", body["message"])
        source.refresh_from_db()
        self.assertEqual(source.status, SourceStatus.ERROR)

    def test_test_connexion_sans_url_echoue_avant_le_reseau(self):
        self._creer()
        source = DataSource.objects.get(slug="kaydan-shield")
        self.client.force_authenticate(self.admin)
        body = self.client.post(f"{BASE}/sources/{source.id}/test-connection/").json()
        self.assertFalse(body["ok"])
        self.assertIn("URL de base", body["message"])

    def test_odoo_exige_une_base_de_donnees(self):
        """Ne pas inventer l'API Odoo : sans `database`, la config est incomplète."""
        self._creer(name="Odoo", slug="odoo-rh", source_type="odoo_hr")
        source = DataSource.objects.get(slug="odoo-rh")
        source.connector.base_url = "https://odoo.test"
        source.connector.save()
        self.client.force_authenticate(self.admin)
        body = self.client.post(f"{BASE}/sources/{source.id}/test-connection/").json()
        self.assertFalse(body["ok"])
        self.assertIn("base de données Odoo", body["message"])

    # ── Désactivation ────────────────────────────────────────────────────────
    def test_desactivation_change_le_statut(self):
        self._creer()
        source = DataSource.objects.get(slug="kaydan-shield")
        self.client.force_authenticate(self.admin)
        body = self.client.post(f"{BASE}/sources/{source.id}/toggle-active/").json()
        self.assertFalse(body["is_active"])
        self.assertEqual(body["status"], SourceStatus.DISABLED)

    # ── Santé consolidée ─────────────────────────────────────────────────────
    def test_sante_globale_expose_partial_stale_et_latence(self):
        self._creer()
        self._creer(name="SAP FI", slug="sap-fi", source_type="sap")
        connectee = DataSource.objects.get(slug="kaydan-shield")
        connectee.status = SourceStatus.CONNECTED
        connectee.save()
        connectee.connector.last_tested_at = timezone.now()
        connectee.connector.last_latency_ms = 120
        connectee.connector.save()

        self.client.force_authenticate(self.admin)
        body = self.client.get(f"{BASE}/sources/health/").json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["connected"], 1)
        self.assertEqual(body["partial"], 1, "une source sur deux répond : le parc est partiel")
        self.assertEqual(body["stale"], 0)
        self.assertEqual(body["avg_latency_ms"], 120)

    def test_source_connectee_mais_non_testee_depuis_longtemps_est_perimee(self):
        self._creer()
        source = DataSource.objects.get(slug="kaydan-shield")
        source.status = SourceStatus.CONNECTED
        source.save()
        source.connector.last_tested_at = timezone.now() - timedelta(hours=48)
        source.connector.save()
        self.client.force_authenticate(self.admin)
        body = self.client.get(f"{BASE}/sources/health/").json()
        self.assertEqual(body["stale"], 1,
                         "connectée mais testée il y a 48 h : à ne pas présenter comme fiable")

    def test_liste_expose_les_champs_de_la_carte(self):
        self._creer()
        self.client.force_authenticate(self.admin)
        row = self.client.get(f"{BASE}/sources/").json()[0]
        for champ in ("environment", "environment_label", "base_url", "last_tested_at",
                      "last_latency_ms", "last_sync_at", "recent_errors", "status_label"):
            self.assertIn(champ, row, f"la carte source a besoin de `{champ}`")


class AssistantCreationTest(APITestCase):
    """Création d'une source depuis l'assistant en trois étapes.

    Le symptôme rapporté en production — « Échec de création (backend indisponible
    ou droits insuffisants) » puis une source Shield enregistrée en « API REST /
    Autre » — recouvrait deux causes distinctes : un refus de permission d'un côté,
    une perte silencieuse de champ de l'autre. Les tests ci-dessous les séparent.
    """

    def setUp(self):
        self.admin = User.objects.create_user(username="wiz-admin", password="x",
                                              email="w@k.co", role="ADMIN_INTEGRATION")
        # Compte affiché « Super Admin » dans l'UI : superutilisateur Django,
        # portant un rôle métier qui, seul, ne donnerait pas accès au centre.
        self.super_admin = User.objects.create_superuser(username="wiz-super", password="x",
                                                         email="s@k.co")
        self.super_admin.role = "DG_GROUP"
        self.super_admin.save(update_fields=["role"])
        self.dg = User.objects.create_user(username="wiz-dg", password="x",
                                           email="g@k.co", role="DG_GROUP")

    def _post(self, user, **overrides):
        self.client.force_authenticate(user)
        payload = {"name": "Kaydan Shield", "slug": "kaydan-shield",
                   "source_type": "kaydan_shield", "environment": "production",
                   "target_module": "rh", **overrides}
        return self.client.post(f"{BASE}/sources/", payload, format="json")

    # ── Permissions : qui peut créer ─────────────────────────────────────────
    def test_super_administrateur_peut_creer(self):
        self.assertEqual(self._post(self.super_admin).status_code, 201)

    def test_admin_integration_peut_creer(self):
        self.assertEqual(self._post(self.admin).status_code, 201)

    def test_role_metier_seul_refuse_avec_un_403_explicite(self):
        """Un DG non superutilisateur est refusé — et on doit pouvoir le lire.

        C'est le cas qui produisait « backend indisponible » : le refus était
        présenté comme une panne, envoyant chercher un problème d'infrastructure
        là où il manquait un rôle.
        """
        resp = self._post(self.dg)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("administrateurs", resp.json()["detail"].lower())
        self.assertFalse(DataSource.objects.filter(slug="kaydan-shield").exists())

    # ── Le champ perdu ───────────────────────────────────────────────────────
    def test_environnement_non_defaut_persiste_et_revient_dans_la_reponse(self):
        """`environment` absent du sérialiseur était ignoré SANS erreur.

        La requête répondait 201, l'utilisateur voyait « Recette » à l'écran, et
        la source repartait en production. Un 201 ne prouve donc rien : il faut
        vérifier la valeur relue.
        """
        resp = self._post(self.admin, environment="staging")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["environment"], "staging")
        self.assertEqual(DataSource.objects.get(slug="kaydan-shield").environment, "staging")

    def test_type_et_module_choisis_ne_sont_pas_remplaces(self):
        """La source Shield s'enregistrait en « API REST / Autre »."""
        resp = self._post(self.admin, source_type="kaydan_shield", target_module="rh")
        self.assertEqual(resp.status_code, 201)
        source = DataSource.objects.get(slug="kaydan-shield")
        self.assertEqual(source.source_type, SourceType.KAYDAN_SHIELD)
        self.assertEqual(source.target_module, "rh")
        self.assertEqual(resp.json()["source_type"], "kaydan_shield")
        self.assertEqual(resp.json()["target_module"], "rh")

    def test_creation_odoo_et_rest(self):
        for slug, stype, module in (("odoo-hr", "odoo_hr", "rh"), ("crm-rest", "rest", "commercial")):
            resp = self._post(self.admin, name=slug, slug=slug, source_type=stype, target_module=module)
            self.assertEqual(resp.status_code, 201, f"{stype} refusé : {resp.content[:160]}")
            source = DataSource.objects.get(slug=slug)
            self.assertEqual(source.source_type, stype)
            self.assertEqual(source.target_module, module)

    # ── Erreurs de saisie : un 400 nommant le champ fautif ───────────────────
    def test_slug_deja_pris_donne_400_en_nommant_le_champ(self):
        self.assertEqual(self._post(self.admin).status_code, 201)
        resp = self._post(self.admin)
        self.assertEqual(resp.status_code, 400)
        # L'UI recopie ces clés : sans elles, l'utilisateur ne sait pas quoi corriger.
        self.assertIn("slug", resp.json())

    def test_type_inconnu_donne_400_et_non_500(self):
        resp = self._post(self.admin, source_type="nimporte_quoi")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("source_type", resp.json())

    # ── Mode dégradé ─────────────────────────────────────────────────────────
    def test_mode_demo_desactive_par_defaut(self):
        """Sans demande explicite, aucune source ne part en mode simulé."""
        self.assertEqual(self._post(self.admin).status_code, 201)
        self.assertFalse(DataSource.objects.get(slug="kaydan-shield").demo_mode)

    def test_source_non_connectee_reste_deconnectee_et_ne_synchronise_pas(self):
        self._post(self.admin, slug="sans-url", name="Sans URL")
        source = DataSource.objects.get(slug="sans-url")
        self.client.force_authenticate(self.admin)

        test = self.client.post(f"{BASE}/sources/{source.id}/test-connection/")
        self.assertEqual(test.status_code, 200)
        self.assertFalse(test.json()["ok"])
        source.refresh_from_db()
        self.assertEqual(source.status, SourceStatus.ERROR)

        # Mode démo désactivé : la synchronisation refuse plutôt que d'inventer.
        sync = self.client.post(f"{BASE}/sources/{source.id}/sync-now/")
        self.assertEqual(sync.json()["status"], "error")
        self.assertIn("non connectée", sync.json()["message"])

    # ── Retour du test affiché par l'assistant ───────────────────────────────
    def test_test_connexion_renvoie_la_latence_et_la_date(self):
        """L'étape 3 annonce « connecté en N ms » : la mesure vient du serveur."""
        self._post(self.admin)
        source = DataSource.objects.get(slug="kaydan-shield")
        source.connector.base_url = "https://api.kaydanshield.com/api/v1"
        source.connector.save(update_fields=["base_url"])
        self.client.force_authenticate(self.admin)

        with patch.object(shield.ShieldClient, "healthcheck", return_value=(True, "Shield joignable")):
            resp = self.client.post(f"{BASE}/sources/{source.id}/test-connection/")

        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertIsNotNone(body["tested_at"])
        self.assertIsInstance(body["latency_ms"], int)

    # ── Le parcours complet de l'assistant ───────────────────────────────────
    def test_parcours_assistant_de_bout_en_bout(self):
        """Rejoue les quatre appels que l'assistant enchaîne à l'étape 3.

        Créer la source, configurer le connecteur, déposer le secret, tester.
        Chaque appel est vérifié séparément ailleurs ; ce test garantit que la
        chaîne tient ensemble et qu'aucun maillon ne perd ce que le précédent a posé.
        """
        creation = self._post(self.admin, environment="staging")
        self.assertEqual(creation.status_code, 201)
        connector_id = creation.json()["connector"]["id"]

        patch_cnx = self.client.patch(
            f"{BASE}/connectors/{connector_id}/",
            {"base_url": "https://api.kaydanshield.com/api/v1", "auth_method": "bearer", "config": {}},
            format="json",
        )
        self.assertEqual(patch_cnx.status_code, 200)

        cred = self.client.post(f"{BASE}/credentials/", {
            "connector": connector_id, "kind": "api_token",
            "label": "Token API Shield (Bearer)", "secret": "jeton-assistant-999",
        }, format="json")
        self.assertEqual(cred.status_code, 201)
        self.assertNotIn("jeton-assistant-999", cred.content.decode())

        source = DataSource.objects.get(slug="kaydan-shield")
        with patch.object(shield.ShieldClient, "healthcheck", return_value=(True, "Shield joignable")):
            verdict = self.client.post(f"{BASE}/sources/{source.id}/test-connection/")
        self.assertTrue(verdict.json()["ok"])

        # Ce que la fiche source affichera juste après la redirection.
        detail = self.client.get(f"{BASE}/sources/{source.id}/").json()
        self.assertEqual(detail["status"], SourceStatus.CONNECTED)
        self.assertEqual(detail["environment"], "staging")
        self.assertEqual(detail["source_type"], "kaydan_shield")
        self.assertFalse(detail["demo_mode"])
        self.assertEqual(detail["connector"]["base_url"], "https://api.kaydanshield.com/api/v1")
        self.assertIsNotNone(detail["connector"]["last_latency_ms"])
        self.assertTrue(detail["connector"]["credentials"][0]["is_set"])
        self.assertNotIn("jeton-assistant-999", json.dumps(detail))
