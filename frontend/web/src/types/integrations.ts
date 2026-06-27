export type SourceStatus =
  | "not_configured"
  | "configured"
  | "testing"
  | "connected"
  | "syncing"
  | "error"
  | "disabled";

export interface DataSource {
  id: string;
  name: string;
  slug: string;
  source_type: string;
  source_type_label: string;
  target_module: string;
  target_module_label?: string;
  status: SourceStatus;
  status_label: string;
  is_active: boolean;
  demo_mode: boolean;
  sync_frequency: string;
  description?: string;
  updated_at: string;
  jobs_count?: number;
  errors_count?: number;
  connector?: DataConnector;
}

export interface DataConnector {
  id: string;
  base_url: string;
  auth_method: string;
  headers: Record<string, string>;
  config: Record<string, unknown>;
  last_tested_at: string | null;
  last_test_ok: boolean | null;
  last_test_message: string;
  endpoints?: unknown[];
  credentials?: { id: string; kind: string; label: string; is_set: boolean; masked: string }[];
}

export interface HealthResponse {
  total: number;
  active: number;
  connected: number;
  error: number;
  by_status: Record<string, number>;
  sources: DataSource[];
}

export interface SyncJob {
  id: string;
  source: string;
  trigger: string;
  status: string;
  rows_ingested: number;
  message: string;
  created_at: string;
  finished_at: string | null;
}

export interface ConnectorEndpoint {
  id: string;
  connector: string;
  name: string;
  path: string;
  http_method: string;
  incremental: boolean;
  cursor_field: string;
  is_active: boolean;
  mappings?: FieldMapping[];
}

export interface FieldMapping {
  id: string;
  endpoint: string;
  source_field: string;
  target_field: string;
  target_table: string;
  transform: string;
  is_key: boolean;
}

export interface SyncLogItem {
  id: string;
  level: string;
  message: string;
  created_at: string;
}

export interface SyncErrorItem {
  id: string;
  code: string;
  message: string;
  resolved: boolean;
  created_at: string;
}
