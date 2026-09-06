/** Adaptateur Kaydan Shield → contrat KMetric.
 *
 *  C'est le SEUL module du frontend qui connaît la forme d'une réponse Shield.
 *  Tout composant en aval ne voit que des `KMetric` : brancher Odoo ou SAP demain
 *  n'obligera à écrire qu'un adaptateur frère, sans toucher une seule vue.
 */
import type { DataState } from "@/components/ui/kit";
import { assertGoverned, type KBreakdownItem, type KMetric, type DataLevel } from "@/lib/kmetric";
import type { DecisionInsight } from "@/components/ui/insight";
import type { KSeriesPoint } from "@/lib/kmetric";
import type { ShieldHrQuery, ShieldKpi, ShieldSeriesQuery } from "@/lib/shieldHr";

const SOURCE = "kaydan_shield";
const SOURCE_LABEL = "Kaydan Shield";

/** Sévérité déduite d'une mesure RH, uniquement sur des seuils explicites.
 *  Aucun autre KPI n'en reçoit : inventer une gravité serait aussi faux
 *  qu'inventer une valeur. */
function severityOf(kpi: ShieldKpi): KMetric["severity"] {
  if (kpi.key !== "taux_presence" || kpi.value === null) return undefined;
  if (kpi.value < 70) return "critical";
  if (kpi.value < 85) return "warning";
  return "success";
}

export function shieldKpisToMetrics(query: ShieldHrQuery | undefined): KMetric[] {
  if (!query) return [];
  const { payload, stale, cachedAt } = query;
  const updatedAt = (stale ? cachedAt : payload.updated_at) ?? undefined;

  return payload.kpis.map((kpi) => {
    // Une valeur issue du cache reste réelle, mais n'est plus « connected ».
    const status: DataState = stale && kpi.status === "connected" ? "stale" : kpi.status;
    const metric: KMetric = {
      id: `shield.${kpi.key}`,
      title: kpi.title,
      value: kpi.value,
      unit: kpi.unit || undefined,
      period: kpi.key.startsWith("taux") || ["presents", "absents", "retards"].includes(kpi.key)
        ? "aujourd'hui"
        : undefined,
      status,
      severity: severityOf(kpi),
      source: SOURCE,
      sourceLabel: payload.source || SOURCE_LABEL,
      updatedAt,
      stale,
      // Le backend qualifie déjà chaque KPI ; on ne redécide pas ici.
      level: (kpi.level ?? "measured") as DataLevel,
      formula: kpi.formula || undefined,
      sourceField: kpi.source_field || undefined,
      drilldownUrl: "/dashboard/capital-humain/presence",
    };
    assertGoverned(metric);
    return metric;
  });
}

/** Répartition par site : présents par site, mesurés via `/attendance/days/?site=`.
 *  Les sites dont la mesure a échoué sont conservés mais sans valeur — les retirer
 *  laisserait croire qu'ils n'existent pas. */
export function shieldPresenceBreakdown(query: ShieldHrQuery | undefined): KBreakdownItem[] {
  const rows = query?.payload.by_site?.sites ?? [];
  return rows.map((row) => ({
    key: String(row.site.id ?? row.site.code),
    label: row.site.name,
    value: row.present,
    status: row.status,
    drilldownUrl: "/dashboard/capital-humain/presence",
  }));
}

/** Effectif ouvriers par site — la seule ventilation d'effectif réellement
 *  dérivable : l'API employés de Shield n'accepte pas de filtre par site. */
export function shieldWorkersBreakdown(query: ShieldHrQuery | undefined): KBreakdownItem[] {
  const rows = query?.payload.by_site?.sites ?? [];
  return rows.map((row) => ({
    key: String(row.site.id ?? row.site.code),
    label: row.site.name,
    value: row.workers,
    status: row.status,
  }));
}

/** Taux de présence par site, pour repérer les sites en tension. */
export function shieldAttendanceRateBreakdown(query: ShieldHrQuery | undefined): KBreakdownItem[] {
  const rows = query?.payload.by_site?.sites ?? [];
  return rows.map((row) => ({
    key: String(row.site.id ?? row.site.code),
    label: row.site.name,
    value: row.attendance_rate,
    status: row.status,
  }));
}

/** État consolidé de la répartition par site, tel que renvoyé par le backend. */
export function shieldBreakdownStatus(query: ShieldHrQuery | undefined): DataState {
  return (query?.payload.by_site?.status ?? "disconnected") as DataState;
}

/** Constats du backend → cartes d'aide à la décision.
 *  Aucun constat n'est fabriqué ici : on met en forme ce que le backend a
 *  déterminé à partir de seuils explicites appliqués à des mesures réelles. */
export function shieldInsights(query: ShieldHrQuery | undefined): DecisionInsight[] {
  const raw = query?.payload.insights ?? [];
  return raw.map((insight) => ({
    id: insight.id,
    title: insight.title,
    finding: insight.finding,
    impact: insight.impact,
    severity: insight.severity,
    sourceLabel: `${insight.source} · ${insight.period}`,
    confidence: insight.confidence ?? null,
    level: insight.level,
    formula: insight.formula,
    action: insight.action,
    detectedAt: query?.payload.updated_at,
  }));
}

/** Métriques génériques (sécurité, overview) : même contrat, autre jeu de KPI. */
export function shieldPayloadToMetrics(
  query: ShieldHrQuery | undefined,
  idPrefix: string,
  drilldownUrl?: string,
): KMetric[] {
  if (!query) return [];
  const { payload, stale, cachedAt } = query;
  const updatedAt = (stale ? cachedAt : payload.updated_at) ?? undefined;
  return payload.kpis.map((kpi) => {
    const status: DataState = stale && kpi.status === "connected" ? "stale" : kpi.status;
    const metric: KMetric = {
      id: `${idPrefix}.${kpi.key}`,
      title: kpi.title,
      value: kpi.value,
      unit: kpi.unit || undefined,
      status,
      source: SOURCE,
      sourceLabel: payload.source || SOURCE_LABEL,
      updatedAt,
      stale,
      level: (kpi.level ?? "measured") as DataLevel,
      formula: kpi.formula || undefined,
      sourceField: kpi.source_field || undefined,
      drilldownUrl,
    };
    assertGoverned(metric);
    return metric;
  });
}

/** Série de présence → points du TrendChart existant.
 *  Un jour non mesuré part avec `value: null` : le graphe laisse alors un TROU,
 *  au lieu de relier deux points comme si la journée avait été observée. */
export function shieldSeriesPoints(query: ShieldSeriesQuery | undefined): KSeriesPoint[] {
  const points = query?.payload.points ?? [];
  return points.map((p) => ({
    // Étiquette courte : la date complète encombrerait l'axe sur 30 points.
    label: p.date.slice(5),
    value: p.status === "measured" ? p.taux_presence : null,
  }));
}

/** Effectifs présents par jour, pour lire les volumes plutôt que le taux. */
export function shieldSeriesHeadcount(query: ShieldSeriesQuery | undefined): KSeriesPoint[] {
  const points = query?.payload.points ?? [];
  return points.map((p) => ({
    label: p.date.slice(5),
    value: p.status === "measured" ? p.present : null,
    compare: p.status === "measured" ? p.absent : null,
  }));
}

/** Répartition employés / ouvriers parmi les présents du jour. */
export function shieldPresenceByKind(query: ShieldHrQuery | undefined): KBreakdownItem[] {
  const byKind = query?.payload.by_kind;
  if (!byKind) return [];
  return [
    { key: "employees", label: "Employés", value: byKind.employees, status: byKind.status },
    { key: "workers", label: "Ouvriers", value: byKind.workers, status: byKind.status },
  ];
}

/** Constats portés par la série (baisse inhabituelle), au même format que les autres. */
export function shieldSeriesInsights(query: ShieldSeriesQuery | undefined): DecisionInsight[] {
  const raw = query?.payload.insights ?? [];
  return raw.map((insight) => ({
    id: insight.id,
    title: insight.title,
    finding: insight.finding,
    impact: insight.impact,
    severity: insight.severity,
    sourceLabel: `${insight.source} · ${insight.period}`,
    confidence: insight.confidence ?? null,
    level: insight.level,
    formula: insight.formula,
    action: insight.action,
    detectedAt: query?.payload.updated_at,
  }));
}
