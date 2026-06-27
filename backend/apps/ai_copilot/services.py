"""Orchestration du chat Copilot : ancrage des faits → router multi-provider → persistance.

Flux gouverné : on calcule d'abord les FAITS via l'ancrage (catalogue/mart, jamais inventés),
puis le router (DeepSeek → Claude → repli) reformule autour de ces faits. Hors-ligne, la
réponse ancrée déterministe est renvoyée telle quelle. Conversation, messages, provider,
latence et tentatives sont journalisés.
"""

from __future__ import annotations

from typing import Optional

from .context import build_context
from .intent import detect_tool_intent
from .models import AIAuditLog, AIConversation, AIMessage
from .providers import AIProviderRouter, GroundedFacts
from .tools import PermissionAwareToolExecutor, ToolError, ToolPermissionDenied, build_default_registry
from .value_resolver import build_value_lookup


def _run_action(registry, message, user, context, conversation):
    """Détecte une intention d'action et l'exécute via l'exécuteur gouverné (RBAC + approbation).

    Retourne (action_dict|None, texte_assistant|None). Une action de lecture renvoie son
    résultat ; une action sensible renvoie une demande d'approbation (jamais exécutée ici)."""
    intent = detect_tool_intent(message)
    if not intent:
        return None, None
    tool_name, args = intent
    executor = PermissionAwareToolExecutor(registry)
    try:
        action = executor.execute(tool_name, args, user, context, conversation=conversation)
    except ToolPermissionDenied as exc:
        return {"status": "denied", "tool": tool_name, "error": str(exc)}, (
            f"Je ne peux pas exécuter « {tool_name} » : droits insuffisants."
        )
    except ToolError as exc:
        return {"status": "error", "tool": tool_name, "error": str(exc)}, (
            f"L'action « {tool_name} » a échoué : {exc}"
        )
    if action.get("status") == "approval_required":
        extra = " (double validation par deux personnes)" if action.get("destructive") else ""
        text = f"J'ai préparé l'action « {action['tool']} » : {action['summary']}. Validation requise avant exécution{extra}."
    else:
        text = f"Action « {action['tool']} » exécutée. Résultat disponible ci-dessous."
    return action, text


def grounded_facts(message: str, value_lookup=None) -> GroundedFacts:
    from k_insight.semantic.grounding import answer
    from k_insight.semantic.registry import CATALOG

    a = answer(CATALOG, message, value_lookup or (lambda _k: None))
    return GroundedFacts(
        grounded=a["grounded"], answer=a["answer"], metric=a["metric"], value=a["value"], source=a["source"]
    )


def chat(user, message: str, payload: Optional[dict] = None, *, conversation=None, router=None, registry=None, ip=None) -> dict:
    payload = payload or {}
    registry = registry or build_default_registry()
    router = router or AIProviderRouter()

    context = build_context(user, payload, registry)
    period = context["period"]
    lookup = build_value_lookup(user, period["year"], period["quarter"], context.get("subsidiary", "all"))

    if conversation is None:
        conversation = AIConversation.objects.create(
            user=user, title=message[:80], context=context, mode=payload.get("mode", "analyse")
        )

    # Intention d'action (mode actionnable) ? Sinon, Q&A ancrée via le router multi-provider.
    action, action_text = _run_action(registry, message, user, context, conversation)
    if action is not None:
        # Une action n'est pas un « fait ancré » du catalogue → grounded=False (l'ActionCard
        # porte l'état réel ; le résultat éventuel vient d'outils gouvernés).
        result = type("R", (), {"text": action_text, "provider": "tool", "latency_ms": 0,
                                "grounded": False, "metric_key": "", "attempts": []})()
        facts = GroundedFacts(grounded=False, answer=action_text)
    else:
        facts = grounded_facts(message, lookup)
        result = router.complete(message, context, facts)

    AIMessage.objects.create(conversation=conversation, role=AIMessage.Role.USER, content=message)
    assistant = AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.ASSISTANT,
        content=result.text,
        provider=result.provider,
        latency_ms=result.latency_ms,
        grounded=result.grounded,
        metric_key=result.metric_key,
        payload={"metric": facts.metric, "value": facts.value, "source": facts.source, "action": action},
    )
    conversation.save(update_fields=["updated_at"])

    AIAuditLog.record(
        user=user,
        action="chat",
        provider=result.provider,
        latency_ms=result.latency_ms,
        success=True,
        detail={"attempts": result.attempts, "grounded": result.grounded, "metric": result.metric_key,
                "action": (action or {}).get("status")},
        ip=ip,
    )
    return {
        "conversation_id": str(conversation.id),
        "message_id": assistant.id,
        "answer": result.text,
        "provider": result.provider,
        "latency_ms": result.latency_ms,
        "grounded": result.grounded,
        "metric": facts.metric,
        "value": facts.value,
        "source": facts.source,
        "action": action,
        "attempts": result.attempts,
        "context": context,
    }
