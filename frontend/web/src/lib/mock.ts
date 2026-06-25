/** Données d'exemple (démo sans backend). Mêmes formes que l'API réelle.
 *  Les chiffres reprennent le jeu de test vérifié côté backend (Q1 2026). */

import type { CatalogResponse, DashboardSummary, GovernanceOverviewResponse, HrKpiSummary } from "@/types/governance";

const QUARTER_BOUNDS: Record<number, [string, string]> = {
  1: ["01-01", "04-01"],
  2: ["04-01", "07-01"],
  3: ["07-01", "10-01"],
  4: ["10-01", "12-31"],
};

export function mockHrKpi(year: number, quarter: number): HrKpiSummary {
  const [a, b] = QUARTER_BOUNDS[quarter] ?? QUARTER_BOUNDS[1];
  // Léger effet de saison pour rendre les filtres vivants.
  const factor = 1 + (quarter - 1) * 0.04;
  const r = (n: number) => Math.round(n * factor);
  return {
    period: { start: `${year}-${a}`, end: `${quarter === 4 ? year : year}-${b}` },
    scope: "GROUP",
    metrics: {
      "hr.payroll_mass": { value: r(3_110_000), unit: "XOF" },
      "hr.entries": { value: 1 + (quarter % 3), unit: "personnes" },
      "hr.exits": { value: 2, unit: "personnes" },
      "hr.net_headcount_change": { value: 1 + (quarter % 3) - 2, unit: "personnes" },
    },
    payroll_by_subsidiary: {
      KRE: r(2_150_000),
      KSH: r(960_000),
      MYK: r(740_000),
    },
  };
}

function unavailableDashboard(
  key: DashboardSummary["key"],
  title: string,
  source: string,
  chartTitle: string,
  periodLabel: string,
): DashboardSummary {
  return {
    key,
    title,
    subtitle: `Dashboard branche au backend. Donnees en attente de materialisation dans ${source}.`,
    status: `Source backend attendue : ${source}`,
    available: false,
    source,
    imageHint: key === "realEstate" ? "real_estate" : key,
    overlayTitle: "Mart a connecter",
    overlaySubtitle: source,
    overlayValue: "--",
    overlayBadges: ["EDW", "MART"],
    periodLabel,
    chartTitle,
    chartValue: "--",
    chartDelta: "Aucune donnee servie",
    chartDeltaUp: false,
    chartUnit: key === "finance" ? "XOF" : "%",
    chartData: {},
    chartEmptyLabel: `Aucune donnee disponible dans ${source}`,
    cards: [
      { label: "Source", context: "Backend", value: "--", delta: "mart absent", up: false, gauge: 8, color: "#416FF4", highlighted: true },
      { label: "Qualite", context: "Controle", value: "--", delta: "a connecter", up: false, gauge: 8, color: "#D92B55" },
      { label: "Audit", context: "RBAC", value: "OK", delta: "read", up: true, gauge: 60, color: "#42BFA0" },
    ],
    controlTitle: "Controle donnees",
    controlSubtitle: `Materialiser ${source} pour activer ce dashboard`,
    alertTop: [["Source", source], ["Etat", "Absent"], ["API", "OK"], ["RBAC", "OK"], ["Mode", "read"]],
    alertBottom: [["Action", "dbt"], ["Grain", "a definir"], ["Scope", "filiale"], ["Audit", "OK"], ["Prod", "pret"]],
  };
}

export function mockGovernanceOverview(year: number, quarter: number): GovernanceOverviewResponse {
  const hr = mockHrKpi(year, quarter);
  const payroll = hr.payroll_by_subsidiary;
  const total = Object.values(payroll).reduce((sum, value) => sum + value, 0);
  const sortedPayroll = Object.entries(payroll).sort((a, b) => b[1] - a[1]);
  const [topCode, topValue] = sortedPayroll[0] ?? ["--", 0];
  const topShare = total ? Math.round((topValue / total) * 100) : 0;
  const entries = hr.metrics["hr.entries"].value;
  const exits = hr.metrics["hr.exits"].value;
  const net = hr.metrics["hr.net_headcount_change"].value;

  return {
    period: hr.period,
    scope: hr.scope,
    dashboards: {
      realEstate: unavailableDashboard("realEstate", "Pilotage Real Estate", "mart.real_estate_kpi", "Avancement par programme", "Real Estate"),
      finance: unavailableDashboard("finance", "Pilotage Finance", "mart.finance_kpi", "Repartition des charges", "Finance"),
      hr: {
        key: "hr",
        title: "Pilotage RH",
        subtitle: "Synthese RH issue du backend : masse salariale, entrees, sorties et repartition par filiale.",
        status: "Donnees backend chargees",
        available: true,
        source: "mart.hr_kpi",
        imageHint: "hr",
        overlayTitle: "Perimetre Groupe",
        overlaySubtitle: `${hr.period.start} -> ${hr.period.end}`,
        overlayValue: String(Object.keys(payroll).length),
        overlayBadges: Object.keys(payroll),
        periodLabel: `T${quarter} ${year}`,
        chartTitle: "Masse salariale par filiale",
        chartValue: `${(total / 1_000_000).toFixed(1).replace(".0", "")}M XOF`,
        chartDelta: "mart.hr_kpi",
        chartDeltaUp: true,
        chartUnit: "XOF",
        chartData: payroll,
        chartEmptyLabel: "Aucune masse salariale sur la periode",
        cards: [
          { label: "Masse salariale", context: "Cumul de la periode", value: `${(total / 1_000_000).toFixed(1).replace(".0", "")}M XOF`, delta: `${topCode} ${topShare}%`, up: true, gauge: Math.max(8, topShare), color: "#416FF4", highlighted: true },
          { label: "Entrees RH", context: "Embauches periode", value: String(entries), delta: `${Math.abs(net)} net`, up: net >= 0, gauge: 45, color: "#42BFA0" },
          { label: "Sorties RH", context: "Departs periode", value: String(exits), delta: `${exits} departs`, up: false, gauge: 55, color: "#D92B55" },
        ],
        controlTitle: "Controle donnees RH",
        controlSubtitle: "Source backend : mart.hr_kpi",
        alertTop: [["Entrees", String(entries)], ["Sorties", String(exits)], ["Net", `${net >= 0 ? "+" : ""}${net}`], ["Audit", "OK"], ["RBAC", "OK"]],
        alertBottom: [["Mart", "hr_kpi"], ["Grain", "mois"], ["Scope", "filiale"], ["Unite", "XOF"], ["Mode", "read"]],
      },
    },
  };
}

export const mockCatalog: CatalogResponse = {
  count: 6,
  metrics: [
    {
      key: "hr.headcount",
      domain: "hr",
      label: "Effectif",
      unit: "personnes",
      grain: "filiale × département × jour",
      direction: "neutral",
      description: "Nombre de salariés en poste à une date.",
      mart: "mart.hr_kpi",
      dimensions: ["subsidiary", "department", "period"],
    },
    {
      key: "hr.turnover_rate",
      domain: "hr",
      label: "Taux de turnover",
      unit: "ratio",
      grain: "filiale × mois",
      direction: "lower_is_better",
      description: "Départs rapportés à l'effectif moyen.",
      mart: "mart.hr_kpi",
      dimensions: ["subsidiary", "period"],
    },
    {
      key: "hr.payroll_mass",
      domain: "hr",
      label: "Masse salariale (brut)",
      unit: "XOF",
      grain: "filiale × département × mois",
      direction: "neutral",
      description: "Somme des salaires bruts sur la période.",
      mart: "mart.hr_kpi",
      dimensions: ["subsidiary", "department", "period"],
    },
  ],
};
