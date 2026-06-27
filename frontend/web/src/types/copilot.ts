/** Types du K-Insight AI Copilot (miroir de l'API /api/v1/ai/). */

export interface CopilotMetric {
  key: string;
  label: string;
  domain: string;
  unit: string;
  direction: string;
  mart: string;
  description: string;
}

export interface CopilotAction {
  status: "done" | "approval_required" | "denied" | "error";
  tool: string;
  result?: { exports?: Record<string, string>; [k: string]: unknown };
  request_id?: string;
  summary?: string;
  destructive?: boolean;
  required_confirmations?: number;
  error?: string;
}

export interface CopilotChatResponse {
  conversation_id: string;
  message_id: number;
  answer: string;
  provider: string;
  latency_ms: number;
  grounded: boolean;
  metric: CopilotMetric | null;
  value: number | null;
  source: string | null;
  action: CopilotAction | null;
  attempts: { provider: string; ok: boolean; latency_ms?: number; error?: string }[];
  context: Record<string, unknown>;
}

export interface CopilotMessage {
  role: "user" | "assistant";
  content: string;
  provider?: string;
  grounded?: boolean;
  metric?: CopilotMetric | null;
  value?: number | null;
  source?: string | null;
  action?: CopilotAction | null;
}
