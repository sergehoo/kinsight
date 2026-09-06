import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Proxy /api OPTIONNEL : activé seulement si VITE_API_PROXY_TARGET est défini.
  // Permet de travailler en same-origin comme en production (pas de CORS, et le
  // service worker peut alors mettre en cache les réponses métier).
  const proxy = env.VITE_API_PROXY_TARGET
    ? { "/api": { target: env.VITE_API_PROXY_TARGET, changeOrigin: true } }
    : undefined;

  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        // `injectManifest` : le service worker est écrit à la main (src/sw.ts) car la
        // règle « ne jamais servir une donnée de cache comme fraîche » demande un
        // plugin Workbox sur mesure, impossible à exprimer en configuration générée.
        strategies: "injectManifest",
        srcDir: "src",
        filename: "sw.ts",
        registerType: "prompt", // jamais de rechargement surprise : l'utilisateur décide
        injectRegister: null, // l'enregistrement est piloté par src/pwa/PwaLayer.tsx
        includeAssets: ["icons/apple-touch-icon.png", "icons/favicon-32.png"],
        manifest: {
          name: "K-Insight",
          short_name: "K-Insight",
          description: "Gouvernance & Intelligence — Groupe Kaydan",
          lang: "fr",
          dir: "ltr",
          start_url: "/",
          scope: "/",
          display: "standalone",
          orientation: "any",
          theme_color: "#0B0B0C",
          background_color: "#F7F8F9",
          categories: ["business", "productivity"],
          icons: [
            { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
            { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
            { src: "/icons/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
            { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
          ],
        },
        injectManifest: {
          globPatterns: ["**/*.{js,css,html,woff2}"],
          maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
        },
        devOptions: { enabled: false },
      }),
    ],
    resolve: {
      alias: { "@": path.resolve(process.cwd(), "src") },
    },
    server: { port: 5173, host: true, proxy },
    preview: { port: 5173, proxy },
  };
});
