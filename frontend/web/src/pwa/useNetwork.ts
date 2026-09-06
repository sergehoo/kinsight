/** État réseau global + reprise de synchronisation au retour en ligne. */
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";

export function useOnlineStatus(): boolean {
  const [online, setOnline] = React.useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine,
  );
  React.useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

/** Au retour du réseau, on réinterroge les données marquées périmées.
 *  Sans cela l'écran resterait sur la dernière donnée connue (datée). */
export function useResyncOnReconnect(): void {
  const queryClient = useQueryClient();
  React.useEffect(() => {
    const resync = () => {
      void queryClient.invalidateQueries();
    };
    window.addEventListener("online", resync);
    return () => window.removeEventListener("online", resync);
  }, [queryClient]);
}
