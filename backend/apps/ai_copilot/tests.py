"""Tests du K-Insight AI Copilot (Phase 1) : router multi-provider, RBAC + approbation, chat ancré."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AIActionRequest, AIConversation, AIMessage, AIToolExecution
from .providers import AIProviderRouter, GroundedFacts, OfflineGroundedProvider, ProviderClient, ProviderUnavailable
from .tools import (
    ActionApprovalService,
    PermissionAwareToolExecutor,
    Tool,
    ToolPermissionDenied,
    ToolRegistry,
    WRITE_ROLES,
    build_default_registry,
)

User = get_user_model()
FACTS = GroundedFacts(grounded=True, answer="réponse ancrée", metric={"key": "finance.dso"}, value=None, source="mart.finance_kpi")


class _Failing(ProviderClient):
    name = "deepseek"

    def is_available(self):
        return True

    def complete(self, message, context, facts):
        raise ProviderUnavailable("simulate down")


class _Working(ProviderClient):
    name = "claude"

    def is_available(self):
        return True

    def complete(self, message, context, facts):
        return "réponse LLM"


class RouterTest(TestCase):
    def test_fallback_vers_provider_suivant(self):
        router = AIProviderRouter([_Failing(), _Working(), OfflineGroundedProvider()])
        res = router.complete("q", {}, FACTS)
        self.assertEqual(res.provider, "claude")
        self.assertEqual(res.text, "réponse LLM")
        # la 1re tentative (deepseek) est tracée en échec
        self.assertEqual(res.attempts[0]["provider"], "deepseek")
        self.assertFalse(res.attempts[0]["ok"])

    def test_repli_offline_quand_tout_echoue(self):
        router = AIProviderRouter([_Failing(), OfflineGroundedProvider()])
        res = router.complete("q", {}, FACTS)
        self.assertEqual(res.provider, "offline-grounded")
        self.assertEqual(res.text, "réponse ancrée")  # phrase ancrée déterministe
        self.assertTrue(res.grounded)


class ToolRbacApprovalTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="x", role="ADMIN_INTEGRATION")
        self.admin2 = User.objects.create_user("adm2", password="x", role="ADMIN_CA")
        self.reader = User.objects.create_user("rdr", password="x", role="READER")
        self.ran = {"count": 0}

        def handler(args, user, ctx):
            self.ran["count"] += 1
            return {"ran": True, "x": args.get("x")}

        self.reg = ToolRegistry()
        self.reg.register(Tool(name="t_read", description="lecture", handler=lambda a, u, c: {"ok": True}, mode="read"))
        self.reg.register(Tool(
            name="t_write", description="écriture", handler=handler, mode="write", sensitive=True, required_roles=WRITE_ROLES
        ))
        self.reg.register(Tool(
            name="t_destroy", description="suppression", handler=handler, mode="write",
            sensitive=True, destructive=True, required_roles=WRITE_ROLES,
        ))
        self.executor = PermissionAwareToolExecutor(self.reg)
        self.approval = ActionApprovalService(self.reg)

    def test_destructif_exige_double_validation(self):
        out = self.executor.execute("t_destroy", {"x": 9}, self.admin, {})
        self.assertEqual(out["status"], "approval_required")
        self.assertEqual(out["required_confirmations"], 2)
        req = AIActionRequest.objects.get(pk=out["request_id"])
        # 1re confirmation : RIEN exécuté, demande encore pending
        self.approval.approve(req, self.admin)
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")
        self.assertEqual(self.ran["count"], 0)
        # 2e confirmation par une AUTRE personne (4-eyes) : exécution
        self.approval.approve(req, self.admin2)
        req.refresh_from_db()
        self.assertEqual(req.status, "executed")
        self.assertEqual(self.ran["count"], 1)

    def test_destructif_meme_approbateur_refuse(self):
        # Le même utilisateur ne peut pas fournir les deux validations (4-eyes).
        out = self.executor.execute("t_destroy", {"x": 9}, self.admin, {})
        req = AIActionRequest.objects.get(pk=out["request_id"])
        self.approval.approve(req, self.admin)  # 1re
        from .tools import ToolError
        with self.assertRaises(ToolError):
            self.approval.approve(req, self.admin)  # 2e par le MÊME → refusée
        req.refresh_from_db()
        self.assertEqual(req.status, "pending")
        self.assertEqual(self.ran["count"], 0)

    def test_lecture_executee_immediatement(self):
        out = self.executor.execute("t_read", {}, self.reader, {})
        self.assertEqual(out["status"], "done")
        self.assertTrue(AIToolExecution.objects.filter(tool_name="t_read", status="success").exists())

    def test_ecriture_refusee_sans_droits(self):
        with self.assertRaises(ToolPermissionDenied):
            self.executor.execute("t_write", {"x": 1}, self.reader, {})

    def test_ecriture_passe_par_approbation_et_n_execute_pas(self):
        out = self.executor.execute("t_write", {"x": 7}, self.admin, {})
        self.assertEqual(out["status"], "approval_required")
        self.assertEqual(self.ran["count"], 0)  # RIEN exécuté avant validation
        req = AIActionRequest.objects.get(pk=out["request_id"])
        self.assertEqual(req.status, "pending")

    def test_approbation_execute_le_handler(self):
        out = self.executor.execute("t_write", {"x": 7}, self.admin, {})
        req = AIActionRequest.objects.get(pk=out["request_id"])
        self.approval.approve(req, self.admin)
        req.refresh_from_db()
        self.assertEqual(req.status, "executed")
        self.assertEqual(self.ran["count"], 1)
        self.assertEqual(req.result["result"]["x"], 7)

    def test_rejet_n_execute_pas(self):
        out = self.executor.execute("t_write", {"x": 7}, self.admin, {})
        req = AIActionRequest.objects.get(pk=out["request_id"])
        self.approval.reject(req, self.admin, note="non")
        req.refresh_from_db()
        self.assertEqual(req.status, "rejected")
        self.assertEqual(self.ran["count"], 0)

    def test_approbation_refusee_sans_droits(self):
        out = self.executor.execute("t_write", {"x": 7}, self.admin, {})
        req = AIActionRequest.objects.get(pk=out["request_id"])
        with self.assertRaises(ToolPermissionDenied):
            self.approval.approve(req, self.reader)

    def test_revocation_droits_demandeur_bloque_execution(self):
        # Droits du DEMANDEUR révoqués entre la demande et l'approbation → exécution refusée.
        out = self.executor.execute("t_write", {"x": 5}, self.admin, {})
        req = AIActionRequest.objects.get(pk=out["request_id"])
        self.admin.role = "READER"  # perd WRITE_ROLES
        self.admin.save(update_fields=["role"])
        self.approval.approve(req, self.admin2)  # approbateur habilité
        req.refresh_from_db()
        self.assertEqual(req.status, "failed")
        self.assertEqual(self.ran["count"], 0)  # handler NON exécuté

    def test_rejet_refuse_sans_droits(self):
        out = self.executor.execute("t_write", {"x": 7}, self.admin, {})
        req = AIActionRequest.objects.get(pk=out["request_id"])
        with self.assertRaises(ToolPermissionDenied):
            self.approval.reject(req, self.reader, note="tentative")

    def test_double_approbation_bloquee(self):
        out = self.executor.execute("t_write", {"x": 7}, self.admin, {})
        req = AIActionRequest.objects.get(pk=out["request_id"])
        self.approval.approve(req, self.admin)
        # 2e approbation (retry/double-clic) refusée → handler NON ré-exécuté
        from .tools import ToolError
        with self.assertRaises(ToolError):
            self.approval.approve(req, self.admin)
        self.assertEqual(self.ran["count"], 1)


class ValueBindingTest(TestCase):
    """Phase 6 : l'IA renvoie de VRAIES valeurs HR depuis le mart (gouverné si absent)."""

    def setUp(self):
        from apps.governance import gateway
        from apps.governance.gateway import InMemoryMartGateway
        from apps.governance.tests import EMP, PAY
        from k_insight.kpi.hr_mart import build_hr_kpi_rows
        from apps.organizations.models import Subsidiary

        gateway.set_mart_gateway(InMemoryMartGateway(build_hr_kpi_rows(EMP, PAY)))
        for code, name in [("KRE", "K-Express"), ("KSH", "K-Shield"), ("MYK", "MyKaydan")]:
            Subsidiary.objects.create(code=code, name=name)
        self.user = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def tearDown(self):
        from apps.governance import gateway
        gateway.set_mart_gateway(None)

    def test_chat_renvoie_valeur_reelle_hr(self):
        resp = self.client.post(
            "/api/v1/ai/chat/",
            {"message": "masse salariale", "context": {"year": 2026, "quarter": 1}},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["metric"]["key"], "hr.payroll_mass")
        self.assertEqual(resp.data["value"], 3_110_000.0)  # valeur réelle du mart (vérifiée ailleurs)
        self.assertNotIn("N/D", resp.data["answer"])


class ChatApiTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("dg", password="x", role="DG_GROUP", is_group_scope=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_chat_ancre_offline(self):
        # Sans clé LLM (tests), le router bascule sur le repli ancré déterministe.
        resp = self.client.post("/api/v1/ai/chat/", {"message": "quel est le DSO finance ?"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["provider"], "offline-grounded")
        self.assertTrue(resp.data["grounded"])
        self.assertEqual(resp.data["metric"]["key"], "finance.dso")
        self.assertIn("N/D", resp.data["answer"])  # valeur gouvernée, jamais inventée
        # conversation + 2 messages persistés
        conv = AIConversation.objects.get(pk=resp.data["conversation_id"])
        self.assertEqual(conv.messages.count(), 2)

    def test_chat_refuse_hors_catalogue(self):
        resp = self.client.post("/api/v1/ai/chat/", {"message": "le cours du bitcoin ?"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["grounded"])
        self.assertIsNone(resp.data["metric"])

    def test_chat_message_vide_400(self):
        self.assertEqual(self.client.post("/api/v1/ai/chat/", {"message": "  "}, format="json").status_code, 400)

    def test_conversation_listee_et_supprimable(self):
        r = self.client.post("/api/v1/ai/chat/", {"message": "finance.dso"}, format="json")
        cid = r.data["conversation_id"]
        self.assertEqual(self.client.get("/api/v1/ai/conversations/").data["count"], 1)
        detail = self.client.get(f"/api/v1/ai/conversations/{cid}/")
        self.assertEqual(len(detail.data["messages"]), 2)
        self.assertEqual(self.client.delete(f"/api/v1/ai/conversations/{cid}/").status_code, 204)

    def test_authentification_requise(self):
        anon = APIClient()
        self.assertIn(anon.post("/api/v1/ai/chat/", {"message": "x"}, format="json").status_code, (401, 403))


class AutomationTest(TestCase):
    """Phase 5 : automatisation lit en auto, mais une action sensible passe par approbation."""

    def setUp(self):
        from apps.governance import gateway
        from apps.governance.gateway import InMemoryMartGateway

        gateway.set_mart_gateway(InMemoryMartGateway([]))  # mart vide → gouverné, pas d'erreur
        self.admin = User.objects.create_user("adm", password="x", role="ADMIN_INTEGRATION", is_group_scope=True)

    def tearDown(self):
        from apps.governance import gateway
        gateway.set_mart_gateway(None)

    def test_automatisation_lecture_executee(self):
        from .models import AIAutomation
        from .tasks import run_automation

        auto = AIAutomation.objects.create(name="Score quotidien", tool_name="group_score", created_by=self.admin)
        out = run_automation(auto.pk)
        self.assertEqual(out["status"], "done")
        auto.refresh_from_db()
        self.assertIsNotNone(auto.last_run_at)

    def test_automatisation_sensible_bloquee(self):
        # Un planificateur non supervisé ne doit JAMAIS initier une action sensible :
        # ni l'exécuter, ni même créer une demande d'approbation automatiquement.
        from .models import AIActionRequest, AIAutomation
        from .tasks import run_automation

        auto = AIAutomation.objects.create(
            name="Sync auto", tool_name="run_connector_sync", args={"source_id": 1}, created_by=self.admin
        )
        out = run_automation(auto.pk)
        self.assertEqual(out["status"], "blocked")
        self.assertEqual(AIActionRequest.objects.filter(tool_name="run_connector_sync").count(), 0)

    def test_is_due(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import AIAutomation

        auto = AIAutomation.objects.create(name="x", tool_name="group_score", created_by=self.admin, interval_minutes=60)
        self.assertTrue(auto.is_due(timezone.now()))  # jamais exécutée
        auto.last_run_at = timezone.now()
        self.assertFalse(auto.is_due(timezone.now()))  # vient de tourner
        self.assertTrue(auto.is_due(timezone.now() + timedelta(minutes=61)))


class IntentTest(TestCase):
    """Routage d'intention → outil (déterministe, conservateur)."""

    def test_intentions(self):
        from .intent import detect_tool_intent

        self.assertEqual(detect_tool_intent("génère le rapport groupe"), ("generate_report", {}))
        self.assertEqual(detect_tool_intent("lance la synchronisation du connecteur 5"), ("run_connector_sync", {"source_id": 5}))
        self.assertEqual(detect_tool_intent("supprime le connecteur 3"), ("delete_connector", {"source_id": 3}))
        self.assertIsNone(detect_tool_intent("quel est le DSO finance ?"))
        self.assertIsNone(detect_tool_intent("synchronise un connecteur"))  # pas d'identifiant → ambigu


class ActionableChatTest(TestCase):
    """Le Copilot AGIT : lecture exécutée, écriture → approbation, droits respectés."""

    def setUp(self):
        from apps.governance import gateway
        from apps.governance.gateway import InMemoryMartGateway

        gateway.set_mart_gateway(InMemoryMartGateway([]))
        self.admin = User.objects.create_user("adm", password="x", role="ADMIN_INTEGRATION", is_group_scope=True)
        self.reader = User.objects.create_user("rdr", password="x", role="READER", is_group_scope=True)
        self.client = APIClient()

    def tearDown(self):
        from apps.governance import gateway
        gateway.set_mart_gateway(None)

    def test_chat_genere_rapport_lecture(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.post("/api/v1/ai/chat/", {"message": "génère le rapport groupe"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data["action"])
        self.assertEqual(resp.data["action"]["status"], "done")
        self.assertIn("exports", resp.data["action"]["result"])

    def test_chat_sync_demande_approbation_admin(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post("/api/v1/ai/chat/", {"message": "lance la synchronisation du connecteur 1"}, format="json")
        self.assertEqual(resp.data["action"]["status"], "approval_required")

    def test_chat_sync_refuse_pour_lecteur(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.post("/api/v1/ai/chat/", {"message": "lance la synchronisation du connecteur 1"}, format="json")
        self.assertEqual(resp.data["action"]["status"], "denied")

    def test_chat_question_reste_qa(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.post("/api/v1/ai/chat/", {"message": "quel est le DSO finance ?"}, format="json")
        self.assertIsNone(resp.data["action"])  # question → Q&A ancrée, pas d'action


class ToolEndpointTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("adm", password="x", role="ADMIN_INTEGRATION", is_group_scope=True)
        self.reader = User.objects.create_user("rdr", password="x", role="READER")
        self.client = APIClient()

    def test_outil_lecture_execute(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.post("/api/v1/ai/tools/execute/", {"tool": "explain_kpi", "args": {"query": "finance.dso"}}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "done")

    def test_outil_ecriture_non_admin_403(self):
        self.client.force_authenticate(self.reader)
        resp = self.client.post("/api/v1/ai/tools/execute/", {"tool": "run_connector_sync", "args": {"source_id": 1}}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_outil_ecriture_admin_demande_approbation(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post("/api/v1/ai/tools/execute/", {"tool": "run_connector_sync", "args": {"source_id": 1}}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "approval_required")
        # visible dans la liste des actions à approuver
        listing = self.client.get("/api/v1/ai/actions/")
        self.assertEqual(listing.data["count"], 1)
