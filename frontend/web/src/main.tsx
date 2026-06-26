import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "./index.css";

const AppLayout = lazy(() => import("@/layouts/AppLayout").then((module) => ({ default: module.AppLayout })));
const GovernanceOverview = lazy(() => import("@/pages/GovernanceOverview").then((module) => ({ default: module.GovernanceOverview })));
const HrDashboard = lazy(() => import("@/pages/HrDashboard").then((module) => ({ default: module.HrDashboard })));
const ModulePage = lazy(() => import("@/pages/ModulePage").then((module) => ({ default: module.ModulePage })));
const ModulesHome = lazy(() => import("@/pages/ModulesHome").then((module) => ({ default: module.ModulesHome })));

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, staleTime: 30_000 } },
});

function RouteFallback() {
  return (
    <div className="grid min-h-screen place-items-center bg-[#B8B7B4] text-black">
      <div className="rounded-full border border-white/70 bg-white/65 px-5 py-3 text-[13px] font-bold shadow-[0_18px_42px_rgba(40,44,48,0.08)] backdrop-blur-2xl">
        Chargement du cockpit
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<RouteFallback />}>
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
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
