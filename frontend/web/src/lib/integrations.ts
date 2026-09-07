import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  ConnectorEndpoint,
  DataSource,
  FieldMapping,
  HealthResponse,
  SyncErrorItem,
  SyncJob,
  SessionAuth,
  SyncLogItem,
} from "@/types/integrations";

import { API_BASE as BASE, getToken } from "@/lib/api";

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  const token = getToken();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

/** Erreur d'API porteuse de son code HTTP : un 403 (« pas le droit de voir »)
 *  ne doit pas être présenté comme un 500 (« la source est en panne »). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** Erreurs par champ renvoyées par DRF sur un 400. */
    readonly details?: Record<string, string[] | string>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method, headers: headers(), body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) {
    // Un 400 de DRF porte le détail par champ : le perdre obligerait l'utilisateur
    // à deviner quel champ est refusé.
    let details: Record<string, string[] | string> | undefined;
    try {
      const parsed = await res.json();
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) details = parsed;
    } catch {
      /* réponse non-JSON (page d'erreur du proxy, par exemple) */
    }
    throw new ApiError(res.status, `API ${res.status} ${method} ${path}`, details);
  }
  return (res.status === 204 ? (undefined as T) : ((await res.json()) as T));
}

/** Un refus (401/403/404) ne devient pas un succès en réessayant.
 *
 *  Par défaut TanStack Query retente trois fois : l'écran restait dix secondes
 *  sur « Chargement… » avant d'afficher « accès réservé ». Seules les erreurs
 *  serveur ou réseau méritent une seconde chance.
 */
function retryHorsRefus(nbEchecs: number, error: unknown) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
  // UNE seule reprise, pas deux. Face à un amont mort, chaque tentative
  // supplémentaire triple la charge sur un service déjà en difficulté et retarde
  // d'autant le message qui, lui, ne changera pas. Une reprise reste utile : elle
  // absorbe la fenêtre de quelques secondes d'un redéploiement.
  return nbEchecs < 1;
}

export function useSources() {
  return useQuery<DataSource[]>({
    queryKey: ["integrations", "sources"],
    queryFn: () => req<DataSource[]>("GET", "/integrations/sources/"),
    retry: retryHorsRefus,
  });
}

export function useSource(id: string | undefined) {
  return useQuery<DataSource>({
    queryKey: ["integrations", "source", id],
    enabled: Boolean(id),
    queryFn: () => req<DataSource>("GET", `/integrations/sources/${id}/`),
    retry: retryHorsRefus,
  });
}

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["integrations", "health"],
    queryFn: () => req<HealthResponse>("GET", "/integrations/sources/health/"),
    // Rafraîchissement discret : l'indicateur global du header reste vivant
    // sans rechargement de page. `retry: false` évite d'insister si l'API est down.
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    retry: false,
  });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["integrations"] });
}

/** Retrouve une source par son code.
 *
 *  Sert au rattrapage : si la création a échoué de façon AMBIGUË (502, coupure —
 *  la requête est peut-être arrivée, la réponse non), la ligne peut exister côté
 *  serveur. Réessayer à l'aveugle buterait alors sur « ce code existe déjà ».
 */
export async function fetchSourceBySlug(slug: string): Promise<DataSource | undefined> {
  const sources = await req<DataSource[]>("GET", "/integrations/sources/");
  const trouvee = sources.find((s) => s.slug === slug);
  if (!trouvee) return undefined;
  // La LISTE est servie par un sérialiseur allégé qui aplatit le connecteur au lieu
  // de l'imbriquer : `connector.id` y est absent. S'en contenter faisait sauter la
  // configuration du connecteur au réessai, et le test échouait ensuite sur
  // « Configuration incomplète : URL de base ». On relit donc le détail.
  return req<DataSource>("GET", `/integrations/sources/${trouvee.id}/`);
}

export function useCreateSource() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: Partial<DataSource>) => req<DataSource>("POST", "/integrations/sources/", payload),
    onSuccess: invalidate,
  });
}

export function useUpdateConnector() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Record<string, unknown> }) =>
      req("PATCH", `/integrations/connectors/${id}/`, patch),
    onSuccess: invalidate,
  });
}

export function useTestConnection() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (sourceId: string) =>
      req<{ ok: boolean; message: string; status: string; latency_ms: number | null; tested_at: string | null }>(
        "POST",
        `/integrations/sources/${sourceId}/test-connection/?probe=1`,
      ),
    onSuccess: invalidate,
  });
}

/** Relance la session Shield.
 *
 *  Sans jetons : force un renouvellement — suffisant tant que le refresh vit.
 *  Avec jetons : dépose un couple neuf. Les deux sont exigés par le backend, un
 *  access seul redonnant une session qui expire sans recours.
 *
 *  Les jetons ne transitent que dans ce corps de requête : ils ne sont jamais
 *  écrits en storage, ni journalisés, ni renvoyés par la réponse.
 */
export function useReauthenticate() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ sourceId, access, refresh }: { sourceId: string; access?: string; refresh?: string }) =>
      req<{ ok: boolean; message: string; auth: SessionAuth }>(
        "POST",
        `/integrations/sources/${sourceId}/reauthenticate/`,
        access || refresh ? { access, refresh } : {},
      ),
    // `onSettled` et non `onSuccess` : un échec change l'état de la session tout
    // autant qu'une réussite. Quand Shield refuse le renouvellement, le backend
    // retient la cause et le renouvellement automatique cesse d'être promis — sans
    // relire la fiche, l'écran continuait d'afficher « aucun jeton à recoller à
    // l'expiration » juste au-dessus du refus.
    onSettled: invalidate,
  });
}

export function useSyncNow() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (sourceId: string) => req<SyncJob>("POST", `/integrations/sources/${sourceId}/sync-now/`),
    onSuccess: invalidate,
  });
}

export function useEndpoints(connectorId: string | undefined) {
  return useQuery<ConnectorEndpoint[]>({
    queryKey: ["integrations", "endpoints", connectorId],
    enabled: Boolean(connectorId),
    queryFn: () => req<ConnectorEndpoint[]>("GET", `/integrations/endpoints/?connector=${connectorId}`),
  });
}

export function useCreateEndpoint() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: Partial<ConnectorEndpoint> & { connector: string }) =>
      req<ConnectorEndpoint>("POST", "/integrations/endpoints/", payload),
    onSuccess: invalidate,
  });
}

export function useDeleteEndpoint() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => req("DELETE", `/integrations/endpoints/${id}/`), onSuccess: invalidate });
}

export function useMappings(endpointId: string | undefined) {
  return useQuery<FieldMapping[]>({
    queryKey: ["integrations", "mappings", endpointId],
    enabled: Boolean(endpointId),
    queryFn: () => req<FieldMapping[]>("GET", `/integrations/mappings/?endpoint=${endpointId}`),
  });
}

export function useCreateMapping() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: Partial<FieldMapping> & { endpoint: string }) =>
      req<FieldMapping>("POST", "/integrations/mappings/", payload),
    onSuccess: invalidate,
  });
}

export function useDeleteMapping() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => req("DELETE", `/integrations/mappings/${id}/`), onSuccess: invalidate });
}

export function useJobs(sourceId: string | undefined) {
  return useQuery<SyncJob[]>({
    queryKey: ["integrations", "jobs", sourceId],
    enabled: Boolean(sourceId),
    queryFn: () => req<SyncJob[]>("GET", `/integrations/jobs/?source=${sourceId}`),
  });
}

export function useLogs(sourceId: string | undefined) {
  return useQuery<SyncLogItem[]>({
    queryKey: ["integrations", "logs", sourceId],
    enabled: Boolean(sourceId),
    queryFn: () => req<SyncLogItem[]>("GET", `/integrations/logs/?source=${sourceId}`),
  });
}

export function useErrors(sourceId: string | undefined) {
  return useQuery<SyncErrorItem[]>({
    queryKey: ["integrations", "errors", sourceId],
    enabled: Boolean(sourceId),
    queryFn: () => req<SyncErrorItem[]>("GET", `/integrations/errors/?source=${sourceId}`),
  });
}

export function useAddCredential() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (payload: { connector: string; kind: string; label?: string; secret: string }) =>
      req("POST", "/integrations/credentials/", payload),
    onSuccess: invalidate,
  });
}

export function useToggleActive() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (sourceId: string) => req("POST", `/integrations/sources/${sourceId}/toggle-active/`),
    onSuccess: invalidate,
  });
}
