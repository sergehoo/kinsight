/** Contrat de métrique unifié K-Insight.
 *
 *  TOUTE source (Kaydan Shield, Odoo, SAP, EDW, API interne) est normalisée ici avant
 *  d'atteindre un composant. Conséquence voulue : aucun composant d'UI ne connaît la
 *  forme d'une réponse Shield ou Odoo — changer de source ne touche qu'un adaptateur.
 *
 *  Gouvernance (ADR-0007) : la structure elle-même interdit d'afficher un chiffre non
 *  servi par une source. `value` reste `null` tant que la donnée n'existe pas, et
 *  `assertGoverned` transforme une violation en erreur visible en développement.
 */
import type { DataState, SignalSeverity } from "@/components/ui/kit";

/** D'où vient le chiffre — trois statuts épistémiques à ne pas confondre.
 *  `measured` : lu tel quel dans la source.
 *  `computed` : calculé par K-Insight → `formula` obligatoire, donc auditable.
 *  `predicted`: issu d'un modèle → `confidence` obligatoire, jamais présenté comme un fait. */
export type DataLevel = "measured" | "computed" | "predicted";

export const LEVEL_LABEL: Record<DataLevel, string> = {
  measured: "Mesuré",
  computed: "Calculé",
  predicted: "Prédit",
};

export interface KSeriesPoint {
  label: string;
  value: number | null;
  /** Comparatif optionnel : N-1, budget, objectif… */
  compare?: number | null;
}

export interface KBreakdownItem {
  key: string;
  label: string;
  value: number | null;
  status?: DataState;
  drilldownUrl?: string;
}

export interface KMetric {
  id: string;
  title: string;
  value: number | null;
  unit?: string;
  /** Période couverte, ex. « T1 2026 », « aujourd'hui ». */
  period?: string;
  previousValue?: number | null;
  /** Écart absolu vs `previousValue`. Laisser vide : `deltaOf` le calcule sans inventer. */
  delta?: number | null;
  target?: number | null;
  status: DataState;
  severity?: SignalSeverity;
  series?: KSeriesPoint[];
  breakdown?: KBreakdownItem[];
  /** Code machine de la source : kaydan_shield | odoo_hr | edw | sap | api_interne. */
  source: string;
  sourceLabel: string;
  updatedAt?: string;
  stale?: boolean;
  /** 0 → 1. Obligatoire si `level === "predicted"`. */
  confidence?: number | null;
  drilldownUrl?: string;
  level: DataLevel;
  /** Obligatoire si `level` vaut computed ou predicted. */
  formula?: string;
  /** Champ d'origine côté source, pour une mesure. */
  sourceField?: string;
}

/* ── Règles de gouvernance ─────────────────────────────────────────────────── */

/** Les deux seuls états autorisés à porter un chiffre. `stale` est une donnée
 *  réellement observée, simplement plus fraîche ailleurs — elle reste affichable
 *  à condition d'être signalée comme telle. */
export function mayCarryValue(status: DataState): boolean {
  return status === "connected" || status === "stale";
}

export function hasValue(metric: KMetric): boolean {
  return mayCarryValue(metric.status) && metric.value !== null && metric.value !== undefined;
}

/** Écart vs période précédente. Renvoie null plutôt que 0 quand il est indéterminable :
 *  un 0 signifierait « stable », ce qui serait une affirmation non fondée. */
export function deltaOf(metric: KMetric): number | null {
  if (metric.delta !== undefined && metric.delta !== null) return metric.delta;
  if (!hasValue(metric)) return null;
  if (metric.previousValue === null || metric.previousValue === undefined) return null;
  return (metric.value as number) - metric.previousValue;
}

/** Variation relative en %, ou null si la base est nulle/absente (division impossible). */
export function deltaPercentOf(metric: KMetric): number | null {
  const delta = deltaOf(metric);
  const base = metric.previousValue;
  if (delta === null || base === null || base === undefined || base === 0) return null;
  return (delta / Math.abs(base)) * 100;
}

/** Écart à l'objectif. null si aucun objectif n'est défini — ne jamais supposer 100 %. */
export function varianceOf(metric: KMetric): { absolute: number; percent: number | null } | null {
  if (!hasValue(metric)) return null;
  if (metric.target === null || metric.target === undefined) return null;
  const absolute = (metric.value as number) - metric.target;
  return { absolute, percent: metric.target === 0 ? null : (absolute / Math.abs(metric.target)) * 100 };
}

/** Une série n'est traçable que si elle porte au moins un point réel.
 *  Sert de garde-fou : sans cela on tracerait une courbe plate à zéro. */
export function hasRealSeries(series: KSeriesPoint[] | undefined): boolean {
  return Boolean(series && series.some((p) => p.value !== null && p.value !== undefined));
}

export function hasRealBreakdown(items: KBreakdownItem[] | undefined): boolean {
  return Boolean(items && items.some((i) => i.value !== null && i.value !== undefined));
}

/** Replie l'état de la métrique avec le contexte réseau et la fraîcheur.
 *  Une métrique servie par le cache ne peut pas rester annoncée « connected ». */
export function effectiveStatus(metric: KMetric, ctx: { online?: boolean } = {}): DataState {
  if (ctx.online === false && !hasValue(metric)) return "offline";
  if (metric.stale && metric.status === "connected") return "stale";
  return metric.status;
}

/** Invariants du contrat. Bruyant en développement, silencieux en production :
 *  une violation est un bug de normalisation, pas une erreur utilisateur. */
export function assertGoverned(metric: KMetric): void {
  if (!import.meta.env.DEV) return;
  const bug = (why: string) => console.error(`[KMetric] ${metric.id} — ${why}`);
  if (metric.value !== null && metric.value !== undefined && !mayCarryValue(metric.status)) {
    bug(`porte une valeur en état « ${metric.status} » : seuls connected et stale le permettent.`);
  }
  if ((metric.level === "computed" || metric.level === "predicted") && !metric.formula) {
    bug(`niveau « ${metric.level} » sans formule documentée.`);
  }
  if (metric.level === "predicted" && (metric.confidence === null || metric.confidence === undefined)) {
    bug("prédiction sans indice de confiance.");
  }
  if (metric.level === "measured" && metric.formula) {
    bug("mesure porteuse d'une formule : c'est un calcul, pas une mesure.");
  }
}

/* ── Fabriques ─────────────────────────────────────────────────────────────── */

/** Métrique déclarée mais non alimentée. C'est l'état par défaut honnête de tout
 *  KPI dont la source n'est pas encore raccordée. */
export function declaredMetric(
  spec: Pick<KMetric, "id" | "title" | "source" | "sourceLabel" | "level"> &
    Partial<Pick<KMetric, "unit" | "formula" | "sourceField" | "period" | "drilldownUrl" | "target">>,
): KMetric {
  return { value: null, status: "disconnected", ...spec };
}
