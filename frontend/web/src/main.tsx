import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppShell } from "@/components/navigation/AppShell";
import "./index.css";

const AppLayout = lazy(() => import("@/layouts/AppLayout").then((module) => ({ default: module.AppLayout })));
const GovernanceOverview = lazy(() => import("@/pages/GovernanceOverview").then((module) => ({ default: module.GovernanceOverview })));
const HrDashboard = lazy(() => import("@/pages/HrDashboard").then((module) => ({ default: module.HrDashboard })));
const ModulePage = lazy(() => import("@/pages/ModulePage").then((module) => ({ default: module.ModulePage })));
const ModuleRouter = lazy(() => import("@/components/navigation/ModuleRouter").then((module) => ({ default: module.ModuleRouter })));
const ModuleHome = lazy(() => import("@/pages/ModuleHome").then((module) => ({ default: module.ModuleHome })));
const ModulesHome = lazy(() => import("@/pages/ModulesHome").then((module) => ({ default: module.ModulesHome })));
const IntegrationsList = lazy(() => import("@/pages/integrations/IntegrationsList").then((m) => ({ default: m.IntegrationsList })));
const IntegrationForm = lazy(() => import("@/pages/integrations/IntegrationForm").then((m) => ({ default: m.IntegrationForm })));
const IntegrationHealth = lazy(() => import("@/pages/integrations/IntegrationHealth").then((m) => ({ default: m.IntegrationHealth })));

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
        <AppShell>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              {/* Entrée racine : cockpit exécutif consolidé Groupe (Overview Groupe) */}
              <Route index element={<Navigate to="/dashboard/overview-groupe" replace />} />
              <Route path="/dashboard" element={<Navigate to="/dashboard/overview-groupe" replace />} />
              <Route path="/d/:dashboard" element={<GovernanceOverview />} />

              {/* Navigation modulaire canonique : /dashboard/:domaine[/:vue] */}
              <Route path="/dashboard/:moduleId" element={<ModuleHome />} />
              <Route path="/dashboard/:moduleId/:itemId" element={<ModuleRouter />} />
              <Route path="/modules/:key" element={<ModulePage />} />

              {/* Administration : Connecteurs & Intégrations */}
              <Route path="/admin/integrations" element={<IntegrationsList />} />
              <Route path="/admin/integrations/new" element={<IntegrationForm />} />
              <Route path="/admin/integrations/health" element={<IntegrationHealth />} />
              <Route path="/admin/integrations/:id" element={<IntegrationForm />} />

              {/* Vue RH détaillée historique (lecture seule) */}
              <Route element={<AppLayout />}>
                <Route path="/legacy/rh" element={<HrDashboard />} />
              </Route>

              <Route path="*" element={<Navigate to="/dashboard/overview-groupe" replace />} />
            </Routes>
          </Suspense>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
