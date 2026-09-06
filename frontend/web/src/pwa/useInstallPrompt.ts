/** Capture de `beforeinstallprompt` pour proposer l'installation au bon moment.
 *
 *  Le CTA n'apparaît que si le navigateur a réellement émis l'évènement : il reste
 *  donc invisible sur les navigateurs non compatibles (Safari, Firefox) et une fois
 *  l'application installée.
 */
import * as React from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISSED_KEY = "k-insight-install-dismissed";

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    // iOS Safari expose l'état installé hors media query.
    (window.navigator as { standalone?: boolean }).standalone === true
  );
}

export function useInstallPrompt() {
  const [event, setEvent] = React.useState<BeforeInstallPromptEvent | null>(null);
  const [installed, setInstalled] = React.useState(isStandalone);
  const [dismissed, setDismissed] = React.useState(() => {
    try {
      return window.localStorage.getItem(DISMISSED_KEY) === "1";
    } catch {
      return false;
    }
  });

  React.useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault(); // on choisit NOUS le moment de proposer
      setEvent(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setEvent(null);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const install = React.useCallback(async () => {
    if (!event) return;
    await event.prompt();
    const { outcome } = await event.userChoice;
    if (outcome === "accepted") setInstalled(true);
    setEvent(null);
  }, [event]);

  const dismiss = React.useCallback(() => {
    setDismissed(true);
    try {
      window.localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      /* stockage indisponible : on masque au moins pour cette session */
    }
  }, []);

  return { canInstall: Boolean(event) && !installed && !dismissed, installed, install, dismiss };
}
