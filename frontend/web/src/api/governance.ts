import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiDelete, apiDownload, apiGet, apiPatch, apiPost, apiPostDetail, apiPut, USE_MOCK } from "@/lib/api";
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
/** Rapport Capital Humain sous les filtres COURANTS (période, filiale, site,
 *  type, département) : le serveur y applique le périmètre de l'utilisateur. */
export function downloadHrReport(ext: "xlsx" | "pdf" | "pptx", filtres: string, libelle: string) {
  const nom = `k-insight-capital-humain-${libelle.replace(/[^\p{L}\p{N}]+/gu, "-").toLowerCase()}.${ext}`;
  return apiDownload(`/governance/hr/rapport.${ext}?${filtres}`, nom);
}

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
/** Score de gouvernance RH sous TOUS les filtres du cockpit (`parametresFiltres`). */
export function useHrScore(filtres: string) {
  return useQuery<HrScoreResponse>({
    queryKey: ["hr-score", filtres],
    enabled: !USE_MOCK,
    queryFn: () => apiGet<HrScoreResponse>(`/governance/hr/score/?${filtres}`),
  });
}

/** Score de Gouvernance d'un domaine. `capital-humain` lit /hr/score/, les autres /score/<domaine>/.
 *  Même forme de réponse. Gouverné : `available=false` → N/D côté UI. Pas de mock (jamais de score inventé). */
export function useDomainScore(domainId: string | undefined, year: number, quarter: number, subsidiary = "all",
                               filtresRh = "") {
  const sub = subsidiary && subsidiary !== "all" ? `&subsidiary=${subsidiary}` : "";
  const enabled = Boolean(domainId) && !USE_MOCK && SCORE_DOMAINS.includes(domainId as (typeof SCORE_DOMAINS)[number]);
  // Capital Humain : le score est calculé sur l'historique, sous TOUS les filtres
  // du cockpit — pas seulement année et trimestre.
  const path =
    domainId === "capital-humain"
      ? `/governance/hr/score/?${filtresRh || `year=${year}&quarter=${quarter}${sub}`}`
      : `/governance/score/${domainId}/?year=${year}&quarter=${quarter}${sub}`;
  return useQuery<GovernanceScoreResponse>({
    queryKey: ["domain-score", domainId, year, quarter, subsidiary, filtresRh],
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
  /** Pourquoi la ventilation demandée n'est pas servie (filtre ou périmètre). */
  ventilation_motif?: string | null;
  /** Série jour par jour de chaque code (`matrice=site|type`) ; `null` dans une case = non mesuré. */
  matrice?: {
    dimension: "site" | "type";
    lignes: { code: string; libelle: string }[];
    jours: string[];
    valeurs: Array<Array<number | null>>;
  } | null;
  matrice_motif?: string | null;
  /** Seuils de décision publiés avec une mesure Shield (`shield_rules`). */
  seuils?: { presence_critique: number; presence_surveillance: number; [cle: string]: number };
  aujourd_hui?: { value: number | null; status: string; reason?: string | null; date: string } | null;
  historique_depuis?: string | null;
  /** Périmètre réellement appliqué par le serveur : "GROUP" ou les codes filiales. */
  perimetre?: "GROUP" | string[];
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

/* ── Signaux RH et seuils arbitrés (`/governance/hr/signaux/`, `/hr/seuils/`) ── */

export type EtatSignal = "critique" | "surveillance" | "normal" | "non_mesure";

export interface SeuilsSignal {
  /** « bas » : une valeur basse est mauvaise (présence) ; « haut » : l'inverse. */
  sens: "bas" | "haut";
  unite: string;
  surveillance: number;
  critique: number;
  par_defaut: boolean;
  defaut: { surveillance: number; critique: number };
}

export interface SignalRh {
  cle: string;
  libelle: string;
  regle: string;
  lien: string;
  etat: EtatSignal;
  valeur: number | null;
  motif?: string | null;
  source?: string | null;
  metric_id?: string | null;
  seuils?: SeuilsSignal | null;
  confiance?: "élevée" | "moyenne" | "faible" | null;
  couverture?: { jours: number; jours_mesures: number } | null;
  comparaison?: { value: number | null; ecart: number | null; ecart_pct: number | null; unite_ecart: "pts" | "abs" | null } | null;
  details?: { code: string; libelle: string; valeur: number; etat: EtatSignal }[];
  pire?: { libelle: string; valeur: number } | null;
  sites_mesures?: number;
  effectif?: number;
}

export interface HrSignaux {
  signaux: SignalRh[];
  compteurs: Record<EtatSignal, number>;
  periode: { debut: string; fin: string; libelle: string; jusqu_a: string };
  seuils_modifiables: boolean;
}

export function useHrSignals(filtres: string, enabled = true) {
  return useQuery<HrSignaux>({
    queryKey: ["hr-signaux", filtres],
    enabled: enabled && !USE_MOCK,
    staleTime: 5 * 60_000,
    queryFn: () => apiGet<HrSignaux>(`/governance/hr/signaux/?${filtres}`),
  });
}

export interface SeuilRhLigne extends SeuilsSignal {
  signal: string;
  libelle: string;
  modifie_le: string | null;
  modifie_par: string | null;
}

export function useHrThresholds(enabled = true) {
  return useQuery<{ seuils: SeuilRhLigne[]; modifiable: boolean }>({
    queryKey: ["hr-seuils"],
    enabled: enabled && !USE_MOCK,
    queryFn: () => apiGet("/governance/hr/seuils/"),
  });
}

/** Arbitrer (ou réinitialiser) un seuil. Les signaux ET les mesures Shield qui
 *  portent les seuils (historique, constats du jour) sont relus ensuite. */
export function useSaveHrThreshold() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (corps: { signal: string; surveillance?: number; critique?: number; reinitialiser?: boolean }) =>
      apiPut<{ seuils: SeuilRhLigne[]; modifiable: boolean }>("/governance/hr/seuils/", corps),
    onSuccess: (donnees) => {
      client.setQueryData(["hr-seuils"], donnees);
      void client.invalidateQueries({ queryKey: ["hr-signaux"] });
      void client.invalidateQueries({ queryKey: ["hr-history"] });
      void client.invalidateQueries({ queryKey: ["shield", "hr-kpi"] });
    },
  });
}

/* ── Aide à la décision RH (`/governance/hr/decision/`) ──────────────────── */

export interface ConstatRh {
  id: string;
  titre: string;
  /** Le constat chiffré, calculé — jamais rédigé par un modèle. */
  constat: string;
  severite: "critique" | "surveillance" | "info";
  periode: string;
  lien: string;
  valeur?: number | null;
  unite?: string;
  comparaison?: string | null;
  source?: string | null;
  confiance?: "élevée" | "moyenne" | "faible" | null;
  regle?: string;
  action?: string | null;
  details?: { code: string; libelle: string; valeur: number }[] | null;
}

export type SectionSynthese = "resume" | "anomalies" | "hypotheses" | "risques" | "recommandations" | "priorites" | "questions";

export interface SyntheseRh {
  sections: Record<SectionSynthese, string[]>;
  /** Fournisseur ayant rédigé ; `ia` faux = synthèse composée des constats, sans modèle. */
  fournisseur: string | null;
  ia: boolean;
  /** Phrases retirées par le garde-fou (nombre absent des constats). */
  phrases_retirees: number;
  note?: string;
}

export interface DecisionRh {
  constats: ConstatRh[];
  angles_morts: { libelle: string; motif: string }[];
  synthese: SyntheseRh | null;
  periode: { debut: string; fin: string; libelle: string; jusqu_a: string };
}

export function useHrDecision(filtres: string, enabled = true) {
  return useQuery<DecisionRh>({
    queryKey: ["hr-decision", filtres],
    enabled: enabled && !USE_MOCK,
    staleTime: 5 * 60_000,
    queryFn: () => apiGet<DecisionRh>(`/governance/hr/decision/?${filtres}`),
  });
}

/** La synthèse rédigée : sur demande seulement (appel à un modèle). */
export function useHrSynthese(filtres: string, demandee: boolean) {
  return useQuery<DecisionRh>({
    queryKey: ["hr-decision", filtres, "synthese"],
    enabled: demandee && !USE_MOCK,
    staleTime: 10 * 60_000,
    queryFn: () => apiGet<DecisionRh>(`/governance/hr/decision/?${filtres}&synthese=1`),
  });
}

/* ── Rapports programmés (`/governance/hr/rapports-programmes/`) ─────────── */

export interface EnvoiRapport { destinataire: string; statut: "envoye" | "echec" | "ignore"; statut_libelle: string; detail: string; le: string }

export interface RapportProgramme {
  id: number;
  nom: string;
  frequence: "quotidien" | "hebdomadaire" | "mensuel";
  frequence_libelle: string;
  format: "xlsx" | "pdf" | "pptx";
  filtres: Record<string, string>;
  periode_libelle: string;
  actif: boolean;
  auteur: string;
  destinataires: { id: number; nom: string }[];
  prochain_envoi: string | null;
  dernier_envoi: string | null;
  envois: EnvoiRapport[];
}

export interface RapportsProgrammes {
  rapports: RapportProgramme[];
  smtp_configure: boolean;
  peut_programmer_pour_autrui: boolean;
  destinataires_possibles: { id: number; nom: string }[];
  periodes: Record<string, string>;
}

const CLE_RAPPORTS = ["hr-rapports-programmes"];

export function useRapportsProgrammes() {
  return useQuery<RapportsProgrammes>({
    queryKey: CLE_RAPPORTS,
    enabled: !USE_MOCK,
    queryFn: () => apiGet<RapportsProgrammes>("/governance/hr/rapports-programmes/"),
  });
}

/** Créer, modifier, supprimer, envoyer : chaque écriture relit la liste. */
export function useEcrireRapport() {
  const client = useQueryClient();
  const relire = () => client.invalidateQueries({ queryKey: CLE_RAPPORTS });
  return {
    creer: useMutation({
      mutationFn: (corps: Omit<Partial<RapportProgramme>, "destinataires"> & { destinataires?: number[] }) =>
        apiPostDetail<RapportProgramme>("/governance/hr/rapports-programmes/", corps),
      onSuccess: relire,
    }),
    modifier: useMutation({
      mutationFn: ({ id, ...corps }: { id: number; actif?: boolean }) =>
        apiPatch<RapportProgramme>(`/governance/hr/rapports-programmes/${id}/`, corps),
      onSuccess: relire,
    }),
    supprimer: useMutation({
      mutationFn: (id: number) => apiDelete(`/governance/hr/rapports-programmes/${id}/`),
      onSuccess: relire,
    }),
    envoyer: useMutation({
      mutationFn: (id: number) => apiPostDetail<RapportProgramme>(`/governance/hr/rapports-programmes/${id}/envoyer/`),
      onSuccess: relire,
    }),
  };
}
