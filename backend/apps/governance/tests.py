"""Tests d'API governance : catalogue + KPI RH avec RBAC par périmètre.

Exécution : python manage.py test apps
La passerelle mart est substituée par une implémentation mémoire (pas de Postgres).
"""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from k_insight.kpi.hr import Employee, Payslip
from k_insight.kpi.hr_mart import build_hr_kpi_rows

from apps.audit.models import AccessLog
from apps.governance import gateway
from apps.governance.gateway import InMemoryMartGateway
from apps.organizations.models import Subsidiary

User = get_user_model()

# Jeu de données (miroir des tests du domaine pur).
EMP = [
    Employee("E1", "KRE", "OPS", date(2025, 1, 1)),
    Employee("E2", "KRE", "OPS", date(2025, 6, 1), date(2026, 3, 15)),
    Employee("E3", "KSH", "SEC", date(2024, 3, 1)),
    Employee("E4", "KSH", "SEC", date(2026, 2, 1)),
    Employee("E5", "KRE", "FIN", date(2023, 1, 1), date(2026, 1, 10)),
]
PAY = [
    Payslip("E1", "KRE", "OPS", date(2026, 1, 1), 300_000),
    Payslip("E2", "KRE", "OPS", date(2026, 1, 1), 250_000),
    Payslip("E3", "KSH", "SEC", date(2026, 1, 1), 200_000),
    Payslip("E5", "KRE", "FIN", date(2026, 1, 1), 500_000),
    Payslip("E1", "KRE", "OPS", date(2026, 2, 1), 300_000),
    Payslip("E2", "KRE", "OPS", date(2026, 2, 1), 250_000),
    Payslip("E3", "KSH", "SEC", date(2026, 2, 1), 200_000),
    Payslip("E4", "KSH", "SEC", date(2026, 2, 1), 180_000),
    Payslip("E1", "KRE", "OPS", date(2026, 3, 1), 300_000),
    Payslip("E2", "KRE", "OPS", date(2026, 3, 1), 250_000),
    Payslip("E3", "KSH", "SEC", date(2026, 3, 1), 200_000),
    Payslip("E4", "KSH", "SEC", date(2026, 3, 1), 180_000),
]


class FailingMartGateway:
    def fetch_hr_kpi(self):
        raise RuntimeError("EDW unavailable")


class GovernanceApiTest(TestCase):
    def setUp(self):
        gateway.set_mart_gateway(InMemoryMartGateway(build_hr_kpi_rows(EMP, PAY)))
        self.kre = Subsidiary.objects.create(code="KRE", name="K-Express")
        self.ksh = Subsidiary.objects.create(code="KSH", name="K-Shield")
        Subsidiary.objects.create(code="MYK", name="MyKaydan")

        self.dg = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh_kre", password="x", role="DRH")
        self.drh_kre.subsidiaries.add(self.kre)

        self.client = APIClient()

    def tearDown(self):
        gateway.set_mart_gateway(None)

    def test_catalog_retourne_les_metriques_rh(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/catalog/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 6)
        keys = {m["key"] for m in resp.data["metrics"]}
        self.assertIn("hr.turnover_rate", keys)

    def test_hr_kpi_groupe_voit_tout(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/kpi/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["scope"], "GROUP")
        self.assertEqual(resp.data["metrics"]["hr.payroll_mass"]["value"], 3_110_000)
        self.assertEqual(resp.data["metrics"]["hr.entries"]["value"], 1)
        self.assertEqual(resp.data["metrics"]["hr.exits"]["value"], 2)

    def test_overview_branche_les_donnees_rh_reelles(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/overview/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["scope"], "GROUP")
        hr = resp.data["dashboards"]["hr"]
        self.assertTrue(hr["available"])
        self.assertEqual(hr["source"], "mart.hr_kpi")
        self.assertEqual(hr["chartValue"], "3.1M XOF")
        self.assertEqual(hr["chartData"], {"KRE": 2_150_000, "KSH": 960_000})
        self.assertFalse(resp.data["dashboards"]["realEstate"]["available"])
        self.assertFalse(resp.data["dashboards"]["finance"]["available"])

    def test_overview_reste_servie_si_le_mart_rh_est_indisponible(self):
        gateway.set_mart_gateway(FailingMartGateway())
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/overview/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["dashboards"]["hr"]["available"])
        self.assertEqual(resp.data["dashboards"]["hr"]["status"], "mart.hr_kpi indisponible")

    def test_hr_kpi_perimetre_restreint(self):
        self.client.force_authenticate(self.drh_kre)
        resp = self.client.get("/api/v1/governance/hr/kpi/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["scope"], ["KRE"])
        # Seule KRE est visible : 2 150 000, aucune embauche Q1 côté KRE, 2 départs (E2, E5)
        self.assertEqual(resp.data["metrics"]["hr.payroll_mass"]["value"], 2_150_000)
        self.assertEqual(resp.data["metrics"]["hr.entries"]["value"], 0)
        self.assertEqual(resp.data["metrics"]["hr.exits"]["value"], 2)
        self.assertEqual(resp.data["payroll_by_subsidiary"], {"KRE": 2_150_000})

    def test_parametres_invalides(self):
        self.client.force_authenticate(self.dg)
        self.assertEqual(self.client.get("/api/v1/governance/hr/kpi/").status_code, 400)
        self.assertEqual(
            self.client.get("/api/v1/governance/hr/kpi/?year=2026&quarter=9").status_code, 400
        )

    def test_authentification_requise(self):
        resp = self.client.get("/api/v1/governance/hr/kpi/?year=2026&quarter=1")
        self.assertIn(resp.status_code, (401, 403))

    def test_consultation_journalisee(self):
        self.client.force_authenticate(self.drh_kre)
        self.client.get("/api/v1/governance/hr/kpi/?year=2026&quarter=1")
        log = AccessLog.objects.latest("occurred_at")
        self.assertEqual(log.action, "query_metric")
        self.assertEqual(log.subsidiary_scope, ["KRE"])
        self.assertEqual(log.user_role, "DRH")
