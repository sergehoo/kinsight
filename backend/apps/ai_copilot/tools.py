"""Outils contrôlés du Copilot : registre déclaratif + exécuteur conscient des permissions
+ flux d'approbation.

Sécurité (cf. spec) : LECTURE SEULE par défaut. Un outil en lecture s'exécute immédiatement
si l'utilisateur a les droits. Un outil d'ÉCRITURE ou SENSIBLE n'est JAMAIS exécuté
directement : il crée une demande d'approbation (AIActionRequest) qui doit être validée
explicitement avant exécution. RBAC vérifié à la fois à la demande ET à l'approbation.
Tout est journalisé (AIToolExecution, AIAuditLog).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from django.db import transaction

from .models import AIActionApproval, AIActionRequest, AIAuditLog, AIToolExecution

# Rôles habilités aux actions d'écriture sensibles (config/sync de connecteurs).
WRITE_ROLES = frozenset({"ADMIN_INTEGRATION", "ADMIN_CA"})


class ToolError(Exception):
    """Outil inconnu ou désactivé."""


class ToolPermissionDenied(Exception):
    """L'utilisateur n'a pas les droits pour cet outil."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    handler: Callable[[dict, object, dict], dict]
    mode: str = "read"            # "read" | "write"
    sensitive: bool = False       # True → approbation obligatoire
    destructive: bool = False     # True → double validation (suppression, email, notification…)
    required_roles: frozenset = field(default_factory=frozenset)  # vide = tout utilisateur authentifié

    @property
    def needs_approval(self) -> bool:
        return self.mode == "write" or self.sensitive or self.destructive

    @property
    def confirmations(self) -> int:
        return 2 if self.destructive else 1


def can_use(tool: Tool, user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not tool.required_roles:
        return True
    return getattr(user, "role", "") in tool.required_roles


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"Outil inconnu : {name!r}")
        return self._tools[name]

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def allowed_for(self, user) -> list[Tool]:
        return [t for t in self._tools.values() if can_use(t, user)]


def _run(tool: Tool, args: dict, user, context: dict) -> dict:
    start = time.monotonic()
    try:
        result = tool.handler(args or {}, user, context or {})
        latency = int((time.monotonic() - start) * 1000)
        AIToolExecution.objects.create(
            tool_name=tool.name,
            user=user if getattr(user, "is_authenticated", False) else None,
            args=args or {},
            status=AIToolExecution.Status.SUCCESS,
            result=result if isinstance(result, dict) else {"value": result},
            latency_ms=latency,
        )
        return {"status": "done", "tool": tool.name, "result": result}
    except Exception as exc:  # noqa: BLE001 — on trace toute erreur d'outil
        latency = int((time.monotonic() - start) * 1000)
        AIToolExecution.objects.create(
            tool_name=tool.name,
            user=user if getattr(user, "is_authenticated", False) else None,
            args=args or {},
            status=AIToolExecution.Status.ERROR,
            error=str(exc),
            latency_ms=latency,
        )
        raise ToolError(f"Échec de l'outil {tool.name} : {exc}") from exc


class PermissionAwareToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def execute(self, tool_name: str, args: dict, user, context: dict, conversation=None) -> dict:
        tool = self.registry.get(tool_name)
        if not can_use(tool, user):
            raise ToolPermissionDenied(f"Droits insuffisants pour l'outil {tool_name!r}.")

        if not tool.needs_approval:
            AIAuditLog.record(user=user, action="tool_execute", detail={"tool": tool.name, "mode": "read"})
            return _run(tool, args, user, context)

        # Écriture/sensible/destructif : on NE FAIT RIEN — on crée une demande d'approbation.
        req = AIActionRequest.objects.create(
            user=user,
            conversation=conversation,
            tool_name=tool.name,
            args=args or {},
            summary=f"{tool.description} — paramètres : {args or {}}",
            destructive=tool.destructive,
            required_confirmations=tool.confirmations,
        )
        AIAuditLog.record(user=user, action="action_request", detail={"tool": tool.name, "request_id": str(req.id)})
        return {
            "status": "approval_required",
            "tool": tool.name,
            "request_id": str(req.id),
            "summary": req.summary,
            "destructive": tool.destructive,
            "required_confirmations": tool.confirmations,
        }


class ActionApprovalService:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def approve(self, request: AIActionRequest, approver, context: Optional[dict] = None) -> AIActionRequest:
        # RBAC : seuls les habilités à l'outil peuvent approuver.
        tool = self.registry.get(request.tool_name)
        if not can_use(tool, approver):
            raise ToolPermissionDenied("Droits insuffisants pour approuver cette action.")

        # Verrou + re-vérification atomique : empêche la double-exécution (retry/double-clic).
        with transaction.atomic():
            req = AIActionRequest.objects.select_for_update().get(pk=request.pk)
            if req.status != AIActionRequest.Status.PENDING:
                raise ToolError(f"Demande non approuvable (statut {req.status}).")
            # 4-eyes : un approbateur ne compte qu'une fois (sinon double validation = leurre).
            if req.approvals.filter(approver=approver, decision=AIActionApproval.Decision.APPROVED).exists():
                raise ToolError("Vous avez déjà approuvé cette demande ; une seconde validation par une AUTRE personne est requise.")
            AIActionApproval.objects.create(request=req, approver=approver, decision=AIActionApproval.Decision.APPROVED)
            AIAuditLog.record(user=approver, action="approve", detail={"tool": tool.name, "request_id": str(req.id)})

            confirmations = req.approvals.filter(decision=AIActionApproval.Decision.APPROVED).count()
            if confirmations < req.required_confirmations:
                # Double validation : on attend la/les confirmation(s) restante(s) — RIEN exécuté.
                req.result = {"confirmations": confirmations, "required": req.required_confirmations}
                req.save(update_fields=["result"])
                return req

            # Re-vérification RBAC du DEMANDEUR juste avant exécution : ses droits ont pu être
            # révoqués entre la demande et l'approbation (l'action s'exécute en son nom).
            if not can_use(tool, req.user):
                req.status = AIActionRequest.Status.FAILED
                req.result = {"error": "Le demandeur n'a plus les droits requis pour cette action."}
                req.save(update_fields=["status", "result"])
                return req

            try:
                outcome = _run(tool, req.args, req.user, context or {})
                req.status = AIActionRequest.Status.EXECUTED
                req.result = outcome
            except ToolError as exc:
                req.status = AIActionRequest.Status.FAILED
                req.result = {"error": str(exc)}
            req.save(update_fields=["status", "result"])
        return req

    def reject(self, request: AIActionRequest, approver, note: str = "") -> AIActionRequest:
        # RBAC aussi au rejet : sinon un non-habilité pourrait bloquer une action (DoS).
        tool = self.registry.get(request.tool_name)
        if not can_use(tool, approver):
            raise ToolPermissionDenied("Droits insuffisants pour rejeter cette action.")

        with transaction.atomic():
            req = AIActionRequest.objects.select_for_update().get(pk=request.pk)
            if req.status != AIActionRequest.Status.PENDING:
                raise ToolError(f"Demande non rejetable (statut {req.status}).")
            AIActionApproval.objects.create(
                request=req, approver=approver, decision=AIActionApproval.Decision.REJECTED, note=note[:300]
            )
            req.status = AIActionRequest.Status.REJECTED
            req.save(update_fields=["status"])
        AIAuditLog.record(user=approver, action="reject", detail={"tool": req.tool_name, "request_id": str(req.id)})
        return req


# --------------------------------------------------------------------------------------
# Outils par défaut (Phase 1) — lecture ancrée + écriture connecteur sous approbation.
# --------------------------------------------------------------------------------------
def _tool_explain_kpi(args: dict, user, context: dict) -> dict:
    from k_insight.semantic.grounding import answer
    from k_insight.semantic.registry import CATALOG

    from .value_resolver import build_value_lookup

    period = context.get("period", {}) if context else {}
    lookup = build_value_lookup(
        user, int(period.get("year", 2026)), int(period.get("quarter", 1)), (context or {}).get("subsidiary", "all")
    )
    return answer(CATALOG, str(args.get("query", "")), lookup)


def _tool_group_score(args: dict, user, context: dict) -> dict:
    from apps.governance.module_views import build_group_report

    period = context.get("period", {}) if context else {}
    report = build_group_report(
        user, int(period.get("year", 2026)), int(period.get("quarter", 1)), context.get("subsidiary", "all")
    )
    return {"available": report["available"], "global": report["global"], "domains": report["domains"]}


def _tool_run_connector_sync(args: dict, user, context: dict) -> dict:
    """Lance une synchronisation d'un connecteur (écriture sensible — passe par approbation)."""
    from apps.integrations.models import IntegrationSource
    from apps.integrations.services import run_sync

    source = IntegrationSource.objects.filter(pk=args.get("source_id")).first()
    if source is None:
        raise ValueError("Connecteur introuvable.")
    return {"sync": run_sync(source)}


def _tool_generate_report(args: dict, user, context: dict) -> dict:
    """Génère la synthèse de gouvernance Groupe + indique les exports disponibles (lecture)."""
    from apps.governance.module_views import build_group_report

    period = context.get("period", {}) if context else {}
    year, quarter = int(period.get("year", 2026)), int(period.get("quarter", 1))
    report = build_group_report(user, year, quarter, (context or {}).get("subsidiary", "all"))
    return {
        "report": report,
        "exports": {
            "xlsx": f"/api/v1/governance/export/groupe.xlsx?year={year}&quarter={quarter}",
            "pdf": f"/api/v1/governance/export/groupe.pdf?year={year}&quarter={quarter}",
        },
    }


def _tool_delete_connector(args: dict, user, context: dict) -> dict:
    """Supprime un connecteur (DESTRUCTIF — double validation)."""
    from apps.integrations.models import IntegrationSource

    source = IntegrationSource.objects.filter(pk=args.get("source_id")).first()
    if source is None:
        raise ValueError("Connecteur introuvable.")
    name = str(source)
    source.delete()
    return {"deleted": name}


def _tool_send_report_email(args: dict, user, context: dict) -> dict:
    """Envoie un rapport par email (DESTRUCTIF/sortant — double validation).

    Phase 4 : l'envoi SMTP réel est à brancher (non vérifiable ici) ; l'action est tracée et
    la file d'envoi enregistrée — jamais d'envoi silencieux sans la double validation."""
    recipients = args.get("recipients") or []
    if not recipients:
        raise ValueError("Aucun destinataire.")
    return {"status": "queued", "recipients": recipients, "note": "Envoi SMTP à brancher (Phase 4)."}


def build_default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(Tool(
        name="explain_kpi",
        description="Expliquer un indicateur du catalogue et sa valeur (gouverné, N/D si non branché).",
        handler=_tool_explain_kpi,
        mode="read",
    ))
    reg.register(Tool(
        name="group_score",
        description="Lire l'Indice de Gouvernance Groupe et les scores par domaine.",
        handler=_tool_group_score,
        mode="read",
    ))
    reg.register(Tool(
        name="generate_report",
        description="Générer la synthèse de gouvernance Groupe et proposer les exports.",
        handler=_tool_generate_report,
        mode="read",
    ))
    reg.register(Tool(
        name="run_connector_sync",
        description="Lancer une synchronisation d'un connecteur de données",
        handler=_tool_run_connector_sync,
        mode="write",
        sensitive=True,
        required_roles=WRITE_ROLES,
    ))
    reg.register(Tool(
        name="delete_connector",
        description="Supprimer un connecteur de données",
        handler=_tool_delete_connector,
        mode="write",
        sensitive=True,
        destructive=True,
        required_roles=WRITE_ROLES,
    ))
    reg.register(Tool(
        name="send_report_email",
        description="Envoyer un rapport par email à des destinataires",
        handler=_tool_send_report_email,
        mode="write",
        sensitive=True,
        destructive=True,
        required_roles=WRITE_ROLES,
    ))
    return reg
