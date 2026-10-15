/** Lectures Odoo RH côté écran — toujours via le backend, jamais Odoo en direct.
 *
 *  Le backend applique le périmètre : une filiale ne reçoit que ses sociétés
 *  DÉCLARÉES, ou rien (« aucune société rattachée ») ; il ne sert jamais le
 *  référentiel Groupe à un périmètre restreint. */
import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import type { DataState } from "@/components/ui/kit";

export interface OdooKpi {
  key: string;
  title: string;
  value: number | null;
  unit: string;
  status: DataState;
  metric_id?: string | null;
  detail?: string;
}

export interface OdooHrResponse {
  status: DataState;
  source: string;
  detail?: string;
  restriction?: string;
  updated_at?: string;
  kpis: OdooKpi[];
  by_department?: {
    status: DataState;
    detail?: string;
    unassigned?: number;
    rows: { department: string; headcount: number }[];
  };
}

export interface OdooHealth {
  status: DataState | "auth_required";
  source: string;
  detail?: string;
  version?: string;
  derniere_verification?: string | null;
  reconnexion_automatique?: boolean;
  latency_ms?: number;
}

export function useOdooHrKpis(enabled = true) {
  return useQuery<OdooHrResponse>({
    queryKey: ["odoo", "hr-kpi"],
    enabled,
    queryFn: () => apiGet<OdooHrResponse>("/integrations/odoo/hr-kpi/"),
    staleTime: 2 * 60_000,
    retry: false,
  });
}

/** Santé du connecteur Odoo, lisible par tout utilisateur authentifié. Remplace
 *  le « Connecteur non branché » écrit en dur, faux depuis que le transport existe. */
export function useOdooHealth() {
  return useQuery<OdooHealth>({
    queryKey: ["odoo", "health"],
    queryFn: () => apiGet<OdooHealth>("/integrations/odoo/health/"),
    staleTime: 5 * 60_000,
    retry: false,
  });
}
