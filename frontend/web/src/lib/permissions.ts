export type Permission = string;

export const SUPER_ADMIN_PERMISSION = "SUPER_ADMIN";
const STORAGE_KEY = "k-insight-permissions";
const ROLE_STORAGE_KEY = "k-insight-role";

/** Permissions par domaine analytique (topbar) + quelques permissions fines (sidebar). */
export const DOMAIN_PERMISSION = {
  overview: "view_group_overview",
  immobilier: "view_real_estate",
  capitalHumain: "view_hr",
  finance: "view_finance",
  operations: "view_operations",
  commercial: "view_commercial",
  risque: "view_risk",
  ia: "view_ai",
  reports: "view_reports",
} as const;

/** Rôles métiers et périmètre de domaines visibles (cf. règles de gouvernance). */
export type Role = "SUPER_ADMIN" | "DG" | "CODIR" | "DAF" | "RH" | "DIR_IMMO" | "READER";

export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  // DG / CODIR / SUPER_ADMIN : accès à tous les domaines.
  SUPER_ADMIN: [SUPER_ADMIN_PERMISSION],
  DG: ["view_all_dashboards"],
  CODIR: ["view_all_dashboards"],
  // DAF : Finance, Rapports et certains KPI Groupe.
  DAF: [DOMAIN_PERMISSION.finance, DOMAIN_PERMISSION.reports, DOMAIN_PERMISSION.overview],
  // RH : uniquement Capital Humain.
  RH: [DOMAIN_PERMISSION.capitalHumain],
  // Directeur Immobilier : Immobilier, Opérations et Commercial.
  DIR_IMMO: [DOMAIN_PERMISSION.immobilier, DOMAIN_PERMISSION.operations, DOMAIN_PERMISSION.commercial],
  // Lecteur : vue Groupe consolidée seulement.
  READER: [DOMAIN_PERMISSION.overview, DOMAIN_PERMISSION.reports],
};

function parsePermissions(raw: string | null): Permission[] {
  // Défaut = AUCUN accès (l'utilisateur non authentifié est renvoyé vers /login par le garde
  // de route). Les permissions réelles sont écrites au login depuis /api/v1/auth/me/.
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
}

export function getCurrentPermissions(): Permission[] {
  if (typeof window === "undefined") return [];
  return parsePermissions(window.localStorage.getItem(STORAGE_KEY));
}

export function getCurrentRole(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(ROLE_STORAGE_KEY) || "";
}

/** Applique les permissions + le rôle reçus du backend (/auth/me) — source de vérité RBAC. */
export function applyAuthPermissions(permissions: Permission[], role: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(permissions));
  window.localStorage.setItem(ROLE_STORAGE_KEY, role);
}

/** Applique le périmètre d'un rôle (démo/SSO à venir) : écrit ses permissions. */
export function setRole(role: Role) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ROLE_STORAGE_KEY, role);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ROLE_PERMISSIONS[role] ?? [SUPER_ADMIN_PERMISSION]));
}

export function canAccess(requiredPermissions: readonly Permission[] | undefined, userPermissions = getCurrentPermissions()) {
  if (!requiredPermissions?.length) return true;
  if (userPermissions.includes(SUPER_ADMIN_PERMISSION) || userPermissions.includes("view_all_dashboards")) return true;
  return requiredPermissions.every((permission) => userPermissions.includes(permission));
}
