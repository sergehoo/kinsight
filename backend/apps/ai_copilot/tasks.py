"""Tâches Celery du Copilot (Phase 5) — automatisations planifiées.

Gouvernance : une automatisation n'exécute automatiquement que des outils de LECTURE. Un
outil sensible/destructif passe par la file d'approbation (AIActionRequest) — jamais
d'action sensible déclenchée sans validation humaine, même planifiée.
"""

from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from .models import AIAuditLog, AIAutomation
from .tools import PermissionAwareToolExecutor, ToolError, ToolPermissionDenied, build_default_registry


def run_automation(automation_id: int) -> dict:
    """Exécute une automatisation (appelable directement — testable hors Beat)."""
    automation = AIAutomation.objects.filter(pk=automation_id).first()
    if automation is None:
        return {"status": "not_found"}

    registry = build_default_registry()
    executor = PermissionAwareToolExecutor(registry)
    actor = automation.created_by  # l'automatisation agit avec les droits de son créateur

    try:
        tool = registry.get(automation.tool_name)
    except ToolError as exc:
        tool = None
        outcome = {"status": "error", "error": str(exc)}

    if tool is not None and tool.needs_approval:
        # Gouvernance : un planificateur NON supervisé ne doit jamais initier une action
        # sensible/destructive. On bloque (sans exécuter ni créer de demande automatique).
        outcome = {
            "status": "blocked",
            "error": "Outil sensible non automatisable — déclenchement manuel avec validation requis.",
        }
    elif tool is not None:
        try:
            outcome = executor.execute(automation.tool_name, automation.args, actor, automation.context, conversation=None)
        except ToolPermissionDenied as exc:
            outcome = {"status": "denied", "error": str(exc)}
        except ToolError as exc:
            outcome = {"status": "error", "error": str(exc)}

    automation.last_run_at = timezone.now()  # le tick a eu lieu (le statut réel est dans outcome/audit)
    automation.save(update_fields=["last_run_at"])
    AIAuditLog.record(
        user=actor, action="automation_run",
        detail={"automation": automation.name, "tool": automation.tool_name, "outcome_status": outcome.get("status")},
    )
    return outcome


@shared_task(name="ai_copilot.run_due_automations")
def run_due_automations() -> dict:
    """Tâche périodique (Beat) : exécute les automatisations dues."""
    now = timezone.now()
    ran = 0
    for automation in AIAutomation.objects.filter(enabled=True):
        if automation.is_due(now):
            run_automation(automation.pk)
            ran += 1
    return {"ran": ran}
