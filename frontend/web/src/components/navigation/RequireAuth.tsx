import * as React from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { renouvelerSiProche } from "@/lib/api";
import { getStoredUser, isAuthenticated } from "@/lib/auth";
import { ecrireFiltresDansUrl, lireFiltresDepuisUrl, useFilters } from "@/store/filters";

/** Les écrans dont l'adresse porte les filtres : ceux qui affichent des données. */
const PAGES_FILTREES = /^\/(dashboard|modules|d)\//;

/** Garde de route : redirige vers /login si non authentifié (en conservant la cible).
 *
 *  Entretient aussi la session. Le renouvellement sur 401 suffit à ne plus
 *  déconnecter, mais il se paie d'un aller-retour visible : le premier écran
 *  ouvert après une nuit reste vide le temps qu'un appel échoue, se renouvelle
 *  et se rejoue. On anticipe donc au retour sur l'onglet, moment où l'accès a
 *  justement toutes les chances d'avoir expiré.
 */
export function RequireAuth() {
  const location = useLocation();
  const authentifie = isAuthenticated();

  // Hook AVANT tout retour conditionnel : l'ordre des hooks ne doit pas dépendre
  // de l'état d'authentification, sinon React casse à la déconnexion.
  React.useEffect(() => {
    if (!authentifie) return;
    void renouvelerSiProche();
    const auRetour = () => {
      if (document.visibilityState === "visible") void renouvelerSiProche();
    };
    document.addEventListener("visibilitychange", auRetour);
    window.addEventListener("focus", auRetour);
    return () => {
      document.removeEventListener("visibilitychange", auRetour);
      window.removeEventListener("focus", auRetour);
    };
  }, [authentifie]);

  // Filtres ↔ adresse. Lus UNE fois (lien partagé, rechargement), puis réécrits à
  // chaque changement de filtre ET de page : après une navigation, l'adresse doit
  // dire la vue filtrée qu'elle montre.
  React.useEffect(() => {
    lireFiltresDepuisUrl();
  }, []);
  React.useEffect(() => {
    if (!PAGES_FILTREES.test(location.pathname)) return undefined;
    ecrireFiltresDansUrl(useFilters.getState());
    return useFilters.subscribe((etat) => ecrireFiltresDansUrl(etat));
  }, [location.pathname]);

  if (!authentifie) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <Outlet />;
}

/** Entrée racine authentifiée : redirige vers la page d'atterrissage du rôle. */
export function RootRedirect() {
  const user = getStoredUser();
  return <Navigate to={user?.landing || "/dashboard/overview-groupe"} replace />;
}
