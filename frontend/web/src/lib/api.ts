/** Client HTTP minimal pour l'API governance (lecture seule). */

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const TOKEN = import.meta.env.VITE_API_TOKEN as string | undefined;

export async function apiGet<T>(path: string): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (TOKEN) headers.Authorization = `Bearer ${TOKEN}`;

  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) {
    throw new Error(`Erreur API ${res.status} sur ${path}`);
  }
  return (await res.json()) as T;
}

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
