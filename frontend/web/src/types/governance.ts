/** Types miroir de l'API governance (backend Django). */

export interface MetricValue {
  value: number;
  unit: string;
}

export type HrMetricKey =
  | "hr.payroll_mass"
  | "hr.entries"
  | "hr.exits"
  | "hr.net_headcount_change";

export interface HrKpiSummary {
  period: { start: string; end: string };
  scope: "GROUP" | string[];
  metrics: Record<HrMetricKey, MetricValue>;
  payroll_by_subsidiary: Record<string, number>;
}

export type DashboardKey = "realEstate" | "hr" | "finance";

export interface DashboardMetricCard {
  label: string;
  context: string;
  value: string;
  delta: string;
  up: boolean;
  gauge: number;
  color: string;
  highlighted?: boolean;
}

export interface DashboardSummary {
  key: DashboardKey;
  title: string;
  subtitle: string;
  status: string;
  available: boolean;
  source: string;
  imageHint: "real_estate" | "hr" | "finance";
  overlayTitle: string;
  overlaySubtitle: string;
  overlayValue: string;
  overlayBadges: string[];
  periodLabel: string;
  chartTitle: string;
  chartValue: string;
  chartDelta: string;
  chartDeltaUp: boolean;
  chartUnit: string;
  chartData: Record<string, number>;
  chartEmptyLabel: string;
  cards: DashboardMetricCard[];
  controlTitle: string;
  controlSubtitle: string;
  alertTop: Array<[string, string]>;
  alertBottom: Array<[string, string]>;
}

export interface GovernanceOverviewResponse {
  period: { start: string; end: string };
  scope: "GROUP" | string[];
  dashboards: Record<DashboardKey, DashboardSummary>;
}

export interface CatalogMetric {
  key: string;
  domain: string;
  label: string;
  unit: string;
  grain: string;
  direction: "higher_is_better" | "lower_is_better" | "neutral";
  description: string;
  mart: string;
  dimensions: string[];
}

export interface CatalogResponse {
  count: number;
  metrics: CatalogMetric[];
}
