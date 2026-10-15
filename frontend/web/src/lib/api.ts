/** Client HTTP de l'API governance + gestion du token JWT (auth réelle par utilisateur). */

const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const TOKEN_KEY = "k-insight-token";
export const REFRESH_KEY = "k-insight-refresh";
export const USER_KEY = "k-insight-user";

/** Token courant : JWT de l'utilisateur connecté (localStorage), repli sur l'env en dev.
 *
 *  Le repli est confiné au DÉVELOPPEMENT. `VITE_API_TOKEN` est câblé en argument
 *  de build jusque dans les compose de production : renseigné un jour dans
 *  Dokploy, il aurait été inscrit EN CLAIR dans le bundle public, et toute
 *  requête serait restée authentifiée après la déconnexion — `clearSession`
 *  vide le stockage, pas le code. `import.meta.env.DEV` vaut le littéral `false`
 *  en production : la branche et la chaîne disparaissent du bundle.
 */
export function getToken(): string | undefined {
  if (typeof window !== "undefined") {
    const t = window.localStorage.getItem(TOKEN_KEY);
    if (t) return t;
  }
  if (import.meta.env.DEV) return import.meta.env.VITE_API_TOKEN as string | undefined;
  return undefined;
}

export function setSession(access: string, refresh?: string): void {
  window.localStorage.setItem(TOKEN_KEY, access);
  if (refresh) window.localStorage.setItem(REFRESH_KEY, refresh);
}

/** Vide les caches HTTP contenant des réponses métier authentifiées.
 *
 *  Le Cache Storage survit à la déconnexion : sans cette purge, les réponses
 *  API du compte précédent resteraient lisibles sur un poste partagé. Les
 *  jetons, eux, ne sont jamais mis en cache (auth en NetworkOnly côté SW). */
export async function purgeApiCaches(): Promise<void> {
  if (typeof caches === "undefined") return;
  try {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n.startsWith("ki-api")).map((n) => caches.delete(n)));
  } catch {
    /* Cache Storage indisponible (mode privé, contexte non sécurisé) */
  }
}

/** Efface toute trace de session (token + profil + permissions + caches API).
 *
 *  Rend la promesse de la purge : un appelant qui recharge la page juste après
 *  doit l'ATTENDRE, sinon le déchargement peut interrompre la suppression et
 *  laisser des réponses authentifiées dans le Cache Storage. */
export function clearSession(): Promise<void> {
  for (const k of [TOKEN_KEY, REFRESH_KEY, USER_KEY, "k-insight-permissions", "k-insight-role"]) {
    window.localStorage.removeItem(k);
  }
  return purgeApiCaches();
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json", ...extra };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

/** Sur 401 définitif : session expirée/invalide → on nettoie et on renvoie vers /login. */
function on401(): void {
  // Les jetons sont effacés immédiatement (synchrone) ; la redirection, elle,
  // attend la purge des caches : `location.assign` décharge la page, et une
  // suppression du Cache Storage en cours peut ne pas y survivre.
  const purge = clearSession();
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    const cible = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    void purge.finally(() => window.location.assign(cible));
  }
}

/** Issue d'une tentative de renouvellement.
 *
 *  Les trois cas appellent trois gestes DIFFÉRENTS, et les confondre est
 *  exactement ce qui déconnectait l'utilisateur à tort : un refus doit ramener à
 *  l'écran de connexion, une coupure réseau ne doit rien effacer du tout.
 */
type IssueRenouvellement =
  | { acces: string }
  | { refus: true }
  | { reseau: true };

/** Une seule requête de renouvellement en vol à la fois.
 *
 *  Un écran lance volontiers six requêtes en parallèle. À l'expiration, les six
 *  prennent un 401 en même temps ; sans ce verrou, six renouvellements partent,
 *  et comme la rotation est active côté serveur, cinq d'entre eux présentent un
 *  jeton déjà remplacé. Tous partagent donc la même promesse.
 */
let renouvellementEnVol: Promise<IssueRenouvellement> | null = null;

function jetonDeRenouvellement(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

async function renouvelerLaSession(): Promise<IssueRenouvellement> {
  if (renouvellementEnVol) return renouvellementEnVol;

  const refresh = jetonDeRenouvellement();
  // Pas de jeton de renouvellement : rien à tenter. C'est le cas du jeton de
  // développement (`VITE_API_TOKEN`) et des sessions ouvertes avant cette
  // version — elles n'en avaient pas enregistré d'utilisable.
  if (!refresh) return { refus: true };

  renouvellementEnVol = (async (): Promise<IssueRenouvellement> => {
    let res: Response;
    try {
      res = await fetch(`${BASE}/auth/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ refresh }),
      });
    } catch {
      // `fetch` ne rejette que sur un échec de transport. Ce n'est pas un refus :
      // effacer la session ici déconnecterait sur un simple passage de tunnel.
      return { reseau: true };
    }
    if (res.status >= 500) return { reseau: true };
    if (!res.ok) return { refus: true };

    const data = (await res.json().catch(() => null)) as { access?: string; refresh?: string } | null;
    // Un 200 au corps illisible n'est PAS un refus : le serveur a accepté le
    // jeton puis quelque chose s'est mal passé en chemin — proxy qui tronque,
    // réponse coupée. Le classer en refus déconnectait sur une anomalie de
    // plateforme, alors que la session est probablement intacte.
    if (!data) return { reseau: true };
    if (!data.access) return { refus: true };
    // La rotation est active : la réponse porte un jeton de renouvellement neuf
    // qu'il faut enregistrer, sinon la session mourrait quand même à l'échéance
    // du premier.
    setSession(data.access, data.refresh);
    return { acces: data.access };
  })().finally(() => {
    renouvellementEnVol = null;
  });

  return renouvellementEnVol;
}

/** Appel authentifié, avec renouvellement silencieux sur 401.
 *
 *  Le 401 n'est plus une fin de session : on renouvelle, puis on rejoue l'appel
 *  UNE fois. Un second 401 après un jeton frais n'est pas une expiration mais un
 *  refus de droits — insister ne le changerait pas.
 */
export async function fetchAuthentifie(path: string, init?: RequestInit, extra?: Record<string, string>): Promise<Response> {
  const envoyer = () => fetch(`${BASE}${path}`, { ...init, headers: authHeaders(extra) });

  const res = await envoyer();
  if (res.status !== 401) return res;

  const issue = await renouvelerLaSession();
  if ("acces" in issue) {
    const rejoue = await envoyer();
    if (rejoue.status === 401) on401();
    return rejoue;
  }
  if ("reseau" in issue) {
    // La session est peut-être intacte : on laisse l'appelant échouer et
    // retenter, sans rien effacer ni rediriger.
    throw new Error("Session momentanément invérifiable (réseau).");
  }
  on401();
  throw new Error("Session expirée");
}

/** Renouvelle par anticipation si l'accès est sur le point d'expirer.
 *
 *  Évite le hoquet visible : sans cela, le premier appel après une nuit prend un
 *  401, attend le renouvellement, puis se rejoue — l'écran reste vide pendant ce
 *  temps. Appelé au retour sur l'onglet.
 */
export async function renouvelerSiProche(margeSecondes = 120): Promise<void> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_KEY) : null;
  if (!token || !jetonDeRenouvellement()) return;
  const fin = expirationDuJeton(token);
  if (fin === null) return;
  if (fin - Date.now() / 1000 > margeSecondes) return;
  const issue = await renouvelerLaSession();
  // Ignorer le refus laissait l'utilisateur devant un écran qui se croit
  // connecté : rien ne se passait jusqu'à ce qu'une requête prenne un 401. On
  // tranche tout de suite, au moment où l'on vient justement de l'apprendre.
  if ("refus" in issue) on401();
}

/** Date d'expiration portée par un JWT, en secondes epoch.
 *
 *  Lecture SANS vérification de signature, et c'est volontaire : seul le serveur
 *  juge de la validité. Cette valeur ne sert qu'à décider du moment d'un
 *  renouvellement, jamais d'un droit.
 */
export function expirationDuJeton(token: string): number | null {
  const corps = token.split(".")[1];
  if (!corps) return null;
  try {
    const json = atob(corps.replace(/-/g, "+").replace(/_/g, "/"));
    const charge = JSON.parse(json) as { exp?: number };
    return typeof charge.exp === "number" ? charge.exp : null;
  } catch {
    return null;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetchAuthentifie(path);
  if (!res.ok) throw new Error(`Erreur API ${res.status} sur ${path}`);
  return (await res.json()) as T;
}

/** Réponse enrichie de sa fraîcheur. `stale` vaut true quand le service worker
 *  a servi la dernière donnée connue faute de réseau (en-tête `x-ki-stale`). */
export interface ApiResult<T> {
  data: T;
  stale: boolean;
  cachedAt?: string;
}

/** Variante de `apiGet` qui remonte l'origine de la réponse. Utilisée par les vues
 *  qui doivent distinguer « à jour » de « dernière donnée connue ». */
export async function apiGetMeta<T>(path: string): Promise<ApiResult<T>> {
  const res = await fetchAuthentifie(path);
  if (!res.ok) throw new Error(`Erreur API ${res.status} sur ${path}`);
  return {
    data: (await res.json()) as T,
    stale: res.headers.get("x-ki-stale") === "1",
    cachedAt: res.headers.get("x-ki-cached-at") ?? undefined,
  };
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchAuthentifie(
    path,
    { method: "POST", body: JSON.stringify(body) },
    { "Content-Type": "application/json" },
  );
  if (!res.ok) throw new Error(`Erreur API ${res.status} sur ${path}`);
  return (await res.json()) as T;
}

/** Écriture JSON (PUT, PATCH, DELETE…). Un refus garde le MOTIF du serveur
 *  (`detail`) : un seuil rejeté ou un destinataire non autorisé doit dire
 *  pourquoi, pas « Erreur 400 ». Un 204 rend `undefined`. */
async function apiEcrire<T>(methode: string, path: string, body?: unknown): Promise<T> {
  const res = await fetchAuthentifie(
    path,
    { method: methode, body: body === undefined ? undefined : JSON.stringify(body) },
    { "Content-Type": "application/json" },
  );
  if (!res.ok) {
    let detail = "";
    try {
      detail = ((await res.json()) as { detail?: string }).detail ?? "";
    } catch {
      /* corps illisible : le statut suffit */
    }
    throw new Error(detail || `Erreur API ${res.status} sur ${path}`);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const apiPut = <T>(path: string, body: unknown) => apiEcrire<T>("PUT", path, body);
export const apiPatch = <T>(path: string, body: unknown) => apiEcrire<T>("PATCH", path, body);
export const apiDelete = (path: string) => apiEcrire<void>("DELETE", path);
export const apiPostDetail = <T>(path: string, body?: unknown) => apiEcrire<T>("POST", path, body ?? {});

/** Télécharge un fichier authentifié (blob) et déclenche l'enregistrement navigateur. */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const res = await fetchAuthentifie(path);
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
