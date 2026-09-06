/** Adaptateur Kaydan Shield → contrat KMetric.
 *
 *  C'est le SEUL module du frontend qui connaît la forme d'une réponse Shield.
 *  Tout composant en aval ne voit que des `KMetric` : brancher Odoo ou SAP demain
 *  n'obligera à écrire qu'un adaptateur frère, sans toucher une seule vue.
 */
import type { DataState } from "@/components/ui/kit";
import { assertGoverned, type KBreakdownItem, type KMetric, type DataLevel } from "@/lib/kmetric";
import type { ShieldHrQuery, ShieldKpi } from "@/lib/shieldHr";

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

/** Répartition par site. Shield expose les sites réels mais AUCUN compteur de
 *  présence par site : chaque entrée reste donc sans valeur et signalée comme
 *  non connectée, plutôt que remplie d'un zéro trompeur. */
export function shieldSitesToBreakdown(query: ShieldHrQuery | undefined): KBreakdownItem[] {
  const sites = query?.payload.by_site?.sites ?? [];
  return sites.map((site) => ({
    key: String(site.id ?? site.code),
    label: site.name,
    value: site.present_count,
    status: (site.presence_status ?? "disconnected") as DataState,
  }));
}

/** État consolidé de la répartition par site, tel que renvoyé par le backend. */
export function shieldBreakdownStatus(query: ShieldHrQuery | undefined): DataState {
  return (query?.payload.by_site?.status ?? "disconnected") as DataState;
}
