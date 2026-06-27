/** Authentification réelle : login JWT + profil /me (rôle, permissions, atterrissage). */

import { API_BASE, clearSession, getToken, setSession, TOKEN_KEY, USER_KEY } from "@/lib/api";
import { applyAuthPermissions } from "@/lib/permissions";

export interface MeProfile {
  username: string;
  full_name: string;
  role: string;
  is_superuser: boolean;
  is_group_scope: boolean;
  subsidiaries: string[];
  scope: "GROUP" | string[];
  can_see_nominative: boolean;
  permissions: string[];
  landing: string;
}

/** Authentifié = un token de session réel a été obtenu par login (pas le token d'env de dev). */
export function isAuthenticated(): boolean {
  return typeof window !== "undefined" && Boolean(window.localStorage.getItem(TOKEN_KEY));
}

export function getStoredUser(): MeProfile | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as MeProfile;
  } catch {
    return null;
  }
}

/** Récupère le profil + applique permissions/rôle (source de vérité backend). */
export async function fetchMe(): Promise<MeProfile> {
  const res = await fetch(`${API_BASE}/auth/me/`, { headers: { Authorization: `Bearer ${getToken()}`, Accept: "application/json" } });
  if (!res.ok) throw new Error("Profil indisponible.");
  const me = (await res.json()) as MeProfile;
  window.localStorage.setItem(USER_KEY, JSON.stringify(me));
  applyAuthPermissions(me.permissions, me.role);
  return me;
}

/** Connexion : obtient le JWT puis charge le profil. Lève si identifiants invalides. */
export async function login(username: string, password: string): Promise<MeProfile> {
  const res = await fetch(`${API_BASE}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new Error(res.status === 401 ? "Identifiant ou mot de passe incorrect." : `Connexion impossible (${res.status}).`);
  }
  const { access, refresh } = (await res.json()) as { access: string; refresh?: string };
  setSession(access, refresh);
  return fetchMe();
}

export function logout(): void {
  clearSession();
}
