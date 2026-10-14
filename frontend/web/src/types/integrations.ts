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
  /** production | staging | sandbox — distingue un connecteur de recette. */
  environment?: string;
  environment_label?: string;
  /** Champs du connecteur remontés à plat pour la carte source. */
  base_url?: string;
  last_tested_at?: string | null;
  last_test_ok?: boolean | null;
  last_test_message?: string;
  last_latency_ms?: number | null;
  last_sync_at?: string | null;
  recent_errors?: Array<{ code: string; message: string; at: string }>;
}

/** Ce que le backend dit de la session Shield. Aucun jeton n'y figure, par
 *  construction : uniquement des états, des dates et des drapeaux. */
export interface SessionAuth {
  /** `valide` · `renouvelable` (access expiré mais refresh utilisable) · `auth_required` */
  etat: "valide" | "renouvelable" | "auth_required";
  access_present: boolean;
  expire_le: string | null;
  expiration_connue: boolean;
  renouvellement_automatique: boolean;
  refresh_present: boolean;
  derniere_authentification: string | null;
  dernier_echec: string | null;
  cause_dernier_echec: string | null;
  /** Un compte de service est ENREGISTRÉ — rien de plus. Il a été éprouvé
   *  auprès de Shield au moment du dépôt, mais sa seule présence ne prouve pas
   *  que la session se rétablira : c'est `liaison_permanente` qui le dit, en
   *  tenant compte des refus et du MFA survenus depuis. */
  compte_de_service?: boolean;
  /** Shield a refusé ce compte lors d'une reconnexion. Verdict durable : seule
   *  une connexion réussie le lève, pas un simple renouvellement de jeton. */
  compte_de_service_refuse?: boolean;
  /** Shield accepte le compte mais exige une seconde étape. Ce n'est PAS un
   *  refus d'identifiants — le mot de passe est bon — et aucune ressaisie n'y
   *  changera rien : seul un compte technique exempté, ou une clé d'API de
   *  portée `integration`, débloque. Distinct de `compte_de_service_refuse`
   *  précisément pour que l'écran n'envoie pas retaper un mot de passe juste. */
  mfa_requis?: boolean;
  liaison_permanente?: boolean;
  /** L'adresse du compte, jamais son mot de passe. */
  service_email?: string;
  derniere_reconnexion?: string | null;
}

/** État de la liaison Odoo, tel que le backend accepte de le montrer.
 *
 *  Ni la clé, ni le login complet, ni l'uid : le compte n'apparaît que masqué
 *  (« ser***@kaydan.tech »). La permanence d'Odoo ne vient pas d'un jeton — il
 *  n'y en a pas — mais du compte technique et de sa clé stockés chiffrés. */
export interface OdooAuth {
  etat: "connected" | "auth_required" | "error" | "disconnected" | "stale" | "connecting";
  identifiants_complets: boolean;
  /** Faux pour un connecteur configuré avant le chiffrement de la base et du login. */
  identifiants_chiffres: boolean;
  compte_de_service: string;
  base: string;
  version: string;
  derniere_authentification: string | null;
  derniere_verification: string | null;
  latence_ms: number | null;
  reconnexion_automatique: boolean;
  cause_dernier_echec: string | null;
  dernier_echec: string | null;
  message: string;
}

export interface OdooCompanies {
  status: string;
  companies: { id: number; name: string; subsidiary: string }[];
  mapping: Record<string, string>;
  orphans?: string[];
  subsidiaries: string[];
  detail?: string;
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
  last_latency_ms?: number | null;
  /** Renseigné uniquement pour une source Kaydan Shield. */
  session_auth?: SessionAuth | null;
  /** Renseigné uniquement pour une source Odoo RH. */
  odoo_auth?: OdooAuth | null;
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
  partial?: number;
  stale?: number;
  disabled?: number;
  avg_latency_ms?: number | null;
  last_sync?: string | null;
  stale_after_hours?: number;
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
