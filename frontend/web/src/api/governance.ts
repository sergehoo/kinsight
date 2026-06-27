import { useMutation, useQuery } from "@tanstack/react-query";

import { apiDownload, apiGet, apiPost, USE_MOCK } from "@/lib/api";
import { mockCatalog, mockGovernanceOverview, mockHrKpi } from "@/lib/mock";
import type { AiAnswer, AlertsResponse, CatalogResponse, GovernanceOverviewResponse, GovernanceScoreResponse, GroupScoreResponse, HrKpiSummary , HrScoreResponse, ModuleDataResponse } from "@/types/governance";

/** Centre d'alertes (seuils sur scores réels). Gouverné : aucune donnée → aucune alerte. */
export function useAlerts(year: number, quarter: number, subsidiary = "all") {
  const sub = subsidiary && subsidiary !== "all" ? `&subsidiary=${subsidiary}` : "";
  return useQuery<AlertsResponse>({
    queryKey: ["alerts", year, quarter, subsidiary],
    enabled: !USE_MOCK,
    queryFn: () => apiGet<AlertsResponse>(`/governance/alerts/?year=${year}&quarter=${quarter}${sub}`),
  });
}

/** IA ancrée : pose une question, renvoie une réponse sourcée (ou un refus). Jamais inventé. */
export function useAiQuery() {
  return useMutation<AiAnswer, Error, string>({
    mutationFn: (question: string) => apiPost<AiAnswer>("/governance/ai/query/", { question }),
  });
}

/** Télécharge l'export du tableau de bord Gouvernance Groupe (xlsx | pdf). */
export function downloadGroupExport(ext: "xlsx" | "pdf", year: number, quarter: number, subsidiary = "all") {
  const sub = subsidiary && subsidiary !== "all" ? `&subsidiary=${subsidiary}` : "";
  return apiDownload(
    `/governance/export/groupe.${ext}?year=${year}&quarter=${quarter}${sub}`,
    `k-insight-gouvernance-${year}-T${quarter}.${ext}`,
  );
}

/** Domaines dotés d'un Score de Gouvernance (capital-humain via /hr/score/, les autres via /score/<domaine>/). */
export const SCORE_DOMAINS = [
  "capital-humain",
  "immobilier",
  "finance",
  "operations",
  "commercial-clients",
  "risques-conformite",
] as const;

export function useHrKpi(year: number, quarter: number) {
  return useQuery<HrKpiSummary>({
    queryKey: ["hr-kpi", year, quarter],
    queryFn: () =>
      USE_MOCK
        ? Promise.resolve(mockHrKpi(year, quarter))
        : apiGet<HrKpiSummary>(`/governance/hr/kpi/?year=${year}&quarter=${quarter}`),
  });
}

export function useCatalog(domain?: string) {
  return useQuery<CatalogResponse>({
    queryKey: ["catalog", domain ?? "all"],
    queryFn: () =>
      USE_MOCK
        ? Promise.resolve(mockCatalog)
        : apiGet<CatalogResponse>(`/governance/catalog/${domain ? `?domain=${domain}` : ""}`),
  });
}

export function useGovernanceOverview(year: number, quarter: number) {
  return useQuery<GovernanceOverviewResponse>({
    queryKey: ["governance-overview", year, quarter],
    queryFn: () =>
      USE_MOCK
        ? Promise.resolve(mockGovernanceOverview(year, quarter))
        : apiGet<GovernanceOverviewResponse>(`/governance/overview/?year=${year}&quarter=${quarter}`),
  });
}

/** Human Capital Score (global, dimensions pondérées, par filiale, tendance 12 mois).
 *  Gouverné : si le mart n'est pas branché ou ne renvoie rien, `available=false` → N/D côté UI.
 *  Pas de variante mock : on n'invente jamais de score. */
export function useHrScore(year: number, quarter: number, subsidiary = "all") {
  const sub = subsidiary && subsidiary !== "all" ? `&subsidiary=${subsidiary}` : "";
  return useQuery<HrScoreResponse>({
    queryKey: ["hr-score", year, quarter, subsidiary],
    enabled: !USE_MOCK,
    queryFn: () => apiGet<HrScoreResponse>(`/governance/hr/score/?year=${year}&quarter=${quarter}${sub}`),
  });
}

/** Score de Gouvernance d'un domaine. `capital-humain` lit /hr/score/, les autres /score/<domaine>/.
 *  Même forme de réponse. Gouverné : `available=false` → N/D côté UI. Pas de mock (jamais de score inventé). */
export function useDomainScore(domainId: string | undefined, year: number, quarter: number, subsidiary = "all") {
  const sub = subsidiary && subsidiary !== "all" ? `&subsidiary=${subsidiary}` : "";
  const enabled = Boolean(domainId) && !USE_MOCK && SCORE_DOMAINS.includes(domainId as (typeof SCORE_DOMAINS)[number]);
  const path =
    domainId === "capital-humain"
      ? `/governance/hr/score/?year=${year}&quarter=${quarter}${sub}`
      : `/governance/score/${domainId}/?year=${year}&quarter=${quarter}${sub}`;
  return useQuery<GovernanceScoreResponse>({
    queryKey: ["domain-score", domainId, year, quarter, subsidiary],
    enabled,
    queryFn: () => apiGet<GovernanceScoreResponse>(path),
  });
}

/** Indice de Gouvernance Groupe consolidé (Overview). Gouverné : `available=false` → N/D. */
export function useGroupScore(year: number, quarter: number, subsidiary = "all") {
  const sub = subsidiary && subsidiary !== "all" ? `&subsidiary=${subsidiary}` : "";
  return useQuery<GroupScoreResponse>({
    queryKey: ["group-score", year, quarter, subsidiary],
    enabled: !USE_MOCK,
    queryFn: () => apiGet<GroupScoreResponse>(`/governance/score-group/?year=${year}&quarter=${quarter}${sub}`),
  });
}

export function useModuleData(key: string | undefined, year: number, quarter: number, subsidiary = "all") {
  const sub = subsidiary && subsidiary !== "all" ? `&subsidiary=${subsidiary}` : "";
  return useQuery<ModuleDataResponse>({
    queryKey: ["module-data", key, year, quarter, subsidiary],
    enabled: Boolean(key) && !USE_MOCK,
    queryFn: () => apiGet<ModuleDataResponse>(`/governance/module/${key}/?year=${year}&quarter=${quarter}${sub}`),
  });
}
