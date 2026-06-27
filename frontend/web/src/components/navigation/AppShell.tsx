import type * as React from "react";

interface AppShellProps {
  children: React.ReactNode;
}

/** Point d'extension pour les futurs shells authentifiés multi-apps. */
export function AppShell({ children }: AppShellProps) {
  return <>{children}</>;
}
