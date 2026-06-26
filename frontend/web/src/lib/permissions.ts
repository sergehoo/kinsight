export type Permission = string;

export const SUPER_ADMIN_PERMISSION = "SUPER_ADMIN";
const STORAGE_KEY = "k-insight-permissions";

function parsePermissions(raw: string | null): Permission[] {
  if (!raw) return [SUPER_ADMIN_PERMISSION];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [SUPER_ADMIN_PERMISSION];
  } catch {
    return raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
}

export function getCurrentPermissions(): Permission[] {
  if (typeof window === "undefined") return [SUPER_ADMIN_PERMISSION];
  return parsePermissions(window.localStorage.getItem(STORAGE_KEY));
}

export function canAccess(requiredPermissions: readonly Permission[] | undefined, userPermissions = getCurrentPermissions()) {
  if (!requiredPermissions?.length) return true;
  if (userPermissions.includes(SUPER_ADMIN_PERMISSION) || userPermissions.includes("view_all_dashboards")) return true;
  return requiredPermissions.every((permission) => userPermissions.includes(permission));
}
