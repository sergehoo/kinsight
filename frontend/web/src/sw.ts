/// <reference lib="webworker" />
/**
 * Service worker K-Insight.
 *
 * Écrit à la main (stratégie `injectManifest`) parce que la règle de gouvernance
 * la plus importante ne s'exprime pas dans une configuration déclarative : une
 * réponse servie depuis le cache doit être RECONNAISSABLE comme telle par l'UI.
 * Le plugin `StaleMarker` ci-dessous ajoute `x-ki-stale` aux réponses de cache ;
 * `apiGetMeta` le lit et l'écran bascule en état « donnée datée ». Sans ce
 * marquage, une donnée métier vieille de plusieurs heures serait indiscernable
 * d'une donnée fraîche — exactement ce qu'interdit l'ADR-0007.
 */
import { cacheNames, clientsClaim } from "workbox-core";
import { CacheableResponsePlugin } from "workbox-cacheable-response";
import { ExpirationPlugin } from "workbox-expiration";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { CacheFirst, NetworkFirst, NetworkOnly } from "workbox-strategies";
import type { WorkboxPlugin } from "workbox-core/types";

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

const API_CACHE = "ki-api-stale";
const ASSET_CACHE = "ki-assets";

/* ── Coquille applicative ─────────────────────────────────────────────────── */
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Toute navigation retombe sur la coquille SPA : l'interface reste accessible
// hors ligne, ce sont les DONNÉES qui manquent, pas l'application.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL("index.html"), {
    denylist: [/^\/api\//, /^\/admin\//, /^\/static\//, /^\/media\//],
  }),
);

/* ── Marquage de fraîcheur ────────────────────────────────────────────────── */
const StaleMarker: WorkboxPlugin = {
  async cachedResponseWillBeUsed({ cachedResponse }) {
    if (!cachedResponse) return cachedResponse;
    const headers = new Headers(cachedResponse.headers);
    headers.set("x-ki-stale", "1");
    if (!headers.get("x-ki-cached-at")) {
      headers.set("x-ki-cached-at", headers.get("date") ?? new Date().toUTCString());
    }
    return new Response(await cachedResponse.blob(), {
      status: cachedResponse.status,
      statusText: cachedResponse.statusText,
      headers,
    });
  },
};

/** Clé de cache anonymisée : on ne stocke que l'URL, jamais les en-têtes.
 *
 *  Le Cache Storage conserve l'OBJET REQUÊTE, en-têtes compris : sans ce plugin,
 *  le `Authorization: Bearer <JWT>` se retrouve persisté sur le disque et survit
 *  à la déconnexion, lisible par tout script de l'origine. Vérifié : le jeton
 *  était bien présent avant l'ajout de ce garde-fou. */
const AnonymousCacheKey: WorkboxPlugin = {
  cacheKeyWillBeUsed: async ({ request }) => new Request(request.url, { method: "GET" }),
};

/* ── Portée : uniquement notre origine ────────────────────────────────────
   Une API servie depuis une AUTRE origine n'est jamais interceptée : on ne met
   pas en cache les réponses authentifiées d'un tiers, et on évite de casser sa
   négociation CORS. En production l'API est servie sur la même origine. */

/* ── Authentification : jamais de cache ───────────────────────────────────── */
// Jetons, /me, rafraîchissement : rien de tout cela ne doit atterrir dans le
// Cache Storage, qui survit à la déconnexion et est lisible par toute l'origine.
const sameOrigin = (url: URL) => url.origin === self.location.origin;

registerRoute(
  ({ url }) => sameOrigin(url) && /\/api\/v\d+\/auth\//.test(url.pathname),
  new NetworkOnly(),
);

/* ── Écritures et exports : jamais de cache ───────────────────────────────── */
registerRoute(
  ({ url, request }) => sameOrigin(url) && url.pathname.includes("/api/") && request.method !== "GET",
  new NetworkOnly(),
  "POST",
);

/* ── Données métier (GET) : réseau d'abord, cache en filet marqué ─────────── */
registerRoute(
  ({ url, request }) => sameOrigin(url) && url.pathname.includes("/api/") && request.method === "GET",
  new NetworkFirst({
    cacheName: API_CACHE,
    networkTimeoutSeconds: 6,
    plugins: [
      new CacheableResponsePlugin({ statuses: [200] }),
      new ExpirationPlugin({ maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 }),
      AnonymousCacheKey,
      StaleMarker,
    ],
  }),
);

/* ── Images et polices versionnées : cache d'abord ────────────────────────── */
registerRoute(
  ({ url, request }) =>
    sameOrigin(url) && (request.destination === "image" || request.destination === "font"),
  new CacheFirst({
    cacheName: ASSET_CACHE,
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 30 }),
    ],
  }),
);

/* ── Cycle de vie ─────────────────────────────────────────────────────────── */
// Pas de `skipWaiting()` automatique : la page décide du moment de la bascule
// pour ne jamais recharger sous les pieds de l'utilisateur.
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") void self.skipWaiting();
  // Déconnexion : purge des réponses métier mises en cache pour ce compte.
  if (event.data?.type === "PURGE_API_CACHE") {
    event.waitUntil(
      caches.keys().then((names) =>
        Promise.all(names.filter((n) => n.startsWith("ki-api")).map((n) => caches.delete(n))),
      ),
    );
  }
});

// Au changement de version, on retire les caches d'exécution devenus orphelins.
self.addEventListener("activate", (event) => {
  const keep = new Set([API_CACHE, ASSET_CACHE, cacheNames.precache, cacheNames.runtime]);
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n.startsWith("ki-") && !keep.has(n)).map((n) => caches.delete(n))),
    ),
  );
});

clientsClaim();
