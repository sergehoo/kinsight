/** KPIs RH normalisés depuis Kaydan Shield (via le backend K-Insight, jamais Shield en direct). */
import { useQuery } from "@tanstack/react-query";

import { apiGetMeta } from "@/lib/api";
import type { DataState } from "@/components/ui/kit";

export type ShieldKpiKey =
  | "effectif_total" | "employes" | "ouvriers" | "presents"
  | "absents" | "retards" | "taux_presence"
  // Deux taux dérivés des mêmes compteurs, sans appel Shield supplémentaire.
  // Le libellé du backend dit « du jour » : le dépôt porte une seconde
  // définition de l'absentéisme, mensuelle et rapportée aux jours travaillés
  // théoriques, qui ne mesure pas la même chose.
  | "taux_absence_jour" | "taux_ponctualite"
  | "sites";

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

/** Une ligne de répartition par site, telle que normalisée par le backend.
 *
 *  `employees` reste null : l'endpoint employés de Shield n'accepte AUCUN filtre
 *  `site` (vérifié dans `shield_endpoints.py`), et le répartir au prorata
 *  donnerait un chiffre crédible et faux.
 *
 *  Présence, absences et retards par site, EUX, sont bien servis : ils sont
 *  dérivés de la collecte de période, sans appel supplémentaire. Un commentaire
 *  précédent affirmait le contraire — « Shield n'expose aucun compteur de présence
 *  agrégé par site » — juste au-dessus des champs que le backend remplit.
 */
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
  /** Répartition par site, montée sur les relations réelles de l'API.
   *
   *  `restriction` est renseigné quand le serveur a RETIRÉ les lignes faute de
   *  périmètre Groupe : la source ne rattache pas ses sites aux filiales, donc
   *  filtrer serait inventer et montrer serait fuir. Le champ manquait à ce type,
   *  si bien que l'écran ne pouvait pas expliquer le vide et laissait croire à
   *  une source muette. */
  by_site?: {
    status: DataState;
    detail?: string;
    date?: string;
    truncated?: boolean;
    restriction?: string;
    sites: ShieldSiteRow[];
  };
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
  /** Bornes RÉELLEMENT employées par le serveur, et non celles demandées.
   *  Sans elles, l'écran ne peut pas dire si le filtre de période a agi — ni
   *  signaler qu'une période a été ramenée à une borne. */
  date_from?: string;
  date_to?: string;
  points: ShieldSeriesPoint[];
  measured_days?: number;
  insights?: ShieldInsight[];
}

export interface ShieldSeriesQuery {
  payload: ShieldSeriesResponse;
  stale: boolean;
  cachedAt?: string;
}

/** Fenêtres glissantes proposées.
 *
 *  LE COMMENTAIRE PRÉCÉDENT ÉTAIT FAUX : il refusait 90 jours au motif de « 270
 *  appels, un par jour ». La collecte lit la période entière en 3 jeux paginés,
 *  donc la durée ne change pas le nombre d'appels. La vraie borne est le volume —
 *  2 400 lignes par indicateur, soit ~3 jours à 722 personnes/jour. Ouvrir 90
 *  jours promettrait un trimestre pour livrer trois jours de mesures. Le détail
 *  chiffré est dans `backend/apps/integrations/shield_rules.py`.
 */
export const SERIES_WINDOWS = [7, 30] as const;
export type SeriesWindow = (typeof SERIES_WINDOWS)[number];

/** Une période explicite, telle que produite par le sélecteur trimestre + année. */
export interface Periode {
  dateFrom: string;
  dateTo: string;
}

/** Série de présence, sur une fenêtre glissante OU une période datée.
 *
 *  `periode` prend le pas sur `days` : c'est le filtre explicite de l'écran. La
 *  clé de cache porte les deux, sinon un changement de trimestre resservirait la
 *  réponse du précédent.
 */
export function useShieldAttendanceSeries(days: SeriesWindow = 30, periode?: Periode) {
  const requete = periode
    ? `date_from=${periode.dateFrom}&date_to=${periode.dateTo}`
    : `days=${days}`;
  return useQuery<ShieldSeriesQuery>({
    queryKey: ["shield", "attendance-series", periode ? [periode.dateFrom, periode.dateTo] : days],
    queryFn: async () => {
      const { data, stale, cachedAt } = await apiGetMeta<ShieldSeriesResponse>(
        `/integrations/shield/attendance-series/?${requete}`,
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
