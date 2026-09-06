/** Couche PWA : mise à jour contrôlée + invitation à installer.
 *
 *  Aucune mise à jour n'est appliquée sans accord (`registerType: "prompt"`,
 *  `skipWaiting: false`) : un rechargement surprise au milieu d'une lecture de
 *  tableau de bord serait inacceptable. L'ancrage est en bas à GAUCHE, le bas à
 *  droite étant occupé par le Copilot.
 */
import * as React from "react";
import { useRegisterSW } from "virtual:pwa-register/react";

import { useInstallPrompt } from "./useInstallPrompt";
import { useResyncOnReconnect } from "./useNetwork";

// Empilé sur écran étroit, en ligne dès qu'il y a la place : le texte ne se
// comprime plus en colonne de trois mots à côté des boutons.
const SHELL =
  "pointer-events-auto flex w-[min(420px,calc(100vw-2rem))] flex-col gap-3 rounded-[18px] border border-white/70 " +
  "bg-white/85 px-4 py-3 shadow-[0_20px_48px_rgba(36,38,38,0.18)] backdrop-blur-2xl sm:w-auto sm:flex-row sm:items-center";
const ROW = "flex min-w-0 flex-1 items-center gap-3";
const ACTIONS = "flex shrink-0 items-center gap-2 self-end sm:self-auto";

export function PwaLayer() {
  useResyncOnReconnect();
  const { canInstall, install, dismiss } = useInstallPrompt();
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      // Vérifie l'arrivée d'une nouvelle version toutes les heures, sans l'imposer.
      if (registration) window.setInterval(() => void registration.update(), 60 * 60 * 1000);
    },
  });

  const [updating, setUpdating] = React.useState(false);

  const applyUpdate = async () => {
    setUpdating(true);
    // `true` = recharge la page une fois le nouveau service worker actif.
    await updateServiceWorker(true);
  };

  if (!needRefresh && !canInstall) return null;

  return (
    <div
      className="pointer-events-none fixed bottom-0 left-0 z-[70] flex flex-col gap-2 p-4"
      style={{
        paddingBottom: "calc(1rem + env(safe-area-inset-bottom))",
        paddingLeft: "calc(1rem + env(safe-area-inset-left))",
      }}
    >
      {needRefresh ? (
        <div className={SHELL} role="status" aria-live="polite">
          <div className={ROW}>
            <span className="ki-accent-fill h-2 w-2 shrink-0 rounded-full" aria-hidden />
            <div className="min-w-0">
              <p className="text-[12.5px] font-bold leading-tight text-[#16191A]">Nouvelle version disponible</p>
              <p className="text-[11px] font-medium text-[#7C8384]">Rechargement contrôlé, aucune donnée perdue.</p>
            </div>
          </div>
          <div className={ACTIONS}>
          <button
            type="button"
            onClick={applyUpdate}
            disabled={updating}
            className="ki-accent-ring shrink-0 rounded-full bg-[#16191A] px-3.5 py-2 text-[11.5px] font-bold text-white transition-transform hover:-translate-y-0.5 disabled:opacity-60"
          >
            {updating ? "Mise à jour…" : "Mettre à jour"}
          </button>
          <button
            type="button"
            onClick={() => setNeedRefresh(false)}
            aria-label="Plus tard"
            className="ki-accent-ring grid h-8 w-8 shrink-0 place-items-center rounded-full text-[#7C8384] hover:bg-black/5"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
          </div>
        </div>
      ) : null}

      {canInstall && !needRefresh ? (
        <div className={SHELL} role="note">
          <div className={ROW}>
          <span className="ki-accent-bg ki-accent-icon grid h-8 w-8 shrink-0 place-items-center rounded-full" aria-hidden>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3v12" />
              <path d="m7 10 5 5 5-5" />
              <path d="M5 21h14" />
            </svg>
          </span>
          <div className="min-w-0">
            <p className="text-[12.5px] font-bold leading-tight text-[#16191A]">Installer K-Insight</p>
            <p className="text-[11px] font-medium text-[#7C8384]">Accès direct, plein écran, hors ligne.</p>
          </div>
          </div>
          <div className={ACTIONS}>
          <button
            type="button"
            onClick={() => void install()}
            className="ki-accent-ring shrink-0 rounded-full bg-[#16191A] px-3.5 py-2 text-[11.5px] font-bold text-white transition-transform hover:-translate-y-0.5"
          >
            Installer
          </button>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Ne plus proposer"
            className="ki-accent-ring grid h-8 w-8 shrink-0 place-items-center rounded-full text-[#7C8384] hover:bg-black/5"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
