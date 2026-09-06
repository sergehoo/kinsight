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
export interface ShieldSite {
  id: number | null;
  code: string;
  name: string;
  type: string;
  status: string;
  company: string;
  present_count: number | null;
  presence_status: DataState;
}

export interface ShieldHrResponse {
  status: DataState;
  source: string;
  detail?: string;
  /** Horodatage ISO de la normalisation côté backend (fraîcheur affichée). */
  updated_at?: string;
  kpis: ShieldKpi[];
  /** Répartition par site : sites réels, présence non exposée par la source. */
  by_site?: { status: DataState; detail?: string; sites: ShieldSite[] };
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
