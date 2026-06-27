import type * as React from "react";

import { AICopilotPanel } from "@/components/copilot/AICopilotPanel";

interface AppShellProps {
  children: React.ReactNode;
}

/** Shell applicatif : enfants de route + Copilot IA accessible depuis toutes les pages. */
export function AppShell({ children }: AppShellProps) {
  return (
    <>
      {children}
      <AICopilotPanel />
    </>
  );
}
