import { useMutation } from "@tanstack/react-query";

import { apiPost } from "@/lib/api";
import type { CopilotChatResponse } from "@/types/copilot";

interface ChatBody {
  message: string;
  conversation_id?: string;
  context?: Record<string, unknown>;
}

/** Envoie un message au Copilot (ancré sur le catalogue/mart, jamais inventé). */
export function useCopilotChat() {
  return useMutation<CopilotChatResponse, Error, ChatBody>({
    mutationFn: (body) => apiPost<CopilotChatResponse>("/ai/chat/", body),
  });
}

/** Approuve une action sensible proposée par le Copilot (RBAC + 4-eyes côté backend). */
export function useApproveAction() {
  return useMutation<{ id: string; status: string; result?: unknown }, Error, string>({
    mutationFn: (id) => apiPost(`/ai/actions/${id}/approve/`, {}),
  });
}

/** Rejette une action sensible proposée par le Copilot. */
export function useRejectAction() {
  return useMutation<{ id: string; status: string }, Error, { id: string; note?: string }>({
    mutationFn: ({ id, note }) => apiPost(`/ai/actions/${id}/reject/`, { note }),
  });
}
