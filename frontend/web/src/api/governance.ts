import { useQuery } from "@tanstack/react-query";

import { apiGet, USE_MOCK } from "@/lib/api";
import { mockCatalog, mockGovernanceOverview, mockHrKpi } from "@/lib/mock";
import type { CatalogResponse, GovernanceOverviewResponse, HrKpiSummary } from "@/types/governance";

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
