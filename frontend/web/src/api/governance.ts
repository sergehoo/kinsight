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

/** Données d'un module, sous TOUS les filtres du cockpit.
 *
 *  `filtres` est la chaîne produite par `parametresFiltres` : période, filiale,
 *  site, type, département. La clé de cache la contient entière — deux filtres
 *  différents ne peuvent pas partager une réponse. */
export function useModuleData(key: string | undefined, filtres: string) {
  return useQuery<ModuleDataResponse>({
    queryKey: ["module-data", key, filtres],
    enabled: Boolean(key) && !USE_MOCK,
    queryFn: () => apiGet<ModuleDataResponse>(`/governance/module/${key}/?${filtres}`),
  });
}

/** Options RÉELLES des filtres RH (sites, types, départements mesurés). */
export interface HrDimensions {
  site: { code: string; libelle: string }[];
  type: { code: string; libelle: string }[];
  departement: { code: string; libelle: string }[];
  restriction?: string;
}

export function useHrDimensions(enabled = true) {
  return useQuery<HrDimensions>({
    queryKey: ["hr-dimensions"],
    enabled: enabled && !USE_MOCK,
    staleTime: 10 * 60_000,
    queryFn: () => apiGet<HrDimensions>("/governance/hr/dimensions/"),
  });
}

/** Une métrique RH sur la période filtrée (`/governance/hr/history/`). */
export interface HrHistory {
  metric_id: string;
  label: string;
  definition: string;
  unit: string;
  format: string;
  source: string;
  regle: string;
  status: string;
  reason?: string;
  periode?: { debut: string; fin: string; libelle: string; jusqu_a: string };
  valeur?: { value: number | null; status: string; couverture: { jours: number; jours_mesures: number } };
  points: { date: string; value: number | null; status: string }[];
  comparaisons?: {
    precedente?: { value: number | null; ecart: number | null; ecart_pct: number | null; unite_ecart: "pts" | "abs" | null; debut?: string; fin?: string };
    n_1?: { value: number | null; ecart: number | null; ecart_pct: number | null; unite_ecart: "pts" | "abs" | null; debut?: string; fin?: string };
  };
  ventilation?: { code: string; libelle: string; value: number | null; couverture: { jours: number; jours_mesures: number } }[] | null;
  aujourd_hui?: { value: number | null; status: string; reason?: string | null; date: string } | null;
  historique_depuis?: string | null;
}

/** Historique d'une métrique sous les filtres du cockpit. `extra` ajoute des
 *  paramètres propres à l'appel (ventilation par site, par type…). Lecture en
 *  base seulement : aucun appel Shield ni Odoo n'est déclenché. */
export function useHrHistory(metricId: string, filtres: string, extra = "", enabled = true) {
  const query = `metric=${encodeURIComponent(metricId)}&${filtres}${extra ? `&${extra}` : ""}`;
  return useQuery<HrHistory>({
    queryKey: ["hr-history", query],
    enabled: enabled && !USE_MOCK,
    staleTime: 5 * 60_000,
    queryFn: () => apiGet<HrHistory>(`/governance/hr/history/?${query}`),
  });
}
