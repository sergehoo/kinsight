/** Pose les tokens `--domain-*` sur <html> pour le domaine actif.
 *
 *  Les variables vivent au niveau racine (et non sur un conteneur de page) afin
 *  que l'en-tête, le rail, la sidebar et les panneaux flottants — qui ne sont pas
 *  tous dans le même sous-arbre — partagent le même accent. Le changement de
 *  valeur est interpolé par les `@property` déclarées dans index.css : la
 *  transition est donc gérée en CSS, sans re-render ni flash.
 */
import * as React from "react";

import { domainTokens } from "@/config/domainTheme";

export function useDomainTheme(moduleId: string | undefined): void {
  React.useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    const tokens = domainTokens(moduleId);
    for (const [name, value] of Object.entries(tokens)) {
      root.style.setProperty(name, value);
    }
  }, [moduleId]);
}
