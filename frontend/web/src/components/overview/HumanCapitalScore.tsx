import * as React from "react";
import { motion } from "framer-motion";

import { useHrScore } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { Gauge } from "@/components/overview/Gauge";
import { EASE_OUT } from "@/lib/motion";
import { useFilters } from "@/store/filters";
import type { HrScoreResponse } from "@/types/governance";

/** Couleur par dimension — clé miroir du domaine pur `kpi/hr_score.py`. */
const DIM_COLORS: Record<string, string> = {
  effectifs_stabilite: "#416FF4",
  presence_ponctualite: "#2D74E0",
  productivite: "#FF8735",
  recrutement: "#7A5AF8",
  performance: "#42BFA0",
  formation_competences: "#E08A1E",
  engagement_climat: "#8A63D2",
  sante_securite: "#D92B55",
  conformite: "#5B6470",
};

/** Repli gouverné : 9 dimensions, aucun score (tant que le mart n'est pas branché). */
const FALLBACK_DIMENSIONS: HrScoreResponse["dimensions"] = [
  { key: "effectifs_stabilite", label: "Effectifs & stabilité", weight: 15, score: null },
  { key: "presence_ponctualite", label: "Présence & ponctualité", weight: 10, score: null },
  { key: "productivite", label: "Productivité", weight: 15, score: null },
  { key: "recrutement", label: "Recrutement", weight: 10, score: null },
  { key: "performance", label: "Performance", weight: 15, score: null },
  { key: "formation_competences", label: "Formation & compétences", weight: 10, score: null },
  { key: "engagement_climat", label: "Engagement & climat social", weight: 10, score: null },
  { key: "sante_securite", label: "Santé & sécurité", weight: 10, score: null },
  { key: "conformite", label: "Conformité RH", weight: 5, score: null },
];

const FILIALE_TO_CODE: Record<string, string> = { "K-Express": "KRE", "K-Shield": "KSH", MyKaydan: "MYK" };
const MONTH_LABELS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jui", "Aoû", "Sep", "Oct", "Nov", "Déc"];

const fmtScore = (n: number | null | undefined): string => (n == null ? "N/D" : n.toFixed(1));
// Largeur de barre : 0 % si N/D (jamais de remplissage fictif — ADR-0007), bornée 0..100.
const barWidth = (n: number | null): string => (n == null ? "0%" : `${Math.max(0, Math.min(100, n))}%`);

/** Tendance : compare les deux derniers points non nuls de la courbe. */
function trendDelta(trend: HrScoreResponse["trend"]): { dir: "up" | "down" | "flat"; delta: number | null } {
  const pts = trend.filter((t) => t.score != null).map((t) => t.score as number);
  if (pts.length < 2) return { dir: "flat", delta: null };
  const delta = +(pts[pts.length - 1] - pts[pts.length - 2]).toFixed(1);
  return { dir: delta > 0.05 ? "up" : delta < -0.05 ? "down" : "flat", delta };
}

// Drill-down : filiale → département → équipe → collaborateur.
const DRILL_LEVELS = ["Filiale", "Département", "Équipe", "Collaborateur"];

function childrenAt(depth: number): { label: string }[] {
  if (depth === 0) return [{ label: "K-Express" }, { label: "K-Shield" }, { label: "MyKaydan" }];
  if (depth === 1) return [{ label: "Direction Opérations" }, { label: "Direction Commerciale" }, { label: "Direction Support" }];
  if (depth === 2) return [{ label: "Équipe A" }, { label: "Équipe B" }, { label: "Équipe C" }];
  if (depth === 3) return [{ label: "Collaborateur ··· 01" }, { label: "Collaborateur ··· 02" }, { label: "Collaborateur ··· 03" }];
  return [];
}

function ScoreDrilldown({ bySubsidiary }: { bySubsidiary: HrScoreResponse["by_subsidiary"] }) {
  const [path, setPath] = React.useState<string[]>([]);
  const depth = path.length;
  const isLeaf = depth >= 4;
  const rows = childrenAt(depth);
  // Niveau filiale (depth 0) : score réel issu du mart ; niveaux plus fins → N/D (sources à connecter).
  const scoreFor = (label: string): number | null => {
    if (depth !== 0) return null;
    const code = FILIALE_TO_CODE[label];
    return bySubsidiary.find((s) => s.code === code)?.score ?? null;
  };

  return (
    <div className="rounded-[20px] bg-white/55 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Drill-down du score</div>
        <div className="rounded-full bg-[#EEF1FB] px-2.5 py-1 text-[11px] font-bold text-[#185FA5]">{isLeaf ? "Collaborateur" : DRILL_LEVELS[depth]}</div>
      </div>

      {/* Fil d'Ariane */}
      <div className="mb-3 flex flex-wrap items-center gap-1.5 text-[12px] font-semibold">
        <button type="button" onClick={() => setPath([])} className={depth === 0 ? "text-[#16191A]" : "text-[#416FF4] hover:underline"}>Groupe</button>
        {path.map((p, i) => (
          <span key={`${p}-${i}`} className="flex items-center gap-1.5">
            <span className="text-[#C7CCC9]">›</span>
            <button type="button" onClick={() => setPath(path.slice(0, i + 1))} className={i === path.length - 1 ? "text-[#16191A]" : "text-[#416FF4] hover:underline"}>{p}</button>
          </span>
        ))}
      </div>

      {isLeaf ? (
        <div className="rounded-xl bg-white/70 px-4 py-6 text-center">
          <div className="text-[14px] font-bold text-[#16191A]">{path[path.length - 1]}</div>
          <div className="mt-1 text-[28px] font-extrabold text-[#16191A]">N/D<span className="text-[15px] font-bold text-[#9AA09D]"> /100</span></div>
          <div className="mt-1 text-[11px] font-semibold text-[#A0A6A3]">Score individuel — `dim_employee` à connecter</div>
        </div>
      ) : (
        <div className="grid gap-2">
          {rows.map((r) => {
            const sc = scoreFor(r.label);
            return (
              <button
                key={r.label}
                type="button"
                onClick={() => setPath([...path, r.label])}
                className="flex items-center gap-3 rounded-xl bg-white/70 px-3 py-2.5 text-left transition-colors hover:bg-white"
              >
                <span className="min-w-0 flex-1 truncate text-[13px] font-semibold text-[#2C3132]">{r.label}</span>
                <span className="relative hidden h-2 w-24 overflow-hidden rounded-full bg-[#ECEEF0] sm:block">
                  <span className="absolute inset-y-0 left-0 rounded-full bg-[#416FF4]" style={{ width: barWidth(sc), opacity: sc == null ? 0 : 0.9 }} />
                </span>
                <span className={`w-16 shrink-0 text-right text-[12px] font-bold ${sc == null ? "text-[#A0A6A3]" : "text-[#16191A]"}`}>{fmtScore(sc)} /100</span>
                <span className="shrink-0 text-[#C7CCC9]">→</span>
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-3 text-[11px] font-semibold text-[#A0A6A3]">
        {depth === 0
          ? "Filiales : score réel (mart.hr_score). Niveaux plus fins → dim_department · dim_team · dim_employee à connecter."
          : "Entités & scores à connecter : dim_department → dim_team → dim_employee."}
      </div>
    </div>
  );
}

export function HumanCapitalScore() {
  const { year, quarter, subsidiary } = useFilters();
  const { data, isLoading } = useHrScore(year, quarter, subsidiary);

  const available = Boolean(data?.available);
  const global = data?.global ?? null;
  const dimensions = data?.dimensions?.length ? data.dimensions : FALLBACK_DIMENSIONS;
  const bySubsidiary = data?.by_subsidiary ?? [];
  const trend = data?.trend ?? [];
  const { dir, delta } = trendDelta(trend);
  const trendArrow = dir === "up" ? "↑" : dir === "down" ? "↓" : "→";
  const trendLabel = available && delta != null
    ? `Tendance ${trendArrow} ${delta > 0 ? "+" : ""}${delta} pts`
    : "Tendance · mart à connecter";

  return (
    <motion.section
      className="rounded-[30px] p-7"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.82),rgba(243,248,249,0.55))" }}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE_OUT }}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8A9291]">Score de gouvernance RH</p>
          <h3 className="mt-1 text-[22px] font-semibold text-[#151818]">Human Capital Score</h3>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-[#EEF1FB] px-3 py-1.5 text-[11px] font-bold text-[#185FA5]">
          <span className={`h-1.5 w-1.5 rounded-full ${available ? "bg-[#42BFA0]" : "bg-[#416FF4]"}`} />
          {isLoading ? "Chargement…" : available ? "Données EDW — réel" : "Données EDW — gouverné"}
        </span>
      </div>

      <div className="mt-5 grid gap-7 lg:grid-cols-[260px_minmax(0,1fr)]">
        {/* Jauge globale */}
        <div className="flex flex-col items-center justify-center rounded-[24px] bg-white/55 p-5">
          <div className="relative h-[120px] w-[210px]">
            <Gauge value={global} color="#416FF4" />
            <div className="absolute inset-x-0 bottom-1 text-center">
              <div className="text-[34px] font-extrabold leading-none text-[#16191A]">{fmtScore(global)}<span className="text-[16px] font-bold text-[#9AA09D]"> /100</span></div>
            </div>
          </div>
          <div className="mt-2 flex items-center gap-2 text-[13px] font-semibold text-[#8A9291]">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-[#EEF0F0]">{trendArrow}</span>
            {trendLabel}
          </div>
        </div>

        {/* Dimensions pondérées */}
        <div className="grid gap-2.5">
          {dimensions.map((d, i) => (
            <motion.div
              key={d.key}
              className="flex items-center gap-3"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + i * 0.04, duration: 0.4, ease: EASE_OUT }}
            >
              <span className="w-[210px] shrink-0 truncate text-[13px] font-semibold text-[#3C4142]">{d.label}</span>
              <span className="w-10 shrink-0 text-right text-[12px] font-bold text-[#9AA09D]">{d.weight}%</span>
              <span className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-[#ECEEF0]">
                <span
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ background: DIM_COLORS[d.key] ?? "#416FF4", width: barWidth(d.score), opacity: d.score == null ? 0 : 0.92 }}
                />
              </span>
              <span className={`w-11 shrink-0 text-right text-[12px] font-bold ${d.score == null ? "text-[#A0A6A3]" : "text-[#16191A]"}`}>{fmtScore(d.score)}</span>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Par filiale */}
      <div className="mt-6 rounded-[20px] bg-white/55 p-4">
        <div className="mb-3 text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Score par filiale</div>
        <div className="grid gap-3 sm:grid-cols-3">
          {(bySubsidiary.length ? bySubsidiary : [{ code: "KRE", score: null }, { code: "KSH", score: null }, { code: "MYK", score: null }]).map((s) => (
            <div key={s.code} className="rounded-xl bg-white/70 px-4 py-3">
              <div className="text-[12px] font-bold text-[#8A9291]">{s.code}</div>
              <div className="mt-0.5 text-[22px] font-extrabold text-[#16191A]">{fmtScore(s.score)}<span className="text-[12px] font-bold text-[#9AA09D]"> /100</span></div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#ECEEF0]">
                <span className="block h-full rounded-full bg-[#416FF4]" style={{ width: barWidth(s.score), opacity: s.score == null ? 0 : 0.9 }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Évolution 12 mois */}
        <div className="rounded-[20px] bg-white/55 p-4">
          <div className="mb-3 text-[12px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">Évolution · 12 mois</div>
          <div className="flex h-16 items-end gap-1.5">
            {(trend.length ? trend.slice(-12) : Array.from({ length: 12 }, () => ({ month: "", score: null }))).map((t, m) => {
              const h = t.score == null ? 18 : Math.max(6, Math.min(100, t.score));
              return (
                <span
                  key={t.month || m}
                  title={t.month ? `${t.month} · ${fmtScore(t.score)}` : undefined}
                  className="flex-1 rounded-t"
                  style={{ height: `${h}%`, background: t.score == null ? "#DDE2E0" : "#416FF4", opacity: t.score == null ? 1 : 0.85 }}
                />
              );
            })}
          </div>
          <div className="mt-1 flex justify-between text-[10px] font-semibold text-[#A0A6A3]">
            {trend.length ? (
              <>
                <span>{MONTH_LABELS[new Date(trend.slice(-12)[0].month).getMonth()] ?? ""}</span>
                <span>{MONTH_LABELS[new Date(trend[trend.length - 1].month).getMonth()] ?? ""}</span>
              </>
            ) : (
              <span>mart.hr_score à connecter</span>
            )}
          </div>
        </div>

        {/* Drill-down filiale → département → équipe → collaborateur */}
        <ScoreDrilldown bySubsidiary={bySubsidiary} />
      </div>
    </motion.section>
  );
}
