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

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", "Content-Type": "application/json" };
  if (TOKEN) headers.Authorization = `Bearer ${TOKEN}`;
  const res = await fetch(`${BASE}${path}`, { method: "POST", headers, body: JSON.stringify(body) });
  if (!res.ok) {
    throw new Error(`Erreur API ${res.status} sur ${path}`);
  }
  return (await res.json()) as T;
}

/** Télécharge un fichier authentifié (blob) et déclenche l'enregistrement navigateur. */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const headers: Record<string, string> = {};
  if (TOKEN) headers.Authorization = `Bearer ${TOKEN}`;
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) {
    throw new Error(`Erreur export ${res.status} sur ${path}`);
  }
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

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
