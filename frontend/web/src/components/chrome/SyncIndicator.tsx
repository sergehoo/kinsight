/** Indicateur global de synchronisation des sources (header).
 *
 *  Reflète l'état RÉEL du control-plane d'intégration : aucune source déclarée →
 *  « Non connecté », toutes connectées → « Connecté », sinon « Partiel ».
 *  Aucune donnée métier n'est affichée ici, uniquement l'état des connecteurs.
 */
import { Link } from "react-router-dom";

import { ApiError, useHealth } from "@/lib/integrations";
import { STATE_META, useRelativeTime, type DataState } from "@/components/ui/kit";
import { useOnlineStatus } from "@/pwa/useNetwork";

export function SyncIndicator() {
  const { data, isLoading, isError, error, dataUpdatedAt } = useHealth();
  const online = useOnlineStatus();

  // TOUS les hooks sont appelés avant le moindre retour anticipé. Une version
  // précédente sortait entre deux hooks : React comptait alors moins de hooks au
  // second rendu qu'au premier et levait « Rendered fewer hooks than expected »,
  // ce qui blanchissait la page entière au lieu de masquer un badge.
  const relative = useRelativeTime(dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : undefined);

  // `/integrations/sources/health/` est réservé aux administrateurs d'intégration
  // (IsIntegrationAdmin). Pour un DG, un DAF ou un RH, l'appel renvoie 403 : afficher
  // « Indisponible » laisserait croire à une panne des sources alors qu'il s'agit
  // d'une absence de droit. Dans ce cas l'indicateur se retire simplement.
  const forbidden = error instanceof ApiError && (error.status === 403 || error.status === 401);
  if (forbidden && online) return null;

  let state: DataState = "disconnected";
  let detail = "Aucune source déclarée";

  // L'absence de réseau prime : inutile d'accuser les sources d'être en erreur.
  if (!online) {
    state = "offline";
    detail = "Réseau indisponible — données non rafraîchies";
  } else if (isLoading) {
    state = "connecting";
    detail = "Lecture du control-plane…";
  } else if (isError || !data) {
    state = "error";
    detail = "Control-plane injoignable";
  } else if (data.active === 0) {
    state = "disconnected";
    detail = "Aucune source active";
  } else if (data.error > 0 && data.connected === 0) {
    state = "error";
    detail = `${data.error} source(s) en erreur`;
  } else if (data.connected === data.active) {
    state = "connected";
    detail = `${data.connected}/${data.active} sources connectées`;
  } else if (data.connected > 0) {
    state = "partial";
    detail = `${data.connected}/${data.active} sources connectées`;
  } else {
    state = "disconnected";
    detail = `0/${data.active} source connectée`;
  }

  const meta = STATE_META[state];
  const title = relative ? `${detail} · vérifié ${relative}` : detail;

  return (
    <Link
      to="/admin/integrations"
      title={title}
      aria-label={`Synchronisation des sources : ${meta.label}. ${detail}.`}
      className={`min-h-[44px] items-center gap-2 rounded-full px-3 transition-colors hover:bg-white/70 ${
        state === "offline" ? "inline-flex" : "hidden xl:inline-flex"
      }`}
      style={{ background: meta.bg }}
    >
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${state === "connecting" ? "ki-sync-dot" : ""}`}
        style={{ background: meta.color }}
      />
      <span className="text-[11.5px] font-bold leading-none" style={{ color: meta.color }}>
        {meta.label}
      </span>
      {data && !isLoading && !isError ? (
        <span className="text-[11px] font-semibold leading-none text-[#7C8384]">
          {data.connected}/{data.active}
        </span>
      ) : null}
    </Link>
  );
}
