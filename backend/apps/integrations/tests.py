"""Tests du control-plane d'intégration et du connecteur Kaydan Shield."""

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

    def test_by_site_utilise_les_vraies_relations(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._routes()):
            by_site = shield.fetch_hr_kpis()["by_site"]
        self.assertEqual(by_site["status"], "connected")
        row = by_site["sites"][0]
        self.assertEqual(row["site"]["code"], "KRE-01")
        self.assertEqual(row["workers"], 12)      # /ouvriers/workers/?site=1
        self.assertEqual(row["present"], 9)       # /attendance/days/?site=1&present=true
        self.assertEqual(row["absent"], 3)
        self.assertEqual(row["attendance_rate"], 75.0)
        self.assertEqual(row["alerts"], 2)

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
    """Série journalière : jours manquants, vrais zéros, ventilation documentée."""

    def _source(self):
        source = DataSource.objects.create(
            name="Kaydan Shield", slug="kaydan-shield",
            source_type=SourceType.KAYDAN_SHIELD, status=SourceStatus.CONNECTED)
        DataConnector.objects.create(source=source, base_url="https://shield.test",
                                     auth_method=AuthMethod.BEARER)
        return source

    def _counts(self, present=40, absent=10, late=4):
        def handler(path, params=None, **kw):
            params = params or {}
            if path != EP.ATTENDANCE_DAYS:
                raise AssertionError(f"La série ne doit interroger que /attendance/days/, pas {path}")
            if params.get("present"):
                return {"count": present, "results": []}
            if params.get("absent"):
                return {"count": absent, "results": []}
            if params.get("late"):
                return {"count": late, "results": []}
            return {"count": present + absent, "results": []}
        return handler

    def test_serie_7_jours(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._counts()):
            data = shield.fetch_attendance_series(7)
        self.assertEqual(data["status"], "connected")
        self.assertEqual(data["days"], 7)
        self.assertEqual(len(data["points"]), 7)
        self.assertEqual(data["points"][0]["taux_presence"], 80.0)   # 40 / 50
        self.assertTrue(all(p["status"] == "measured" for p in data["points"]))

    def test_serie_30_jours_par_defaut(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._counts()):
            data = shield.fetch_attendance_series(30)
        self.assertEqual(len(data["points"]), 30)
        dates = [p["date"] for p in data["points"]]
        self.assertEqual(dates, sorted(dates), "la série doit être chronologique")

    def test_fenetre_non_supportee_repliee(self):
        """90 jours coûterait 270 appels : la fenêtre est ramenée au maximum tenable."""
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._counts()):
            data = shield.fetch_attendance_series(90)
        self.assertEqual(data["days"], R.MAX_JOURS)

    def test_jour_manquant_reste_unknown(self):
        """Un jour dont la mesure échoue vaut `unknown`, jamais 0."""
        self._source()
        cible = (timezone.localdate() - timedelta(days=3)).isoformat()
        base = self._counts()
        def handler(path, params=None, **kw):
            if (params or {}).get("date") == cible:
                raise ShieldError("timeout", "Délai dépassé")
            return base(path, params, **kw)
        with patch.object(ShieldClient, "get_json", side_effect=handler):
            data = shield.fetch_attendance_series(7)
        trou = next(p for p in data["points"] if p["date"] == cible)
        self.assertEqual(trou["status"], "unknown")
        self.assertIsNone(trou["present"])
        self.assertIsNone(trou["taux_presence"])
        self.assertEqual(data["status"], "partial", "une série trouée ne peut pas être 'connected'")
        self.assertEqual(data["measured_days"], 6)

    def test_zero_reel_conserve_dans_la_serie(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=self._counts(present=0, absent=12, late=0)):
            point = shield.fetch_attendance_series(7)["points"][0]
        self.assertEqual(point["present"], 0)
        self.assertEqual(point["taux_presence"], 0.0, "0 présent sur 12 attendus vaut 0 %, pas null")
        self.assertEqual(point["status"], "measured")

    def test_serie_totalement_indisponible(self):
        self._source()
        with patch.object(ShieldClient, "get_json", side_effect=ShieldError("network", "ko")):
            data = shield.fetch_attendance_series(7)
        self.assertEqual(data["status"], "error")
        self.assertTrue(all(p["status"] == "unknown" for p in data["points"]))
        self.assertEqual(data["insights"], [])

    def test_serie_sans_source(self):
        data = shield.fetch_attendance_series(7)
        self.assertEqual(data["status"], "disconnected")
        self.assertEqual(data["points"], [])

    def test_ventilation_par_holder_kind(self):
        """`holder_kind` est la seule ventilation documentée (employee | worker)."""
        self._source()
        def handler(path, params=None, **kw):
            params = params or {}
            if path == EP.ATTENDANCE_DAYS and params.get("holder_kind"):
                return {"count": 30 if params["holder_kind"] == "employee" else 20, "results": []}
            if path == EP.ATTENDANCE_DAYS:
                return {"count": 5, "results": []}
            if path == EP.EMPLOYEES:
                return {"count": 120, "results": []}
            if path == EP.WORKERS:
                return {"count": 80, "results": []}
            if path == EP.SITES:
                return {"count": 0, "results": []}
            if path == EP.ATTENDANCE_TODAY:
                return {"present_count": 50, "absent_count": 10, "late_count": 2}
            raise AssertionError(path)
        with patch.object(ShieldClient, "get_json", side_effect=handler):
            by_kind = shield.fetch_hr_kpis()["by_kind"]
        self.assertEqual(by_kind["status"], "connected")
        self.assertEqual(by_kind["employees"], 30)
        self.assertEqual(by_kind["workers"], 20)
        self.assertEqual(by_kind["total"], 50)
        self.assertEqual(by_kind["employees_share"], 60.0)
        self.assertEqual(by_kind["workers_share"], 40.0)

    def test_by_site_porte_les_retards_et_un_drilldown(self):
        self._source()
        def handler(path, params=None, **kw):
            params = params or {}
            if path == EP.SITES:
                return {"count": 1, "results": [{"id": 1, "code": "KRE", "name": "Riviera",
                                                 "type": "site", "status": "active"}]}
            if path == EP.ATTENDANCE_DAYS:
                if params.get("late"):
                    return {"count": 4, "results": []}
                if params.get("present"):
                    return {"count": 20, "results": []}
                if params.get("absent"):
                    return {"count": 5, "results": []}
                return {"count": 25, "results": []}
            if path in (EP.EMPLOYEES, EP.WORKERS):
                return {"count": 10, "results": []}
            if path == EP.ALERTS:
                return {"count": 0, "results": []}
            if path == EP.ATTENDANCE_TODAY:
                return {"present_count": 20, "absent_count": 5, "late_count": 4}
            raise AssertionError(path)
        with patch.object(ShieldClient, "get_json", side_effect=handler):
            row = shield.fetch_hr_kpis()["by_site"]["sites"][0]
        self.assertEqual(row["late"], 4)
        self.assertEqual(row["attendance_rate"], 80.0)
        self.assertEqual(row["alerts"], 0, "0 alerte est une mesure, pas une absence de mesure")
        self.assertEqual(row["drilldown_url"], "/dashboard/capital-humain/presence")
        # L'effectif employés par site reste hors de portée de l'API Shield.
        self.assertIsNone(row["employees"])
        self.assertEqual(row["employees_status"], "unknown")
        self.assertEqual(row["total_status"], "unknown")

    def test_endpoint_serie_exige_authentification(self):
        client = APIClient()
        self.assertEqual(client.get(f"{BASE}/shield/attendance-series/?days=7").status_code, 401)
