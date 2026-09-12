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

/** Échec de connexion portant le code HTTP, pour que l'écran dise la vraie cause.
 *
 *  Sans le code, la page ne pouvait distinguer un mot de passe erroné d'un
 *  serveur injoignable et affichait le même message pour les deux — celui qui
 *  fait ressaisir un mot de passe pourtant juste. `etape` distingue en outre le
 *  refus d'identifiants de l'échec de lecture du profil, qui n'appellent pas le
 *  même geste.
 */
export class LoginError extends Error {
  constructor(
    readonly statut: number | null,
    readonly etape: "jeton" | "profil" | "reseau",
    message: string,
  ) {
    super(message);
    this.name = "LoginError";
  }
}

/** Connexion : obtient le JWT puis charge le profil. Lève une `LoginError`. */
export async function login(username: string, password: string): Promise<MeProfile> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/auth/token/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    // `fetch` ne rejette que sur un échec de transport : ni serveur, ni DNS, ni
    // réseau. Ce n'est pas un refus d'identifiants et ne doit pas se lire ainsi.
    throw new LoginError(null, "reseau", "Serveur injoignable.");
  }
  if (!res.ok) throw new LoginError(res.status, "jeton", `Connexion refusée (${res.status}).`);

  const { access, refresh } = (await res.json()) as { access: string; refresh?: string };
  setSession(access, refresh);

  try {
    return await fetchMe();
  } catch {
    // Le jeton est valide mais le profil n'a pas pu être lu : sans permissions ni
    // rôle, l'application afficherait un cockpit vide en se croyant connectée.
    // On repart d'un état propre plutôt que de laisser cette moitié de session.
    clearSession();
    throw new LoginError(null, "profil",
      "Identifiants acceptés, mais le profil n'a pas pu être chargé. Session annulée.");
  }
}

export function logout(): void {
  clearSession();
}
