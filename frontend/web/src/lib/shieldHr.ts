/** KPIs RH normalisés depuis Kaydan Shield (via le backend K-Insight, jamais Shield en direct). */
import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
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
}

export interface ShieldHrResponse {
  status: DataState;
  source: string;
  detail?: string;
  /** Horodatage ISO de la normalisation côté backend (fraîcheur affichée). */
  updated_at?: string;
  kpis: ShieldKpi[];
}

export function useShieldHrKpis() {
  return useQuery<ShieldHrResponse>({
    queryKey: ["shield", "hr-kpi"],
    queryFn: () => apiGet<ShieldHrResponse>("/integrations/shield/hr-kpi/"),
    staleTime: 60_000,
    // Le cockpit doit sembler vivant sans rechargement brutal.
    refetchInterval: 120_000,
    refetchOnWindowFocus: true,
    retry: false,
  });
}
