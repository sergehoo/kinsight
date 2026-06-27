import { Navigate, Outlet, useLocation } from "react-router-dom";

import { getStoredUser, isAuthenticated } from "@/lib/auth";

/** Garde de route : redirige vers /login si non authentifié (en conservant la cible). */
export function RequireAuth() {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <Outlet />;
}

/** Entrée racine authentifiée : redirige vers la page d'atterrissage du rôle. */
export function RootRedirect() {
  const user = getStoredUser();
  return <Navigate to={user?.landing || "/dashboard/overview-groupe"} replace />;
}
