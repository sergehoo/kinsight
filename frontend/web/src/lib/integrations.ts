import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  ConnectorEndpoint,
  DataSource,
  FieldMapping,
  HealthResponse,
  SyncErrorItem,
  SyncJob,
  SyncLogItem,
} from "@/types/integrations";

import { API_BASE as BASE, getToken } from "@/lib/api";

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  const token = getToken();
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method, headers: headers(), body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(`API ${res.status} ${method} ${path}`);
  return (res.status === 204 ? (undefined as T) : ((await res.json()) as T));
}

export function useSources() {
  return useQuery<DataSource[]>({
    queryKey: ["integrations", "sources"],
    queryFn: () => req<DataSource[]>("GET", "/integrations/sources/"),
  });
}

export function useSource(id: string | undefined) {
  return useQuery<DataSource>({
    queryKey: ["integrations", "source", id],
    enabled: Boolean(id),
    queryFn: () => req<DataSource>("GET", `/integrations/sources/${id}/`),
  });
}

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["integrations", "health"],
    queryFn: () => req<HealthResponse>("GET", "/integrations/sources/health/"),
  });
}

function useInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["integrations"] });
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
    mutationFn: (sourceId: string) => req<{ ok: boolean; message: string; status: string }>("POST", `/integrations/sources/${sourceId}/test-connection/?probe=1`),
    onSuccess: invalidate,
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
