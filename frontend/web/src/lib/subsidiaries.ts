/** Les filiales que l'utilisateur peut filtrer — depuis la base, jamais en dur.
 *
 *  `store/filters.ts` portait une constante de quatre entrées : la même liste
 *  pour tout le monde, sans référentiel. Un tel filtre ne peut ni suivre
 *  l'organisation réelle, ni respecter un périmètre — il proposait le Groupe
 *  entier à un directeur qui n'a droit qu'à sa filiale.
 *
 *  La borne est côté serveur (`/auth/subsidiaries/`), pas ici : ce module ne fait
 *  que lire ce que le serveur consent à nommer.
 */
import { useQuery } from "@tanstack/react-query";

import { apiGet, USE_MOCK } from "@/lib/api";

export interface Subsidiary {
  code: string;
  name: string;
  country?: string;
  currency?: string;
}

export interface SubsidiariesResponse {
  /** "GROUP", ou la liste des codes du périmètre de l'utilisateur. */
  scope: "GROUP" | string[];
  results: Subsidiary[];
}

export function useSubsidiaries() {
  return useQuery<SubsidiariesResponse>({
    queryKey: ["auth", "subsidiaries"],
    enabled: !USE_MOCK,
    queryFn: () => apiGet<SubsidiariesResponse>("/auth/subsidiaries/"),
    // Le référentiel des filiales ne bouge pas dans la journée : le relire à
    // chaque montage de la barre de filtres serait du bruit.
    staleTime: 30 * 60_000,
    retry: false,
  });
}

/** Le nom à afficher pour un code, sans jamais fabriquer de libellé.
 *
 *  Rend `undefined` quand le code n'est pas dans le périmètre servi : afficher le
 *  code brut à la place ferait apparaître à l'écran une entité que le serveur a
 *  précisément refusé de nommer.
 */
export function nomDeFiliale(reponse: SubsidiariesResponse | undefined, code: string): string | undefined {
  return reponse?.results.find((f) => f.code === code)?.name;
}
