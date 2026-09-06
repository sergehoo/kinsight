/** KPIs RH normalisés depuis Kaydan Shield (via le backend K-Insight, jamais Shield en direct). */
import { useQuery } from "@tanstack/react-query";

import { apiGetMeta } from "@/lib/api";
import type { DataState } from "@/components/ui/kit";

export type ShieldKpiKey =
  | "effectif_total" | "employes" | "ouvriers" | "presents"
  | "absents" | "retards" | "taux_presence" | "sites";

export interface ShieldKpi {
  key: ShieldKpiKey;
  title: string;
  value: number | null;
  unit: string;
  /** connected | disconnected | error (le backend n'émet jamais `connecting`). */
  status: DataState;
  /** Niveau qualifié par le backend : mesuré tel quel, ou calculé par K-Insight. */
  level?: "measured" | "computed";
  /** Formule documentée — renseignée uniquement pour les KPI calculés. */
  formula?: string;
  /** Champ d'origine côté Shield — renseigné uniquement pour les mesures. */
  source_field?: string;
}

/** Un site réel de Shield. `present_count` reste null : Shield n'expose aucun
 *  compteur de présence agrégé par site (le seul endpoint par site est nominatif). */
/** Une ligne de répartition par site, telle que normalisée par le backend.
 *  `employees` reste null : Shield n'expose aucun filtre par site sur les employés. */
export interface ShieldSiteRow {
  site: { id: number | null; code: string; name: string; type: string; status: string; company: string };
  employees: number | null;
  employees_status: "unknown";
  employees_reason: string;
  workers: number | null;
  total: number | null;
  total_status: "unknown";
  present: number | null;
  absent: number | null;
  late: number | null;
  attendance_rate: number | null;
  drilldown_url?: string;
  alerts: number | null;
  status: DataState;
  updated_at: string;
}

/** Constat déterministe produit par le backend à partir de mesures réelles. */
export interface ShieldInsight {
  id: string;
  severity: "info" | "success" | "warning" | "critical" | "anomaly";
  title: string;
  finding: string;
  impact?: string;
  level: "measured" | "computed";
  formula?: string;
  source: string;
  period: string;
  confidence?: number;
  action?: { label: string; to: string };
}

export interface ShieldHrResponse {
  status: DataState;
  source: string;
  detail?: string;
  /** Horodatage ISO de la normalisation côté backend (fraîcheur affichée). */
  updated_at?: string;
  kpis: ShieldKpi[];
  /** Présence du jour ventilée employés / ouvriers (filtre `holder_kind`). */
  by_kind?: {
    status: DataState;
    date: string;
    employees: number | null;
    workers: number | null;
    total: number | null;
    employees_share: number | null;
    workers_share: number | null;
  };
  /** Répartition par site, montée sur les relations réelles de l'API. */
  by_site?: { status: DataState; detail?: string; date?: string; truncated?: boolean; sites: ShieldSiteRow[] };
  insights?: ShieldInsight[];
}

/** La charge utile accompagnée de son origine : réseau ou cache hors ligne. */
export interface ShieldHrQuery {
  payload: ShieldHrResponse;
  /** true = servie par le service worker faute de réseau → à afficher comme datée. */
  stale: boolean;
  cachedAt?: string;
}

export function useShieldHrKpis() {
  return useQuery<ShieldHrQuery>({
    queryKey: ["shield", "hr-kpi"],
    queryFn: async () => {
      const { data, stale, cachedAt } = await apiGetMeta<ShieldHrResponse>("/integrations/shield/hr-kpi/");
      return { payload: data, stale, cachedAt };
    },
    staleTime: 60_000,
    // Le cockpit doit sembler vivant sans rechargement brutal.
    refetchInterval: 120_000,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    retry: false,
  });
}

/** Indicateurs Sécurité & Conformité (cockpit Risques). */
export function useShieldSecurity() {
  return useQuery<ShieldHrQuery>({
    queryKey: ["shield", "security"],
    queryFn: async () => {
      const { data, stale, cachedAt } = await apiGetMeta<ShieldHrResponse>("/integrations/shield/security/");
      return { payload: data, stale, cachedAt };
    },
    staleTime: 60_000,
    refetchInterval: 120_000,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    retry: false,
  });
}

/** Agrégats Shield pour la vue Groupe. */
export function useShieldOverview() {
  return useQuery<ShieldHrQuery>({
    queryKey: ["shield", "overview"],
    queryFn: async () => {
      const { data, stale, cachedAt } = await apiGetMeta<ShieldHrResponse>("/integrations/shield/overview/");
      return { payload: data, stale, cachedAt };
    },
    staleTime: 60_000,
    refetchInterval: 120_000,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    retry: false,
  });
}

/** Un jour de la série de présence. `unknown` = mesure indisponible ce jour-là,
 *  ce qui n'est pas la même chose qu'une journée à zéro présent. */
export interface ShieldSeriesPoint {
  date: string;
  present: number | null;
  absent: number | null;
  late: number | null;
  taux_presence: number | null;
  status: "measured" | "unknown";
}

export interface ShieldSeriesResponse {
  status: DataState;
  source: string;
  detail?: string;
  updated_at?: string;
  days: number;
  points: ShieldSeriesPoint[];
  measured_days?: number;
  insights?: ShieldInsight[];
}

export interface ShieldSeriesQuery {
  payload: ShieldSeriesResponse;
  stale: boolean;
  cachedAt?: string;
}

/** Fenêtres réellement supportées : la série se construit par comptages
 *  journaliers, 90 jours demanderaient 270 appels à chaque rafraîchissement. */
export const SERIES_WINDOWS = [7, 30] as const;
export type SeriesWindow = (typeof SERIES_WINDOWS)[number];

export function useShieldAttendanceSeries(days: SeriesWindow = 30) {
  return useQuery<ShieldSeriesQuery>({
    queryKey: ["shield", "attendance-series", days],
    queryFn: async () => {
      const { data, stale, cachedAt } = await apiGetMeta<ShieldSeriesResponse>(
        `/integrations/shield/attendance-series/?days=${days}`,
      );
      return { payload: data, stale, cachedAt };
    },
    // Plus lente et plus coûteuse que les cartes : on la rafraîchit moins souvent.
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: true,
    retry: false,
  });
}
