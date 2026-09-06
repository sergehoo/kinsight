/** Cartes décisionnelles K-Insight, pilotées par le contrat KMetric.
 *
 *  Ce module ne recrée RIEN de ce que `kit.tsx` fournit déjà : MetricCard,
 *  SignalCard, EmptyChartState, StateBadge, Skeleton et SourceMeta y restent la
 *  référence. On n'ajoute ici que les briques réellement absentes :
 *  VarianceCard, RankingCard, DecisionInsightCard, SourceHealth, LevelBadge.
 *
 *  `AlertCard` est volontairement un alias de `SignalCard` : le composant demandé
 *  par la mission existe déjà sous un autre nom, le dupliquer serait une régression.
 */
import * as React from "react";
import { Link } from "react-router-dom";

import {
  SignalCard,
  SourceMeta,
  StateBadge,
  STATE_META,
  type DataState,
  type SignalSeverity,
} from "@/components/ui/kit";
import { glass } from "@/components/chrome/theme";
import { AnimatedNumber } from "@/components/overview/AnimatedNumber";
import {
  deltaPercentOf,
  hasValue,
  LEVEL_LABEL,
  varianceOf,
  type DataLevel,
  type KBreakdownItem,
  type KMetric,
} from "@/lib/kmetric";

/** La brique « alerte » de la mission existe déjà dans le kit sous le nom SignalCard. */
export { SignalCard as AlertCard } from "@/components/ui/kit";

const CARD =
  "flex min-w-0 flex-col overflow-hidden rounded-[22px] p-4 transition-all duration-300 hover:-translate-y-0.5 sm:p-5";
const CARD_STYLE: React.CSSProperties = {
  ...glass,
  background: "linear-gradient(135deg,rgba(255,255,255,0.86),rgba(243,248,249,0.58))",
};

/* ── LevelBadge : mesuré / calculé / prédit ────────────────────────────────── */
const LEVEL_STYLE: Record<DataLevel, { c: string; bg: string }> = {
  measured: { c: "#4A5150", bg: "rgba(74,81,80,0.10)" },
  computed: { c: "#3E6BA8", bg: "rgba(62,107,168,0.12)" },
  predicted: { c: "#8A63D2", bg: "rgba(138,99,210,0.14)" },
};

/** Signale l'origine épistémique du chiffre. Une valeur calculée expose sa formule
 *  au survol, une prédiction sa confiance : le lecteur sait toujours ce qu'il lit. */
export function LevelBadge({
  level,
  formula,
  confidence,
}: {
  level: DataLevel;
  formula?: string;
  confidence?: number | null;
}) {
  const style = LEVEL_STYLE[level];
  const title =
    level === "computed" && formula
      ? `Calculé : ${formula}`
      : level === "predicted"
        ? `Prédiction${confidence != null ? ` — confiance ${Math.round(confidence * 100)} %` : ""}`
        : "Mesure lue directement dans la source";
  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-[0.05em]"
      style={{ background: style.bg, color: style.c }}
      title={title}
    >
      {LEVEL_LABEL[level]}
      {level === "predicted" && confidence != null ? ` ${Math.round(confidence * 100)}%` : ""}
    </span>
  );
}

/* ── VarianceCard : réel vs objectif / budget / N-1 ────────────────────────── */
export function VarianceCard({ metric, targetLabel = "objectif" }: { metric: KMetric; targetLabel?: string }) {
  const variance = varianceOf(metric);
  const deltaPercent = deltaPercentOf(metric);
  const meta = STATE_META[metric.status];
  const favourable = variance ? variance.absolute >= 0 : null;

  return (
    <article className={CARD} style={CARD_STYLE}>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-[#586061]">{metric.title}</span>
        <div className="flex shrink-0 items-center gap-1">
          <LevelBadge level={metric.level} formula={metric.formula} confidence={metric.confidence} />
          <StateBadge state={metric.status} />
        </div>
      </div>

      <div className="mt-2.5 flex items-end gap-1.5">
        <span className="text-[clamp(22px,4.5vw,30px)] font-extrabold leading-none text-[#16191A]">
          {hasValue(metric) ? <AnimatedNumber value={String(metric.value)} /> : meta.placeholder}
        </span>
        {metric.unit && hasValue(metric) ? (
          <span className="pb-0.5 text-[12px] font-bold text-[#9AA09D]">{metric.unit}</span>
        ) : null}
      </div>

      {variance ? (
        <div className="mt-2 space-y-1">
          <div className="flex items-baseline justify-between gap-2 text-[11.5px] font-bold">
            <span className="text-[#8C9391]">vs {targetLabel}</span>
            <span style={{ color: favourable ? "#1E8A6E" : "#D92B55" }}>
              {variance.absolute >= 0 ? "+" : ""}
              {Math.round(variance.absolute * 10) / 10}
              {metric.unit ? ` ${metric.unit}` : ""}
              {variance.percent !== null ? ` (${variance.percent >= 0 ? "+" : ""}${Math.round(variance.percent)} %)` : ""}
            </span>
          </div>
          {/* Jauge d'atteinte : bornée à 100 % pour ne pas suggérer un dépassement infini. */}
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#E8ECEA]">
            <span
              className="block h-full rounded-full transition-[width] duration-500"
              style={{
                width: `${Math.max(0, Math.min(100, ((metric.value as number) / (metric.target as number)) * 100))}%`,
                background: favourable ? "#1E8A6E" : "#D92B55",
              }}
            />
          </div>
        </div>
      ) : (
        <p className="mt-2 text-[11px] font-medium leading-snug text-[#8C9391]">
          {hasValue(metric)
            ? `Aucun ${targetLabel} défini pour cette mesure — écart non calculable.`
            : `${metric.sourceLabel} à raccorder — aucune donnée publiée.`}
        </p>
      )}

      {deltaPercent !== null ? (
        <p className="mt-1.5 text-[11px] font-semibold" style={{ color: deltaPercent >= 0 ? "#1E8A6E" : "#D92B55" }}>
          {deltaPercent >= 0 ? "+" : ""}
          {Math.round(deltaPercent)} % vs période précédente
        </p>
      ) : null}

      <SourceMeta source={metric.sourceLabel} updatedAt={metric.updatedAt} scope={metric.period} />
    </article>
  );
}

/* ── RankingCard : classement filiale / site / commercial ──────────────────── */
export function RankingCard({
  title,
  items,
  unit,
  state,
  source,
  updatedAt,
  max = 5,
}: {
  title: string;
  items: KBreakdownItem[];
  unit?: string;
  state: DataState;
  source?: string;
  updatedAt?: string;
  max?: number;
}) {
  // Les entrées sans valeur ne sont pas classées : les mettre à zéro les ferait
  // apparaître en dernier comme si elles avaient été mesurées.
  const ranked = items
    .filter((i) => i.value !== null && i.value !== undefined)
    .sort((a, b) => (b.value as number) - (a.value as number))
    .slice(0, max);
  const unranked = items.length - ranked.length;
  const top = ranked[0]?.value as number | undefined;

  return (
    <article className={CARD} style={CARD_STYLE}>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-[#586061]">{title}</span>
        <StateBadge state={state} />
      </div>

      {ranked.length ? (
        <ol className="mt-3 space-y-2">
          {ranked.map((item, index) => (
            <li key={item.key} className="min-w-0">
              <div className="flex items-baseline justify-between gap-2">
                <span className="min-w-0 truncate text-[12px] font-semibold text-[#3C4142]">
                  <span className="mr-1.5 text-[10.5px] font-bold text-[#A0A6A3]">{index + 1}.</span>
                  {item.label}
                </span>
                <span className="shrink-0 text-[12px] font-extrabold text-[#16191A]">
                  {item.value}
                  {unit ? <span className="ml-0.5 text-[10px] font-bold text-[#9AA09D]">{unit}</span> : null}
                </span>
              </div>
              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[#EDF0EE]">
                <span
                  className="ki-accent-fill block h-full rounded-full"
                  style={{ width: top ? `${((item.value as number) / top) * 100}%` : "0%" }}
                />
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-3 text-[11.5px] font-medium leading-snug text-[#8C9391]">
          Aucune entrée mesurée — le classement s'affichera dès que la source publiera des valeurs.
        </p>
      )}

      {unranked > 0 ? (
        <p className="mt-2 text-[10.5px] font-semibold text-[#A0A6A3]">
          {unranked} entrée{unranked > 1 ? "s" : ""} sans mesure, exclue{unranked > 1 ? "s" : ""} du classement.
        </p>
      ) : null}

      <SourceMeta source={source} updatedAt={updatedAt} />
    </article>
  );
}

/* ── DecisionInsightCard : aide à la décision ──────────────────────────────── */
export interface DecisionInsight {
  id: string;
  title: string;
  /** Le CONSTAT, adossé à des chiffres réels. Jamais une impression. */
  finding: string;
  impact?: string;
  severity: SignalSeverity;
  sourceLabel: string;
  /** 0 → 1. Obligatoire dès que l'insight repose sur un calcul ou un modèle. */
  confidence?: number | null;
  level: DataLevel;
  formula?: string;
  action?: { label: string; to: string };
  detectedAt?: string;
}

const SEV_COLOR: Record<SignalSeverity, string> = {
  info: "#37A0DD",
  success: "#1E8A6E",
  warning: "#E0801E",
  critical: "#D92B55",
  anomaly: "#8A63D2",
};

export function DecisionInsightCard({ insight }: { insight: DecisionInsight }) {
  const color = SEV_COLOR[insight.severity];
  return (
    <article className={CARD} style={{ ...CARD_STYLE, borderLeft: `3px solid ${color}` }}>
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 flex-1 text-[13px] font-bold leading-snug text-[#16191A]">{insight.title}</span>
        <LevelBadge level={insight.level} formula={insight.formula} confidence={insight.confidence} />
      </div>
      <p className="mt-1.5 text-[11.5px] font-medium leading-relaxed text-[#5B6261]">{insight.finding}</p>
      {insight.impact ? (
        <p className="mt-1.5 text-[11.5px] font-semibold leading-relaxed" style={{ color }}>
          Impact : {insight.impact}
        </p>
      ) : null}
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        {insight.action ? (
          <Link
            to={insight.action.to}
            className="ki-accent-ring rounded-full bg-[#16191A] px-3 py-1.5 text-[11px] font-bold text-white transition-transform hover:-translate-y-0.5"
          >
            {insight.action.label}
          </Link>
        ) : null}
      </div>
      <SourceMeta source={insight.sourceLabel} updatedAt={insight.detectedAt} />
    </article>
  );
}

/** État vide de l'aide à la décision. Il est essentiel : ne rien avoir à dire est
 *  une information, et vaut mieux qu'une recommandation fabriquée. */
export function NoInsights({ reason }: { reason: string }) {
  return (
    <article className={CARD} style={CARD_STYLE}>
      <div className="flex items-center gap-2">
        <span className="text-[12.5px] font-semibold text-[#586061]">Aide à la décision</span>
        <StateBadge state="disconnected" />
      </div>
      <p className="mt-2 text-[11.5px] font-medium leading-relaxed text-[#8C9391]">{reason}</p>
      <p className="mt-1.5 text-[10.5px] font-semibold text-[#A0A6A3]">
        Aucune recommandation n'est produite tant qu'elle ne s'appuie pas sur des données réelles.
      </p>
    </article>
  );
}

/* ── SourceHealth : état des sources alimentant un domaine ─────────────────── */
export interface SourceHealthItem {
  code: string;
  label: string;
  state: DataState;
  detail?: string;
  updatedAt?: string;
}

export function SourceHealth({ sources, title = "Sources de données" }: { sources: SourceHealthItem[]; title?: string }) {
  const connected = sources.filter((s) => s.state === "connected").length;
  return (
    <article className={CARD} style={CARD_STYLE}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[12.5px] font-semibold text-[#586061]">{title}</span>
        <span className="text-[11px] font-bold text-[#7C8384]">
          {connected}/{sources.length} connectée{sources.length > 1 ? "s" : ""}
        </span>
      </div>
      <ul className="mt-3 space-y-2">
        {sources.map((source) => (
          <li key={source.code} className="flex min-w-0 items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-[12px] font-semibold text-[#3C4142]">{source.label}</div>
              {source.detail ? (
                <div className="truncate text-[10.5px] font-medium text-[#9AA09D]">{source.detail}</div>
              ) : null}
            </div>
            <StateBadge state={source.state} />
          </li>
        ))}
      </ul>
    </article>
  );
}
