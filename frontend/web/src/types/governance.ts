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
  /** false = aucune ligne réelle derrière ces agrégats (valeurs neutralisées à null). */
  available?: boolean;
  /** connected = le mart a répondu ; error = mart injoignable. */
  source_state?: "connected" | "error";
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

export interface HrScoreDimension {
  key: string;
  label: string;
  weight: number;
  score: number | null;
  /** Pourquoi la dimension n'est pas scorée (source absente, couverture…). */
  motif?: string | null;
  /** Règle de conversion appliquée, écrite en clair. */
  formule?: string;
  source?: string;
  entrees?: { taux_presence: number | null; taux_ponctualite: number | null; jours_mesures: number; jours: number } | null;
  sous_scores?: { presence: number; ponctualite: number } | null;
  /** Score de la même dimension sur la période précédente. */
  precedent?: number | null;
}
export interface HrScoreResponse {
  available: boolean;
  global: number | null;
  /** Pourquoi le global n'est pas publié (couverture insuffisante du poids). */
  motif_global?: string | null;
  couverture?: { poids_couvert: number; poids_total: number; dimensions_scorees: number; dimensions: number; seuil: number };
  source?: string;
  source_state?: string;
  by_subsidiary_motif?: string;
  dimensions: HrScoreDimension[];
  by_subsidiary: { code: string; score: number | null }[];
  trend: { month: string; score: number | null }[];
  period?: { start: string; end: string; label?: string };
  scope?: "GROUP" | string[];
}

/** Dimension d'un score de gouvernance de domaine (avec métadonnées de source). */
export interface GovernanceScoreDimension {
  key: string;
  label: string;
  weight: number;
  score: number | null;
  mart_source?: string;
  rationale?: string;
}
/** Réponse générique d'un Score de Gouvernance (HR ou domaine métier). */
export interface GovernanceScoreResponse {
  domain?: string;
  label?: string;
  available: boolean;
  global: number | null;
  dimensions: GovernanceScoreDimension[];
  by_subsidiary: { code: string; score: number | null }[];
  trend: { month: string; score: number | null }[];
  period?: { start: string; end: string };
  scope?: "GROUP" | string[];
}

/** Indice de Gouvernance Groupe consolidé (agrégation pondérée des domaines). */
export interface GroupScoreResponse {
  available: boolean;
  global: number | null;
  domains: { domain: string; label: string; weight: number; score: number | null }[];
  by_subsidiary: { code: string; score: number | null }[];
  trend: { month: string; score: number | null }[];
  period?: { start: string; end: string };
  scope?: "GROUP" | string[];
}

/** Centre d'alertes (seuils sur scores réels, gouverné). */
export interface GovernanceAlert {
  severity: "info" | "warning" | "critical";
  label: string;
  scope: string;
  source: string;
  kind: string;
  value: number;
  threshold: number;
}
export interface AlertsResponse {
  available: boolean;
  count: number;
  counts: { info: number; warning: number; critical: number };
  alerts: GovernanceAlert[];
  period?: { start: string; end: string };
  scope?: "GROUP" | string[];
}

/** Réponse de l'IA ancrée (sourcée sur le catalogue + mart, jamais inventée). */
export interface AiAnswer {
  grounded: boolean;
  answer: string;
  value: number | null;
  source: string | null;
  metric: {
    key: string;
    label: string;
    domain: string;
    unit: string;
    direction: string;
    mart: string;
    description: string;
  } | null;
}

/** Une carte résolue par le registre canonique RH : valeur RÉELLE ou motif.
 *
 *  `value` est `null` quand aucune source ne la sert, hors droits ou hors
 *  périmètre — jamais 0. `reason` dit lequel, et s'affiche tel quel. `instant`
 *  marque une mesure « aujourd'hui », live, qui ne répond pas au filtre de période. */
export interface ModuleDataValue {
  value: number | null;
  unit: string;
  format: string;
  metric_id?: string;
  label?: string;
  definition?: string;
  instant?: boolean;
  source?: "shield" | "odoo" | "aucune";
  source_label?: string;
  status?: string;
  reason?: string;
  as_of?: string | null;
  /** Période réellement lue, et sa couverture en jours mesurés. */
  periode?: { libelle: string; debut: string; fin: string; couverture?: { jours: number; jours_mesures: number } };
  /** Écart à la période précédente (points pour un taux). */
  precedente?: { value: number | null; ecart: number | null; ecart_pct: number | null; unite_ecart: "pts" | "abs" | null };
  /** Mesure live du jour, sous les mêmes filtres quand la source le permet. */
  aujourd_hui?: { value: number | null; status?: string; reason?: string | null; as_of?: string | null };
}
export interface ModuleDataSeries { name: string; type: string; unit?: string; points: { label: string; value: number }[]; }
export interface ModuleDataResponse {
  key: string;
  available: boolean;
  source: string | null;
  /** Période réellement lue (bornes jusqu'à la veille) et son libellé. `null`
   *  quand la période demandée n'a pas encore commencé. */
  period?: { start: string; end: string; label?: string } | null;
  scope?: "GROUP" | string[];
  values: Record<string, ModuleDataValue>;
  series: ModuleDataSeries[];
}
