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

    def test_catalog_filtre_par_domaine_rh(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/catalog/?domain=hr")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 6)
        self.assertIn("hr.turnover_rate", {m["key"] for m in resp.data["metrics"]})

    def test_catalog_couvre_tous_les_domaines(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/catalog/")
        self.assertEqual(resp.status_code, 200)
        # RH (6) + 5 domaines métier (9 chacun) = 51 métriques
        self.assertEqual(resp.data["count"], 51)
        keys = {m["key"] for m in resp.data["metrics"]}
        self.assertIn("finance.dso", keys)
        self.assertIn("immobilier.taux_commercialisation", keys)
        domains = {m["domain"] for m in resp.data["metrics"]}
        self.assertEqual(
            domains,
            {"hr", "immobilier", "finance", "operations", "commercial-clients", "risques-conformite"},
        )

    def test_hr_kpi_groupe_voit_tout(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/kpi/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["scope"], "GROUP")
        self.assertEqual(resp.data["metrics"]["hr.payroll_mass"]["value"], 3_110_000)
        self.assertEqual(resp.data["metrics"]["hr.entries"]["value"], 1)
        self.assertEqual(resp.data["metrics"]["hr.exits"]["value"], 2)

    def test_hr_kpi_periode_vide_renvoie_zero(self):
        # Choix de design : les KPI BRUTS (comptages/sommes) renvoient 0 pour une période
        # sans données — 0 entrées EST la réponse réelle. La gouvernance N/D s'applique au
        # niveau des SCORES (cf. HrScoreView), pas aux comptages bruts.
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/kpi/?year=2025&quarter=4")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["metrics"]["hr.payroll_mass"]["value"], 0)
        self.assertEqual(resp.data["metrics"]["hr.entries"]["value"], 0)
        self.assertEqual(resp.data["metrics"]["hr.exits"]["value"], 0)

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


# Lignes de score de démonstration (month_start, subsidiary_code, dimension_key, score).
# Conçues pour vérifier la pondération, la renormalisation et le filtre de période.
SCORE_ROWS = [
    (date(2025, 12, 1), "KRE", "effectifs_stabilite", 50.0),  # hors Q1 → trend seulement
    (date(2026, 1, 1), "KRE", "effectifs_stabilite", 80.0),
    (date(2026, 1, 1), "KRE", "conformite", 90.0),
    (date(2026, 2, 1), "KRE", "effectifs_stabilite", 80.0),
    (date(2026, 2, 1), "KRE", "conformite", 90.0),
    (date(2026, 1, 1), "KSH", "performance", 60.0),
    (date(2026, 2, 1), "KSH", "performance", 60.0),
]


class HrScoreApiTest(TestCase):
    """Human Capital Score : pondération renormalisée, périmètre, période, gouverné N/D."""

    def setUp(self):
        gateway.set_mart_gateway(InMemoryMartGateway(build_hr_kpi_rows(EMP, PAY), SCORE_ROWS))
        self.kre = Subsidiary.objects.create(code="KRE", name="K-Express")
        self.ksh = Subsidiary.objects.create(code="KSH", name="K-Shield")
        Subsidiary.objects.create(code="MYK", name="MyKaydan")
        self.dg = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh_kre", password="x", role="DRH")
        self.drh_kre.subsidiaries.add(self.kre)
        self.client = APIClient()

    def tearDown(self):
        gateway.set_mart_gateway(None)

    def test_score_global_pondere_et_renormalise(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["available"])
        # (80*15 + 90*5 + 60*15) / 35 = 72.9
        self.assertEqual(resp.data["global"], 72.9)
        dims = {d["key"]: d for d in resp.data["dimensions"]}
        self.assertEqual(len(resp.data["dimensions"]), 9)
        self.assertEqual(dims["effectifs_stabilite"]["score"], 80.0)
        self.assertEqual(dims["effectifs_stabilite"]["weight"], 15)
        self.assertEqual(dims["conformite"]["score"], 90.0)
        self.assertIsNone(dims["recrutement"]["score"])  # gouverné : dimension non alimentée

    def test_score_par_filiale(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1")
        by_sub = {s["code"]: s["score"] for s in resp.data["by_subsidiary"]}
        self.assertEqual(by_sub["KRE"], 82.5)  # (80*15 + 90*5) / 20
        self.assertEqual(by_sub["KSH"], 60.0)  # (60*15) / 15

    def test_trend_inclut_les_mois_hors_periode(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1")
        trend = {t["month"]: t["score"] for t in resp.data["trend"]}
        self.assertEqual(trend["2025-12-01"], 50.0)  # mois hors Q1, présent dans la courbe
        self.assertEqual(trend["2026-01-01"], 72.9)
        self.assertEqual(trend["2026-02-01"], 72.9)

    def test_filtre_filiale_query_param(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1&subsidiary=KSH")
        self.assertEqual(resp.data["global"], 60.0)
        self.assertEqual([s["code"] for s in resp.data["by_subsidiary"]], ["KSH"])

    def test_perimetre_restreint(self):
        self.client.force_authenticate(self.drh_kre)
        resp = self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1")
        self.assertEqual(resp.data["scope"], ["KRE"])
        self.assertEqual(resp.data["global"], 82.5)  # KRE uniquement
        self.assertEqual([s["code"] for s in resp.data["by_subsidiary"]], ["KRE"])

    def test_gouverne_si_aucune_donnee(self):
        gateway.set_mart_gateway(InMemoryMartGateway(build_hr_kpi_rows(EMP, PAY)))  # pas de score
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["available"])
        self.assertIsNone(resp.data["global"])
        self.assertTrue(all(d["score"] is None for d in resp.data["dimensions"]))
        self.assertEqual(resp.data["by_subsidiary"], [])
        self.assertEqual(resp.data["trend"], [])

    def test_score_journalise(self):
        self.client.force_authenticate(self.dg)
        self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1")
        log = AccessLog.objects.latest("occurred_at")
        self.assertEqual(log.action, "query_hr_score")
        self.assertEqual(log.metric_key, "hr.human_capital_score")

    def test_filiale_hors_perimetre_ne_fuit_pas(self):
        # drh_kre (périmètre KRE) demande explicitement KSH → aucune donnée KSH ne doit fuiter.
        self.client.force_authenticate(self.drh_kre)
        resp = self.client.get("/api/v1/governance/hr/score/?year=2026&quarter=1&subsidiary=KSH")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["available"])
        self.assertIsNone(resp.data["global"])
        self.assertEqual(resp.data["by_subsidiary"], [])


# Lignes mart.domain_score de démo (domain, month, sub, dim, score).
DOMAIN_SCORE_ROWS = [
    ("immobilier", date(2025, 12, 1), "KRE", "maitrise_fonciere", 40.0),  # hors Q1 → trend
    ("immobilier", date(2026, 1, 1), "KRE", "maitrise_fonciere", 80.0),   # poids 20
    ("immobilier", date(2026, 1, 1), "KRE", "securite_chantier", 60.0),   # poids 12
    ("immobilier", date(2026, 2, 1), "KRE", "maitrise_fonciere", 80.0),
    ("immobilier", date(2026, 2, 1), "KRE", "securite_chantier", 60.0),
    ("immobilier", date(2026, 1, 1), "KSH", "pilotage_risques", 50.0),    # poids 10
    ("finance", date(2026, 1, 1), "KRE", "liquidite_tresorerie", 90.0),   # autre domaine : ignoré
]


class DomainScoreApiTest(TestCase):
    """Score de Gouvernance générique : pondération par domaine, isolation, RBAC, gouverné."""

    def setUp(self):
        gateway.set_mart_gateway(
            InMemoryMartGateway(build_hr_kpi_rows(EMP, PAY), domain_score_rows=DOMAIN_SCORE_ROWS)
        )
        self.kre = Subsidiary.objects.create(code="KRE", name="K-Express")
        self.ksh = Subsidiary.objects.create(code="KSH", name="K-Shield")
        Subsidiary.objects.create(code="MYK", name="MyKaydan")
        self.dg = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh_kre", password="x", role="DRH")
        self.drh_kre.subsidiaries.add(self.kre)
        self.client = APIClient()

    def tearDown(self):
        gateway.set_mart_gateway(None)

    def test_domaine_inconnu_404(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score/inexistant/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 404)

    def test_score_immobilier_pondere(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score/immobilier/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["domain"], "immobilier")
        self.assertTrue(resp.data["available"])
        # (80*20 + 60*12 + 50*10) / 42 = 67.1
        self.assertEqual(resp.data["global"], 67.1)
        self.assertEqual(len(resp.data["dimensions"]), 6)
        dims = {d["key"]: d for d in resp.data["dimensions"]}
        self.assertEqual(dims["maitrise_fonciere"]["score"], 80.0)
        self.assertIsNone(dims["execution_programmes"]["score"])  # gouverné
        self.assertIn("mart_source", dims["maitrise_fonciere"])  # métadonnée exposée

    def test_isolation_par_domaine(self):
        # la ligne finance (90) ne doit pas polluer immobilier
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score/immobilier/?year=2026&quarter=1")
        dims = {d["key"]: d for d in resp.data["dimensions"]}
        self.assertNotIn("liquidite_tresorerie", dims)

    def test_par_filiale_et_trend(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score/immobilier/?year=2026&quarter=1")
        by_sub = {s["code"]: s["score"] for s in resp.data["by_subsidiary"]}
        self.assertEqual(by_sub["KRE"], 72.5)  # (80*20 + 60*12) / 32
        self.assertEqual(by_sub["KSH"], 50.0)  # (50*10) / 10
        trend = {t["month"]: t["score"] for t in resp.data["trend"]}
        self.assertEqual(trend["2025-12-01"], 40.0)
        self.assertEqual(trend["2026-01-01"], 67.1)

    def test_perimetre_restreint(self):
        self.client.force_authenticate(self.drh_kre)
        resp = self.client.get("/api/v1/governance/score/immobilier/?year=2026&quarter=1")
        self.assertEqual(resp.data["scope"], ["KRE"])
        self.assertEqual(resp.data["global"], 72.5)
        self.assertEqual([s["code"] for s in resp.data["by_subsidiary"]], ["KRE"])

    def test_gouverne_si_domaine_non_alimente(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score/operations/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["available"])
        self.assertIsNone(resp.data["global"])
        self.assertTrue(all(d["score"] is None for d in resp.data["dimensions"]))
        self.assertEqual(resp.data["trend"], [])

    def test_journalise(self):
        self.client.force_authenticate(self.dg)
        self.client.get("/api/v1/governance/score/finance/?year=2026&quarter=1")
        log = AccessLog.objects.latest("occurred_at")
        self.assertEqual(log.action, "query_domain_score")
        self.assertEqual(log.metric_key, "finance.governance_score")


class GroupScoreApiTest(TestCase):
    """Indice de Gouvernance Groupe : agrégation pondérée des scores de domaine."""

    def setUp(self):
        gateway.set_mart_gateway(
            InMemoryMartGateway(
                build_hr_kpi_rows(EMP, PAY),
                score_rows=[(date(2026, 1, 1), "KRE", "effectifs_stabilite", 80.0)],
                domain_score_rows=[
                    ("immobilier", date(2026, 1, 1), "KRE", "maitrise_fonciere", 70.0),
                    ("immobilier", date(2026, 1, 1), "KSH", "maitrise_fonciere", 60.0),
                ],
            )
        )
        self.kre = Subsidiary.objects.create(code="KRE", name="K-Express")
        self.ksh = Subsidiary.objects.create(code="KSH", name="K-Shield")
        Subsidiary.objects.create(code="MYK", name="MyKaydan")
        self.dg = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.client = APIClient()

    def tearDown(self):
        gateway.set_mart_gateway(None)

    def test_indice_consolide_pondere_et_renormalise(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score-group/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["available"])
        # capital-humain global = 80 (w16), immobilier global = (70+60)/2=65 (w22), reste N/D
        # (80*16 + 65*22) / 38 = 71.3
        self.assertEqual(resp.data["global"], 71.3)
        self.assertEqual(len(resp.data["domains"]), 6)
        by_dom = {d["domain"]: d["score"] for d in resp.data["domains"]}
        self.assertEqual(by_dom["capital-humain"], 80.0)
        self.assertEqual(by_dom["immobilier"], 65.0)
        self.assertIsNone(by_dom["finance"])  # gouverné : domaine non alimenté

    def test_indice_par_filiale(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score-group/?year=2026&quarter=1")
        by_sub = {s["code"]: s["score"] for s in resp.data["by_subsidiary"]}
        # KRE : RH 80 (w16) + immo 70 (w22) -> (80*16+70*22)/38 = 74.2
        self.assertEqual(by_sub["KRE"], 74.2)
        # KSH : seulement immo 60 -> 60.0 (RH non alimenté pour KSH)
        self.assertEqual(by_sub["KSH"], 60.0)

    def test_gouverne_si_aucune_donnee(self):
        gateway.set_mart_gateway(InMemoryMartGateway(build_hr_kpi_rows(EMP, PAY)))
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/score-group/?year=2026&quarter=1")
        self.assertFalse(resp.data["available"])
        self.assertIsNone(resp.data["global"])
        self.assertTrue(all(d["score"] is None for d in resp.data["domains"]))
        self.assertEqual(resp.data["by_subsidiary"], [])
        self.assertEqual(resp.data["trend"], [])

    def test_journalise(self):
        self.client.force_authenticate(self.dg)
        self.client.get("/api/v1/governance/score-group/?year=2026&quarter=1")
        log = AccessLog.objects.latest("occurred_at")
        self.assertEqual(log.action, "query_group_score")
        self.assertEqual(log.metric_key, "group.governance_index")

    def test_export_xlsx(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/export/groupe.xlsx?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("spreadsheetml", resp["Content-Type"])
        self.assertEqual(resp.content[:2], b"PK")  # signature ZIP/XLSX
        self.assertGreater(len(resp.content), 500)

    def test_export_pdf(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/export/groupe.pdf?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertEqual(resp.content[:4], b"%PDF")

    def test_export_format_inconnu_400(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/export/groupe.docx?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 400)

    def test_export_journalise(self):
        self.client.force_authenticate(self.dg)
        self.client.get("/api/v1/governance/export/groupe.pdf?year=2026&quarter=1")
        log = AccessLog.objects.latest("occurred_at")
        self.assertEqual(log.action, "export_group_score")


class AlertsApiTest(TestCase):
    """Centre d'alertes : seuils sur scores réels, gouverné N/D, périmètre RBAC."""

    def setUp(self):
        gateway.set_mart_gateway(
            InMemoryMartGateway(
                build_hr_kpi_rows(EMP, PAY),
                score_rows=[(date(2026, 1, 1), "KRE", "effectifs_stabilite", 90.0)],
                domain_score_rows=[("immobilier", date(2026, 1, 1), "KRE", "maitrise_fonciere", 40.0)],
            )
        )
        self.kre = Subsidiary.objects.create(code="KRE", name="K-Express")
        Subsidiary.objects.create(code="KSH", name="K-Shield")
        Subsidiary.objects.create(code="MYK", name="MyKaydan")
        self.dg = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.client = APIClient()

    def tearDown(self):
        gateway.set_mart_gateway(None)

    def test_alertes_par_seuil(self):
        # immobilier global = 40 → critique ; capital-humain = 90 → rien ;
        # KRE = (90*16 + 40*22)/38 = 61.1 → vigilance ; groupe 61.1 → vigilance.
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/alerts/?year=2026&quarter=1")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["available"])
        self.assertEqual(resp.data["counts"]["critical"], 1)
        self.assertGreaterEqual(resp.data["counts"]["warning"], 1)
        self.assertEqual(resp.data["alerts"][0]["severity"], "critical")  # trié pire d'abord
        sources = {a["source"] for a in resp.data["alerts"]}
        self.assertIn("immobilier.governance_score", sources)
        # domaines non alimentés (finance, ops…) → aucune alerte inventée
        self.assertNotIn("finance.governance_score", sources)

    def test_gouverne_aucune_alerte_si_aucune_donnee(self):
        gateway.set_mart_gateway(InMemoryMartGateway(build_hr_kpi_rows(EMP, PAY)))
        self.client.force_authenticate(self.dg)
        resp = self.client.get("/api/v1/governance/alerts/?year=2026&quarter=1")
        self.assertFalse(resp.data["available"])
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(resp.data["alerts"], [])

    def test_journalise(self):
        self.client.force_authenticate(self.dg)
        self.client.get("/api/v1/governance/alerts/?year=2026&quarter=1")
        log = AccessLog.objects.latest("occurred_at")
        self.assertEqual(log.action, "query_alerts")


class AiQueryApiTest(TestCase):
    """IA ancrée : réponse sourcée sur le catalogue, refus hors catalogue, gouverné N/D."""

    def setUp(self):
        self.dg = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.client = APIClient()

    def test_question_ancree_sur_le_catalogue(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.post("/api/v1/governance/ai/query/", {"question": "quel est le DSO finance ?"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["grounded"])
        self.assertEqual(resp.data["metric"]["key"], "finance.dso")
        self.assertIsNone(resp.data["value"])  # source non branchée → N/D, jamais inventé
        self.assertIn("N/D", resp.data["answer"])

    def test_refus_hors_catalogue(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.post("/api/v1/governance/ai/query/", {"question": "météo à Abidjan demain ?"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["grounded"])
        self.assertIsNone(resp.data["metric"])

    def test_question_vide_400(self):
        self.client.force_authenticate(self.dg)
        resp = self.client.post("/api/v1/governance/ai/query/", {"question": "  "}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_journalise(self):
        self.client.force_authenticate(self.dg)
        self.client.post("/api/v1/governance/ai/query/", {"question": "finance.dso"}, format="json")
        log = AccessLog.objects.latest("occurred_at")
        self.assertEqual(log.action, "query_ai")
        self.assertEqual(log.metric_key, "finance.dso")
