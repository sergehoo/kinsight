/** Client HTTP de l'API governance + gestion du token JWT (auth réelle par utilisateur). */

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const TOKEN_KEY = "k-insight-token";
export const REFRESH_KEY = "k-insight-refresh";
export const USER_KEY = "k-insight-user";

/** Token courant : JWT de l'utilisateur connecté (localStorage), repli sur l'env en dev. */
export function getToken(): string | undefined {
  if (typeof window !== "undefined") {
    const t = window.localStorage.getItem(TOKEN_KEY);
    if (t) return t;
  }
  return import.meta.env.VITE_API_TOKEN as string | undefined;
}

export function setSession(access: string, refresh?: string): void {
  window.localStorage.setItem(TOKEN_KEY, access);
  if (refresh) window.localStorage.setItem(REFRESH_KEY, refresh);
}

/** Efface toute trace de session (token + profil + permissions). */
export function clearSession(): void {
  for (const k of [TOKEN_KEY, REFRESH_KEY, USER_KEY, "k-insight-permissions", "k-insight-role"]) {
    window.localStorage.removeItem(k);
  }
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json", ...extra };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

/** Sur 401 : session expirée/invalide → on nettoie et on renvoie vers /login. */
function on401(): void {
  clearSession();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (res.status === 401) {
    on401();
    throw new Error("Session expirée");
  }
  if (!res.ok) throw new Error(`Erreur API ${res.status} sur ${path}`);
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  if (res.status === 401) {
    on401();
    throw new Error("Session expirée");
  }
  if (!res.ok) throw new Error(`Erreur API ${res.status} sur ${path}`);
  return (await res.json()) as T;
}

/** Télécharge un fichier authentifié (blob) et déclenche l'enregistrement navigateur. */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { headers: authHeaders() });
  if (res.status === 401) {
    on401();
    throw new Error("Session expirée");
  }
  if (!res.ok) throw new Error(`Erreur export ${res.status} sur ${path}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const API_BASE = BASE;
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
