import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppLayout } from "@/layouts/AppLayout";
import { HrDashboard } from "@/pages/HrDashboard";
import { GovernanceOverview } from "@/pages/GovernanceOverview";
import { ModulePage } from "@/pages/ModulePage";
import { ModulesHome } from "@/pages/ModulesHome";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 30_000 } },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Dashboard hero (governance) — sélection de filiale via l'URL */}
          <Route index element={<GovernanceOverview />} />
          <Route path="/d/:dashboard" element={<GovernanceOverview />} />

          {/* Accueil des modules + pages métiers/transverses */}
          <Route path="/dashboard" element={<ModulesHome />} />
          <Route path="/modules/:key" element={<ModulePage />} />

          {/* Vue RH détaillée historique (lecture seule) */}
          <Route element={<AppLayout />}>
            <Route path="/legacy/rh" element={<HrDashboard />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
