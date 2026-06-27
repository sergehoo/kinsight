import * as React from "react";
import { motion } from "framer-motion";

import { useAiQuery } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";

const SAMPLES = [
  "Quel est le taux de recouvrement ?",
  "Délai moyen de recouvrement client",
  "Taux de commercialisation des programmes",
  "Taux de turnover RH",
];

export function AiQueryBox() {
  const [question, setQuestion] = React.useState("");
  const ai = useAiQuery();

  const ask = (q: string) => {
    const value = q.trim();
    if (!value) return;
    setQuestion(value);
    ai.mutate(value);
  };

  const data = ai.data;

  return (
    <motion.section
      className="rounded-[30px] p-6"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.86),rgba(243,248,249,0.55))" }}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.48, ease: EASE_OUT }}
    >
      <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8A9291]">IA de gouvernance — ancrée</p>
      <h3 className="mt-1 text-[20px] font-semibold text-[#151818]">Interroger le catalogue</h3>
      <p className="mt-1 text-[12.5px] font-medium text-[#777C7D]">
        Réponses sourcées uniquement sur les indicateurs définis et le Data Warehouse. Aucune métrique ni
        chiffre inventé : hors catalogue, la question est refusée.
      </p>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ex. : quel est le DSO finance ?"
          className="h-11 flex-1 rounded-full border border-white/70 bg-white/75 px-5 text-[13px] font-semibold text-[#1A1F1F] outline-none placeholder:text-[#8B9394]"
        />
        <button
          type="submit"
          disabled={ai.isPending || !question.trim()}
          className="h-11 shrink-0 rounded-full bg-[#111313] px-5 text-[13px] font-bold text-white shadow-[0_12px_24px_rgba(0,0,0,0.14)] transition-transform hover:-translate-y-0.5 disabled:opacity-50"
        >
          {ai.isPending ? "…" : "Demander"}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SAMPLES.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => ask(s)}
            className="rounded-full border border-white/70 bg-white/55 px-3 py-1 text-[11px] font-semibold text-[#586061] transition-colors hover:bg-white"
          >
            {s}
          </button>
        ))}
      </div>

      {ai.isError ? (
        <div className="mt-4 rounded-xl bg-[rgba(217,43,85,0.08)] px-4 py-3 text-[13px] font-semibold text-[#D92B55]">
          Erreur lors de l'interrogation de l'IA.
        </div>
      ) : data ? (
        <div className="mt-4 rounded-2xl bg-white/72 p-4">
          <div className="flex items-center gap-2">
            <span
              className="rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide"
              style={data.grounded ? { background: "rgba(66,191,160,0.14)", color: "#1E8A6E" } : { background: "rgba(154,160,157,0.16)", color: "#6B7270" }}
            >
              {data.grounded ? "Ancré · sourcé" : "Hors catalogue · refusé"}
            </span>
            {data.metric ? (
              <span className="font-mono text-[11px] text-[#8A9291]">{data.metric.key} · {data.metric.unit}</span>
            ) : null}
          </div>
          <p className="mt-2 text-[14px] font-medium leading-relaxed text-[#2C3132]">{data.answer}</p>
          {data.metric ? (
            <div className="mt-3 flex flex-wrap gap-2 text-[11px] font-semibold text-[#586061]">
              <span className="rounded-full bg-white/70 px-2.5 py-1">Valeur : {data.value == null ? "N/D" : data.value}</span>
              <span className="rounded-full bg-white/70 px-2.5 py-1">Source : {data.source}</span>
              <span className="rounded-full bg-white/70 px-2.5 py-1">Sens : {data.metric.direction}</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </motion.section>
  );
}
