/** Attendance & Presence — branchée sur Kaydan Shield, pas sur un mart absent.
 *
 *  CE QUE CETTE PAGE REMPLACE. Elle était rendue par `ModulePage`, c'est-à-dire
 *  par le catalogue statique de `lib/modules.tsx` : douze cartes à `value: "N/D"`
 *  écrites en dur, adossées à `mart.hr_attendance_kpi` — une table qui n'existe
 *  nulle part dans le dépôt (ni dbt, ni DDL, ni seed, ni source Airbyte). La page
 *  n'attendait donc pas une panne : elle attendait une source qui n'a jamais été
 *  modélisée, et rien n'aurait pu l'allumer.
 *
 *  Pendant ce temps, Shield sert la présence réelle depuis le backend. Les huit
 *  premiers indicateurs ci-dessous sont mesurés ou calculés à partir de mesures
 *  réelles ; la série journalière est réelle aussi, trous compris.
 *
 *  LES QUATRE INDICATEURS SANS SOURCE RESTENT AFFICHÉS. Départs anticipés, heures
 *  travaillées, heures supplémentaires et pointages RFID n'ont AUCUNE source
 *  aujourd'hui — ni chez Shield, ni au mart, ni chez Airbyte. Les retirer
 *  effacerait la question ; on les garde en `disconnected` avec leur motif, et le
 *  compteur « N/12 alimentés » rend l'écart lisible plutôt que muet. C'est le
 *  contraire d'une page vide : c'est une page qui dit ce qu'elle sait et ce
 *  qu'elle ne sait pas.
 *
 *  PÉRIMÈTRE. Les compteurs de Shield sont des agrégats Groupe : la source ne
 *  rattache pas ses sites aux filiales, donc rien ici n'est filtrable par
 *  filiale sans inventer ce rattachement — et le backend retire la répartition
 *  par site (et les alertes qui nomment un site) hors périmètre Groupe. La page
 *  le dit au lieu de le laisser deviner.
 */
import * as React from "react";

import { TrendChart } from "@/components/charts";
import { PageShell } from "@/components/chrome/PageShell";
import { glass } from "@/components/chrome/theme";
import { CheckCircle } from "@/components/overview/icons";
import {
  MetricCard,
  ResponsiveGrid,
  SignalCard,
  StateBadge,
  type DataState,
} from "@/components/ui/kit";
import { shieldSeriesHeadcount, shieldSeriesInsights, shieldSeriesPoints } from "@/lib/adapters/shield";
import {
  SERIES_WINDOWS,
  useShieldAttendanceSeries,
  useShieldHrKpis,
  type SeriesWindow,
  type ShieldHrQuery,
  type ShieldKpi,
  type ShieldSeriesQuery,
} from "@/lib/shieldHr";
import { useOnlineStatus } from "@/pwa/useNetwork";

const SOURCE = "Kaydan Shield";
const ACCENT = "#FF8735";

/** Les douze libellés de la page, et ce qui les alimente RÉELLEMENT.
 *
 *  `cle` renvoie à une clé servie par `/integrations/shield/hr-kpi/`. `motif`
 *  n'est renseigné que pour les indicateurs sans source : c'est la phrase que la
 *  carte affiche à la place d'un chiffre, et elle nomme la cause plutôt que de
 *  laisser croire à une panne passagère.
 */
const INDICATEURS: Array<{ titre: string; cle?: ShieldKpi["key"]; motif?: string }> = [
  { titre: "Présents", cle: "presents" },
  { titre: "Absents", cle: "absents" },
  { titre: "Retards", cle: "retards" },
  { titre: "Taux de présence", cle: "taux_presence" },
  { titre: "Taux d'absence du jour", cle: "taux_absence_jour" },
  { titre: "Taux de ponctualité", cle: "taux_ponctualite" },
  { titre: "Effectif total", cle: "effectif_total" },
  { titre: "Sites", cle: "sites" },
  {
    titre: "Départs anticipés",
    motif: "Aucune source : Shield ne compte que présents, absents et retards.",
  },
  {
    titre: "Heures travaillées",
    motif: "Aucune source : exigerait les pointages horaires (Odoo hr.attendance, non raccordé).",
  },
  {
    titre: "Heures supplémentaires",
    motif: "Aucune source : dépend des heures travaillées, elles-mêmes non collectées.",
  },
  {
    titre: "Pointages RFID",
    motif: "Source existante (événements d'accès) mais mesure non définie : un franchissement de porte n'est pas une déclaration de présence.",
  },
];

/** L'état d'une requête Shield, dit dans le vocabulaire gouverné du kit.
 *
 *  `stale` avant `payload.status` : une donnée servie par le cache hors ligne est
 *  réelle mais datée, et l'annoncer « connectée » serait la présenter comme
 *  fraîche.
 */
function etatDeLaRequete(
  requete: { isLoading: boolean; isError: boolean; data?: ShieldHrQuery | ShieldSeriesQuery },
  enLigne: boolean,
): DataState {
  if (requete.isLoading) return "connecting";
  if (requete.isError || !requete.data) return enLigne ? "error" : "offline";
  if (requete.data.stale) return "stale";
  return requete.data.payload.status;
}

function Bandeau({
  alimentes,
  total,
  etat,
  source,
  detail,
}: {
  alimentes: number;
  total: number;
  etat: DataState;
  source: string;
  detail?: string;
}) {
  return (
    <div className="rounded-[26px] px-6 py-5" style={{ ...glass, background: "rgba(255,255,255,0.54)" }}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-full bg-[#E8F5EF] text-[#1E9B69]">
          <CheckCircle width={18} height={18} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold text-[#171A1A]">Contrat de données gouverné</h3>
            <StateBadge state={etat} />
            <span className="rounded-full bg-[#F1F4F2] px-2.5 py-0.5 text-[11px] font-bold text-[#586061]">
              {alimentes}/{total} indicateurs alimentés
            </span>
          </div>
          {/* La phrase change à zéro : « les indicateurs alimentés viennent de
              Kaydan Shield » sous un compteur 0/12 se lit comme une promesse
              démentie deux lignes plus bas. C'est l'état de la production tant
              qu'aucun jeton Shield n'est déposé — donc la phrase la plus lue. */}
          <p className="mt-1.5 text-[13px] font-medium leading-relaxed text-[#697071]">
            {alimentes === 0 ? (
              <>
                Aucun indicateur n'est alimenté pour l'instant, et aucun chiffre n'est inventé pour
                combler le vide. La source <span className="font-bold text-[#252A2B]">{source}</span>{" "}
                doit être raccordée et testée dans le centre de connecteurs.
              </>
            ) : (
              <>
                Aucun chiffre n'est inventé. Les indicateurs alimentés viennent de{" "}
                <span className="font-bold text-[#252A2B]">{source}</span>, via le backend K-Insight —
                jamais de Shield en direct. Les autres restent sans valeur et disent pourquoi.
              </>
            )}
          </p>
          {detail ? (
            <p className="mt-1.5 text-[12.5px] font-semibold leading-relaxed text-[#8C6D1F]">{detail}</p>
          ) : null}
          <p className="mt-1.5 text-[11.5px] font-medium leading-relaxed text-[#8C9391]">
            Mesures agrégées au périmètre Groupe : la source ne rattache pas ses sites aux filiales, un
            filtrage par filiale serait une invention. Les filtres de la barre ci-dessus ne s'appliquent
            donc pas à ces indicateurs.
          </p>
        </div>
      </div>
    </div>
  );
}

export function AttendancePage() {
  const enLigne = useOnlineStatus();
  const [fenetre, setFenetre] = React.useState<SeriesWindow>(30);

  const kpis = useShieldHrKpis();
  const serie = useShieldAttendanceSeries(fenetre);

  const etatKpis = etatDeLaRequete(kpis, enLigne);
  const etatSerie = etatDeLaRequete(serie, enLigne);

  const parCle = React.useMemo(() => {
    const map = new Map<string, ShieldKpi>();
    for (const kpi of kpis.data?.payload.kpis ?? []) map.set(kpi.key, kpi);
    return map;
  }, [kpis.data]);

  // « Alimenté » veut dire : une valeur réellement obtenue. Une carte en attente
  // ou en erreur ne compte pas — sinon le compteur annoncerait une couverture
  // que la page n'a pas.
  const cartes = INDICATEURS.map((indicateur) => {
    const kpi = indicateur.cle ? parCle.get(indicateur.cle) : undefined;
    const etat: DataState = indicateur.cle
      ? etatKpis === "connecting"
        ? "connecting"
        : (kpi?.status ?? (etatKpis === "connected" ? "partial" : etatKpis))
      : "disconnected";
    return { ...indicateur, kpi, etat };
  });
  const alimentes = cartes.filter((c) => c.kpi?.value !== null && c.kpi?.value !== undefined
    && (c.etat === "connected" || c.etat === "stale")).length;

  const points = shieldSeriesPoints(serie.data);
  const effectifs = shieldSeriesHeadcount(serie.data);
  const constats = shieldSeriesInsights(serie.data);
  const joursMesures = serie.data?.payload.measured_days;
  const joursTotal = serie.data?.payload.points.length;

  return (
    <PageShell
      title="Attendance & Presence"
      subtitle="Présents, absents, retards et ponctualité, mesurés par Kaydan Shield (contrôle d'accès RFID)."
      icon={<CheckCircle width={22} height={22} />}
      accent={ACCENT}
    >
      <div className="space-y-8">
        <Bandeau
          alimentes={alimentes}
          total={INDICATEURS.length}
          etat={etatKpis}
          source={kpis.data?.payload.source ?? SOURCE}
          detail={kpis.data?.payload.detail}
        />

        <section>
          <h2 className="mb-3 text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
            Indicateurs du jour
          </h2>
          <ResponsiveGrid min={232}>
            {cartes.map((carte) => (
              <MetricCard
                key={carte.titre}
                title={carte.titre}
                value={carte.kpi?.value ?? null}
                unit={carte.kpi?.unit}
                state={carte.etat}
                // Pas de provenance ni de fraîcheur sur un indicateur sans source :
                // « à l'instant » sous une carte vide daterait une mesure qui n'existe
                // pas, et nommer une source serait pire encore.
                source={carte.motif ? undefined : (kpis.data?.payload.source ?? SOURCE)}
                updatedAt={carte.motif ? undefined : kpis.data?.payload.updated_at}
                scope={carte.motif ? undefined : "Périmètre Groupe"}
                unavailableNote={carte.motif}
                accent={ACCENT}
              />
            ))}
          </ResponsiveGrid>

          {/* La liste des motifs sous la grille a été retirée : chaque carte porte
              désormais le sien via `unavailableNote`, et le répéter en dessous
              faisait lire deux fois la même phrase. */}
        </section>

        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
                Évolution journalière
              </h2>
              {joursMesures !== undefined && joursTotal ? (
                <p className="mt-1 text-[12px] font-semibold text-[#8C9391]">
                  {joursMesures} jour(s) mesuré(s) sur {joursTotal}
                  {joursMesures < joursTotal
                    ? " — les jours non mesurés laissent un trou dans la courbe, ils ne sont pas comptés à zéro."
                    : ""}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-1.5 rounded-full p-1" style={glass}>
              {SERIES_WINDOWS.map((jours) => (
                <button
                  key={jours}
                  type="button"
                  onClick={() => setFenetre(jours)}
                  aria-pressed={fenetre === jours}
                  className="rounded-full px-3.5 py-1.5 text-[12px] font-bold transition-colors"
                  style={fenetre === jours ? { background: "#0B0B0C", color: "#fff" } : { color: "#52595A" }}
                >
                  {jours} jours
                </button>
              ))}
            </div>
          </div>

          {serie.data?.payload.detail ? (
            <p className="mb-3 text-[12.5px] font-semibold text-[#8C6D1F]">{serie.data.payload.detail}</p>
          ) : null}

          <div className="grid gap-5 xl:grid-cols-2">
            <div className="rounded-[26px] p-5" style={glass}>
              <TrendChart
                series={points}
                label="Taux de présence"
                unit="%"
                state={etatSerie}
                source={serie.data?.payload.source ?? SOURCE}
                emptyMessage="Aucun jour mesuré sur cette fenêtre."
              />
            </div>
            <div className="rounded-[26px] p-5" style={glass}>
              <TrendChart
                series={effectifs}
                label="Présents"
                state={etatSerie}
                source={serie.data?.payload.source ?? SOURCE}
                emptyMessage="Aucun jour mesuré sur cette fenêtre."
              />
            </div>
          </div>
        </section>

        {constats.length ? (
          <section>
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
              Constats
            </h2>
            <ResponsiveGrid min={300}>
              {constats.map((constat) => (
                <SignalCard
                  key={constat.id}
                  severity={constat.severity}
                  title={constat.title}
                  description={constat.finding}
                  source={constat.sourceLabel}
                  detectedAt={constat.detectedAt}
                  action={constat.action}
                />
              ))}
            </ResponsiveGrid>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}

export default AttendancePage;
