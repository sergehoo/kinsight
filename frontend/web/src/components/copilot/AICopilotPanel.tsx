import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useLocation } from "react-router-dom";

import { useApproveAction, useCopilotChat, useRejectAction } from "@/api/copilot";
import { downloadGroupExport } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { getModuleFromPath } from "@/config/modules.config";
import { EASE_OUT } from "@/lib/motion";
import { SUBSIDIARIES, useFilters } from "@/store/filters";
import type { CopilotAction, CopilotMessage } from "@/types/copilot";

const SUGGESTIONS = [
  "Quel est le DSO finance ?",
  "Masse salariale du trimestre",
  "Taux de commercialisation immobilier",
  "Explique le taux de turnover RH",
];

function Sparkle({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.8 4.7L18.5 9l-4.7 1.8L12 15l-1.8-4.2L5.5 9l4.7-1.3L12 3z" />
      <path d="M19 14l.9 2.3L22 17l-2.1.7L19 20l-.9-2.3L16 17l2.1-.7L19 14z" />
    </svg>
  );
}

function ActionCard({ action }: { action: CopilotAction }) {
  const { year, quarter, subsidiary } = useFilters();
  const approve = useApproveAction();
  const reject = useRejectAction();
  const [decision, setDecision] = React.useState<string | null>(null);

  if (action.status === "done") {
    const exports = action.result?.exports;
    return (
      <div className="mt-2.5 rounded-xl border border-[#42BFA0]/30 bg-[rgba(66,191,160,0.08)] px-3 py-2.5">
        <div className="text-[11px] font-bold text-[#1E8A6E]">✓ Action exécutée · {action.tool}</div>
        {exports ? (
          <div className="mt-2 flex gap-1.5">
            <button type="button" onClick={() => downloadGroupExport("xlsx", year, quarter, subsidiary)} className="rounded-full bg-[#16191A] px-3 py-1 text-[11px] font-bold text-white">Excel</button>
            <button type="button" onClick={() => downloadGroupExport("pdf", year, quarter, subsidiary)} className="rounded-full bg-[#16191A] px-3 py-1 text-[11px] font-bold text-white">PDF</button>
          </div>
        ) : null}
      </div>
    );
  }
  if (action.status === "approval_required" && action.request_id) {
    const done = decision ?? (approve.data?.status || (reject.data ? "rejected" : null));
    return (
      <div className="mt-2.5 rounded-xl border border-[#E0801E]/35 bg-[rgba(224,128,30,0.08)] px-3 py-2.5">
        <div className="text-[11px] font-bold text-[#B8651A]">
          ⚠ Validation requise · {action.tool}{action.destructive ? " · double validation (2 personnes)" : ""}
        </div>
        <div className="mt-1 text-[11.5px] font-medium text-[#5A4A35]">{action.summary}</div>
        {done ? (
          <div className={`mt-2 text-[11px] font-bold ${done === "error" ? "text-[#B0223F]" : "text-[#16191A]"}`}>
            {done === "error" ? "Échec de la décision — réessayez." : `Statut : ${done}`}
          </div>
        ) : (
          <div className="mt-2 flex gap-1.5">
            <button
              type="button"
              disabled={approve.isPending}
              onClick={() => {
                if (action.destructive && !window.confirm("Action destructrice. Confirmer votre validation ? (une 2e personne devra aussi valider)")) return;
                approve.mutate(action.request_id as string, { onSuccess: (r) => setDecision(r.status), onError: () => setDecision("error") });
              }}
              className="rounded-full bg-[#1E8A6E] px-3 py-1 text-[11px] font-bold text-white disabled:opacity-50"
            >
              Approuver
            </button>
            <button
              type="button"
              disabled={reject.isPending}
              onClick={() => reject.mutate({ id: action.request_id as string }, { onSuccess: () => setDecision("rejected"), onError: () => setDecision("error") })}
              className="rounded-full bg-white/80 px-3 py-1 text-[11px] font-bold text-[#B8651A]"
            >
              Rejeter
            </button>
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="mt-2.5 rounded-xl border border-[#D92B55]/30 bg-[rgba(217,43,85,0.07)] px-3 py-2 text-[11px] font-semibold text-[#B0223F]">
      {action.status === "denied" ? "Droits insuffisants pour cette action." : `Action impossible : ${action.error ?? "erreur"}`}
    </div>
  );
}

function MessageBubble({ m }: { m: CopilotMessage }) {
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-[#16191A] px-4 py-2.5 text-[13px] font-medium text-white">{m.content}</div>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[88%] rounded-2xl rounded-bl-md bg-white/75 px-4 py-3">
        {m.metric ? (
          // Badge « ancré » uniquement pour une réponse appuyée sur une métrique du catalogue.
          // (Actions → ActionCard ; refus → texte explicite ; pas de badge trompeur.)
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <span className="rounded-full px-2 py-0.5 text-[9.5px] font-bold uppercase tracking-wide" style={{ background: "rgba(66,191,160,0.16)", color: "#1E8A6E" }}>
              ancré · sourcé
            </span>
            {m.provider ? <span className="font-mono text-[9.5px] text-[#A0A6A3]">{m.provider}</span> : null}
          </div>
        ) : null}
        <p className="whitespace-pre-wrap text-[13px] font-medium leading-relaxed text-[#2C3132]">{m.content}</p>
        {m.metric ? (
          <div className="mt-2.5 flex flex-wrap gap-1.5 text-[10.5px] font-semibold text-[#586061]">
            <span className="rounded-full bg-white/80 px-2 py-0.5 font-mono">{m.metric.key}</span>
            <span className="rounded-full bg-white/80 px-2 py-0.5">Valeur : {m.value == null ? "N/D" : `${m.value} ${m.metric.unit}`}</span>
            {m.source ? <span className="rounded-full bg-white/80 px-2 py-0.5">Source : {m.source}</span> : null}
          </div>
        ) : null}
        {m.action ? <ActionCard action={m.action} /> : null}
      </div>
    </div>
  );
}

export function AICopilotPanel() {
  const [open, setOpen] = React.useState(false);
  const [fullscreen, setFullscreen] = React.useState(false);
  const [input, setInput] = React.useState("");
  const [messages, setMessages] = React.useState<CopilotMessage[]>([]);
  const [conversationId, setConversationId] = React.useState<string | undefined>(undefined);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  const { pathname } = useLocation();
  const { year, quarter, subsidiary } = useFilters();
  const chat = useCopilotChat();
  const module = getModuleFromPath(pathname);
  const subLabel = SUBSIDIARIES.find((s) => s.code === subsidiary)?.label ?? "Toutes filiales";

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, chat.isPending]);

  const send = (text: string) => {
    const msg = text.trim();
    if (!msg || chat.isPending) return;
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setInput("");
    chat.mutate(
      { message: msg, conversation_id: conversationId, context: { module: module?.id, page: pathname, year, quarter, subsidiary } },
      {
        onSuccess: (r) => {
          setConversationId(r.conversation_id);
          setMessages((m) => [
            ...m,
            { role: "assistant", content: r.answer, provider: r.provider, grounded: r.grounded, metric: r.metric, value: r.value, source: r.source, action: r.action },
          ]);
        },
        onError: () =>
          setMessages((m) => [...m, { role: "assistant", content: "Le Copilot est momentanément indisponible.", grounded: false, metric: null }]),
      },
    );
  };

  const reset = () => {
    setMessages([]);
    setConversationId(undefined);
  };

  return (
    <>
      {/* Lanceur flottant global */}
      <motion.button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Ouvrir le Copilot IA"
        className="fixed bottom-6 right-6 z-[60] flex h-14 items-center gap-2 rounded-full pl-4 pr-5 text-[13px] font-bold text-white shadow-[0_18px_44px_rgba(36,38,38,0.30)]"
        style={{ background: "linear-gradient(135deg,#2A2D2D,#101111)" }}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: open ? 0 : 1, scale: open ? 0.9 : 1, pointerEvents: open ? "none" : "auto" }}
        whileHover={{ y: -2 }}
      >
        <span style={{ color: "#FF8735" }}><Sparkle /></span>
        Copilot
      </motion.button>

      <AnimatePresence>
        {open ? (
          <motion.aside
            key="copilot"
            className={`fixed z-[61] flex flex-col overflow-hidden ${fullscreen ? "inset-4 rounded-[28px]" : "bottom-5 right-5 top-5 w-[min(440px,calc(100vw-2.5rem))] rounded-[26px]"}`}
            style={{ ...glass, background: "linear-gradient(160deg,rgba(255,255,255,0.92),rgba(240,245,246,0.88))" }}
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 40 }}
            transition={{ duration: 0.32, ease: EASE_OUT }}
          >
            {/* En-tête */}
            <div className="flex items-center justify-between gap-2 border-b border-white/60 px-5 py-3.5">
              <div className="flex items-center gap-2">
                <span className="grid h-8 w-8 place-items-center rounded-full text-white" style={{ background: "linear-gradient(135deg,#2A2D2D,#101111)" }}>
                  <span style={{ color: "#FF8735" }}><Sparkle size={16} /></span>
                </span>
                <div>
                  <div className="text-[14px] font-bold leading-none text-[#16191A]">K-Insight Copilot</div>
                  <div className="mt-0.5 text-[10.5px] font-semibold text-[#8A9291]">Ancré sur le Data Warehouse · jamais d'invention</div>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button type="button" onClick={reset} aria-label="Nouvelle conversation" className="grid h-8 w-8 place-items-center rounded-full bg-white/60 text-[#42474A] hover:bg-white">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M3 12a9 9 0 1 0 3-6.7M3 4v4h4" /></svg>
                </button>
                <button type="button" onClick={() => setFullscreen((v) => !v)} aria-label="Plein écran" className="grid h-8 w-8 place-items-center rounded-full bg-white/60 text-[#42474A] hover:bg-white">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></svg>
                </button>
                <button type="button" onClick={() => setOpen(false)} aria-label="Fermer" className="grid h-8 w-8 place-items-center rounded-full bg-white/60 text-[#42474A] hover:bg-white">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
                </button>
              </div>
            </div>

            {/* Contexte courant */}
            <div className="flex flex-wrap items-center gap-1.5 border-b border-white/50 px-5 py-2 text-[10.5px] font-bold text-[#586061]">
              <span className="rounded-full bg-white/65 px-2.5 py-1">{module?.label ?? "Groupe"}</span>
              <span className="rounded-full bg-white/65 px-2.5 py-1">T{quarter} {year}</span>
              <span className="rounded-full bg-white/65 px-2.5 py-1">{subLabel}</span>
            </div>

            {/* Conversation */}
            <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
              {messages.length === 0 ? (
                <div className="grid gap-3">
                  <p className="text-[13px] font-medium leading-relaxed text-[#3C4142]">
                    Posez une question sur vos indicateurs, scores et alertes. Je réponds uniquement à partir de données
                    réelles ; sinon je le dis (jamais de chiffre inventé).
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {SUGGESTIONS.map((s) => (
                      <button key={s} type="button" onClick={() => send(s)} className="rounded-full border border-white/70 bg-white/55 px-3 py-1.5 text-[11px] font-semibold text-[#586061] hover:bg-white">
                        {s}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map((m, i) => <MessageBubble key={i} m={m} />)
              )}
              {chat.isPending ? (
                <div className="flex justify-start"><div className="rounded-2xl bg-white/70 px-4 py-2.5 text-[12px] font-semibold text-[#8A9291]">Le Copilot analyse…</div></div>
              ) : null}
            </div>

            {/* Saisie */}
            <form
              className="flex items-end gap-2 border-t border-white/60 p-3"
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
            >
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                rows={1}
                placeholder="Demandez au Copilot…"
                className="max-h-28 min-h-[44px] flex-1 resize-none rounded-2xl border border-white/70 bg-white/80 px-4 py-3 text-[13px] font-medium text-[#1A1F1F] outline-none placeholder:text-[#9AA09D]"
              />
              <button
                type="submit"
                disabled={chat.isPending || !input.trim()}
                aria-label="Envoyer"
                className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-white shadow-[0_12px_24px_rgba(0,0,0,0.16)] transition-transform hover:-translate-y-0.5 disabled:opacity-40"
                style={{ background: "linear-gradient(135deg,#2A2D2D,#101111)" }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z" /></svg>
              </button>
            </form>
          </motion.aside>
        ) : null}
      </AnimatePresence>
    </>
  );
}
