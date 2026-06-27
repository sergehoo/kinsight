"""API du K-Insight AI Copilot (Phase 1). Authentifié, gouverné, journalisé."""

from __future__ import annotations

import uuid

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import AIActionRequest, AIConversation
from .tools import (
    ActionApprovalService,
    PermissionAwareToolExecutor,
    ToolError,
    ToolPermissionDenied,
    build_default_registry,
)


def _registry():
    return build_default_registry()


def _conversation_payload(conv: AIConversation, with_messages: bool = False) -> dict:
    data = {
        "id": str(conv.id),
        "title": conv.title,
        "mode": conv.mode,
        "archived": conv.archived,
        "updated_at": conv.updated_at.isoformat(),
    }
    if with_messages:
        data["messages"] = [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "provider": m.provider,
                "grounded": m.grounded,
                "metric_key": m.metric_key,
                "payload": m.payload,
                "created_at": m.created_at.isoformat(),
            }
            for m in conv.messages.all()
        ]
    return data


class ChatView(APIView):
    def post(self, request):
        message = (request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "'message' est requis."}, status=status.HTTP_400_BAD_REQUEST)
        conversation = None
        conv_id = request.data.get("conversation_id")
        if conv_id:
            try:
                uuid.UUID(str(conv_id))
            except (ValueError, TypeError):
                return Response({"detail": "conversation_id invalide."}, status=status.HTTP_400_BAD_REQUEST)
            conversation = AIConversation.objects.filter(pk=conv_id, user=request.user).first()
            if conversation is None:
                return Response({"detail": "Conversation introuvable."}, status=status.HTTP_404_NOT_FOUND)
        payload = request.data.get("context") or {}
        payload.setdefault("mode", request.data.get("mode", "analyse"))
        result = services.chat(
            request.user, message, payload, conversation=conversation, ip=request.META.get("REMOTE_ADDR")
        )
        return Response(result)


class ConversationListView(APIView):
    def get(self, request):
        convs = AIConversation.objects.filter(user=request.user, archived=False)
        return Response({"count": convs.count(), "conversations": [_conversation_payload(c) for c in convs]})


class ConversationDetailView(APIView):
    def get(self, request, pk):
        conv = AIConversation.objects.filter(pk=pk, user=request.user).first()
        if conv is None:
            return Response({"detail": "Conversation introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_conversation_payload(conv, with_messages=True))

    def delete(self, request, pk):
        # Suppression scopée en une requête (ownership dans le WHERE) — pas de fenêtre de course.
        deleted, _ = AIConversation.objects.filter(pk=pk, user=request.user).delete()
        if not deleted:
            return Response({"detail": "Conversation introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ToolsListView(APIView):
    def get(self, request):
        tools = _registry().allowed_for(request.user)
        return Response(
            {
                "count": len(tools),
                "tools": [
                    {"name": t.name, "description": t.description, "mode": t.mode, "needs_approval": t.needs_approval}
                    for t in tools
                ],
            }
        )


class ToolExecuteView(APIView):
    def post(self, request):
        tool_name = request.data.get("tool")
        if not tool_name:
            return Response({"detail": "'tool' est requis."}, status=status.HTTP_400_BAD_REQUEST)
        args = request.data.get("args") or {}
        if not isinstance(args, dict):
            return Response({"detail": "'args' doit être un objet."}, status=status.HTTP_400_BAD_REQUEST)
        context = request.data.get("context") or {}
        executor = PermissionAwareToolExecutor(_registry())
        try:
            result = executor.execute(tool_name, args, request.user, context)
        except ToolPermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ToolError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class ActionListView(APIView):
    """Demandes d'action en attente d'approbation (que l'utilisateur a le droit d'approuver)."""

    def get(self, request):
        # Filtre RBAC EN BASE : on ne charge que les demandes dont l'utilisateur peut approuver
        # l'outil (pas de chargement global ni de fuite de timing sur les demandes inaccessibles).
        allowed_names = [t.name for t in _registry().allowed_for(request.user)]
        pending = AIActionRequest.objects.filter(
            status=AIActionRequest.Status.PENDING, tool_name__in=allowed_names
        )
        out = [
            {"id": str(req.id), "tool": req.tool_name, "summary": req.summary, "args": req.args,
             "requested_by": getattr(req.user, "username", None), "created_at": req.created_at.isoformat()}
            for req in pending
        ]
        return Response({"count": len(out), "actions": out})


class ActionApproveView(APIView):
    def post(self, request, pk):
        req = AIActionRequest.objects.filter(pk=pk).first()
        if req is None:
            return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
        service = ActionApprovalService(_registry())
        try:
            req = service.approve(req, request.user, context=request.data.get("context") or {})
        except ToolPermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ToolError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": str(req.id), "status": req.status, "result": req.result})


class ActionRejectView(APIView):
    def post(self, request, pk):
        req = AIActionRequest.objects.filter(pk=pk).first()
        if req is None:
            return Response({"detail": "Demande introuvable."}, status=status.HTTP_404_NOT_FOUND)
        service = ActionApprovalService(_registry())
        try:
            req = service.reject(req, request.user, note=request.data.get("note", ""))
        except ToolPermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ToolError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"id": str(req.id), "status": req.status})
