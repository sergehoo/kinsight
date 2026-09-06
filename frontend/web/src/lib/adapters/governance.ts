/** Adaptateur EDW / governance → contrat KMetric.
 *
 *  Second adaptateur, frère de `shield.ts` : il isole la forme des réponses
 *  `governance/*` pour que les vues n'aient jamais à la connaître.
 *
 *  Il ne publie QUE ce que le mart sert réellement aujourd'hui — la masse
 *  salariale, les entrées/sorties et leur ventilation par filiale. Tout le reste
 *  du cockpit Finance/Immobilier/Opérations reste déclaré et non alimenté : le
 *  mart correspondant n'existe pas, et le déclarer « connecté » serait mentir.
 */
import { assertGoverned, type KBreakdownItem, type KMetric } from "@/lib/kmetric";
import type { HrKpiSummary } from "@/types/governance";

const SOURCE = "edw";
const SOURCE_LABEL = "Mart EDW";

/** Ventilation de la masse salariale par filiale : la seule répartition
 *  réellement servie par le backend à ce jour. */
export function payrollBreakdown(summary: HrKpiSummary | undefined): KBreakdownItem[] {
  const raw = summary?.payroll_by_subsidiary;
  if (!raw) return [];
  return Object.entries(raw).map(([code, value]) => ({
    key: code,
    label: code,
    value: typeof value === "number" ? value : null,
    status: typeof value === "number" ? "connected" : "disconnected",
  }));
}

/** Métriques RH issues du mart. Les clés du contrat reprennent celles du
 *  catalogue backend (`hr.*`) pour rester alignées avec sa définition. */
export function hrMartMetrics(summary: HrKpiSummary | undefined, period?: string): KMetric[] {
  if (!summary?.metrics) return [];
  // Le backend neutralise lui-même les agrégats non adossés à des lignes réelles
  // et le dit via `available` : on ne redevine pas l'état à partir de la valeur.
  const unavailable = summary.available === false;
  const build = (id: string, title: string, key: keyof HrKpiSummary["metrics"], unit?: string): KMetric => {
    const raw = summary.metrics[key];
    const value = unavailable || typeof raw?.value !== "number" ? null : raw.value;
    const metric: KMetric = {
      id,
      title,
      value,
      unit: unit ?? raw?.unit ?? undefined,
      period,
      // Trois cas distincts : mart injoignable (error), mart sans ligne à publier
      // (disconnected), mesure absente d'une réponse par ailleurs valide (partial).
      status:
        summary.source_state === "error"
          ? "error"
          : unavailable
            ? "disconnected"
            : value === null
              ? "partial"
              : "connected",
      source: SOURCE,
      sourceLabel: SOURCE_LABEL,
      level: "measured",
      sourceField: String(key),
      drilldownUrl: "/dashboard/capital-humain/masse-salariale",
    };
    assertGoverned(metric);
    return metric;
  };

  return [
    build("hr.masse_salariale", "Masse salariale", "hr.payroll_mass", "XOF"),
    build("hr.entrees", "Entrées", "hr.entries"),
    build("hr.sorties", "Sorties", "hr.exits"),
    build("hr.variation_effectif", "Variation d'effectif", "hr.net_headcount_change"),
  ];
}
