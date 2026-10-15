/** Attendance & Presence — Kaydan Shield, live ET historisé.
 *
 *  DEUX TEMPS, DEUX BLOCS, ET LA PAGE LE DIT.
 *    - La PÉRIODE (filtres du cockpit : trimestre, année, 7/30/90 j, dates) vient
 *      de l'historique K-Insight : chaque journée close de Shield y est déposée
 *      chaque nuit. Le site et le type de personnel s'y appliquent ; la
 *      comparaison à la période précédente et à N-1 aussi.
 *    - AUJOURD'HUI est live : la journée n'est pas close, elle n'est pas encore
 *      dans l'historique. Ces cartes sont datées et ne suivent pas la période.
 *
 *  Une seule requête sert les deux (module `hr-attendance`, résolu par le
 *  registre canonique) ; les courbes et le classement des sites lisent
 *  l'historique ; les ventilations du jour et les constats, la charge Shield
 *  partagée. Aucun chiffre n'est inventé : un indicateur sans source reste N/D
 *  avec son motif, un jour non mesuré laisse un trou dans la courbe.
 *
 *  PÉRIMÈTRE. Shield ne rattache pas ses sites aux filiales : ses chiffres sont
 *  des chiffres Groupe. Un périmètre restreint, ou un filtre filiale, rend les
 *  cartes N/D avec ce motif — jamais le total Groupe sous l'étiquette filiale.
 */
import * as React from "react";

import { useHrHistory, useModuleData } from "@/api/governance";
import { BreakdownChart, ComparisonChart, TrendChart } from "@/components/charts";
import { PageShell } from "@/components/chrome/PageShell";
import { glass } from "@/components/chrome/theme";
import { CarteGraphe } from "@/components/overview/GraphesRh";
import { CheckCircle } from "@/components/overview/icons";
import { MetricCard, ResponsiveGrid, SignalCard, StateBadge, type DataState } from "@/components/ui/kit";
import { CHALEUR_SITES, PRESENTS_PAR_TYPE } from "@/config/graphesRh";
import { ecartAffiche } from "@/lib/ecarts";
import {
  shieldAttendanceRateBreakdown,
  shieldBreakdownStatus,
  shieldInsights,
  shieldPresenceBreakdown,
  shieldPresenceByKind,
} from "@/lib/adapters/shield";
import type { KBreakdownItem, KSeriesPoint } from "@/lib/kmetric";
import { useShieldHrKpis } from "@/lib/shieldHr";
import { useOnlineStatus } from "@/pwa/useNetwork";
import { libelleFiltrePeriode, parametresFiltres, useFilters } from "@/store/filters";
import type { ModuleDataValue } from "@/types/governance";

const SOURCE = "Kaydan Shield";
const ACCENT = "#FF8735";
const MODULE = "hr-attendance";

/** Cartes de PÉRIODE : ce que l'historique sait agréger (règle du registre). */
const CARTES_PERIODE: Array<{ libelle: string; titre: string; unite?: string }> = [
  { libelle: "Taux de présence", titre: "Taux de présence", unite: "%" },
  { libelle: "Présents", titre: "Présents · moyenne / jour" },
  { libelle: "Absents", titre: "Absents · moyenne / jour" },
  { libelle: "Retards", titre: "Retards · moyenne / jour" },
  { libelle: "Taux de ponctualité", titre: "Taux de ponctualité", unite: "%" },
  { libelle: "Taux d'absence", titre: "Taux d'absence", unite: "%" },
];

/** Cartes du JOUR : la mesure live, sous les mêmes filtres quand Shield le permet. */
const CARTES_JOUR: Array<{ libelle: string; titre: string; unite?: string }> = [
  { libelle: "Présents", titre: "Présents" },
  { libelle: "Absents", titre: "Absents" },
  { libelle: "Retards", titre: "Retards" },
  { libelle: "Taux de présence", titre: "Taux de présence", unite: "%" },
  { libelle: "Effectif total", titre: "Effectif déclaré" },
  { libelle: "Employés présents", titre: "Employés présents" },
  { libelle: "Ouvriers présents", titre: "Ouvriers présents" },
];

/** Sans source : déclarés pour que l'écart au cockpit cible reste lisible. */
const SANS_SOURCE = ["Taux d'absentéisme", "Heures travaillées", "Heures supplémentaires",
  "Départs anticipés", "Pointages RFID"];

function etatCarte(valeur: number | null | undefined, statut: string | undefined, chargement: boolean): DataState {
  if (chargement) return "connecting";
  if (valeur !== null && valeur !== undefined) return "connected";
  if (statut === "error") return "error";
  return "disconnected";
}

function nombre(v: number | null | undefined): number | null {
  if (v === null || v === undefined) return null;
  return Math.round(v * 10) / 10;
}

function jourCourt(iso: string): string {
  const [, m, j] = iso.split("-");
  return `${j}/${m}`;
}

function CarteDePeriode({ carte, valeur, chargement }: {
  carte: (typeof CARTES_PERIODE)[number];
  valeur?: ModuleDataValue;
  chargement: boolean;
}) {
  const ecart = valeur ? ecartAffiche(valeur.metric_id, valeur.precedente ?? undefined) : null;
  const couverture = valeur?.periode?.couverture;
  return (
    <MetricCard
      title={carte.titre}
      value={nombre(valeur?.value)}
      unit={carte.unite}
      state={etatCarte(valeur?.value, valeur?.status, chargement)}
      trend={ecart?.texte}
      trendUp={ecart?.favorable}
      comparison={couverture ? `${couverture.jours_mesures}/${couverture.jours} j mesurés` : undefined}
      source={valeur?.source_label}
      scope={valeur?.periode?.libelle}
      unavailableNote={valeur?.value === null || valeur?.value === undefined ? valeur?.reason : undefined}
      accent={ACCENT}
    />
  );
}

function CarteDuJour({ carte, valeur, chargement }: {
  carte: (typeof CARTES_JOUR)[number];
  valeur?: ModuleDataValue;
  chargement: boolean;
}) {
  const live = valeur?.aujourd_hui;
  return (
    <MetricCard
      title={carte.titre}
      value={nombre(live?.value)}
      unit={carte.unite}
      state={etatCarte(live?.value, live?.status, chargement)}
      source={valeur?.source_label}
      updatedAt={live?.as_of ?? undefined}
      scope="Aujourd'hui · live"
      unavailableNote={live?.value === null || live?.value === undefined ? (live?.reason ?? undefined) : undefined}
      accent={ACCENT}
    />
  );
}

export function AttendancePage() {
  const enLigne = useOnlineStatus();
  const filtres = useFilters();
  const parametres = parametresFiltres(filtres).toString();
  const sansDimension = parametresFiltres({ ...filtres, site: "", personnel: "", departement: "" }).toString();

  const module = useModuleData(MODULE, parametres);
  const valeurs = module.data?.values ?? {};
  const chargement = module.isLoading;

  // Courbes : l'historique, sous TOUS les filtres (site ou type compris).
  const taux = useHrHistory("hr.taux_presence_jour", parametres, "compare=n-1");
  const presents = useHrHistory("hr.presents_jour", parametres, "compare=aucune");
  const absents = useHrHistory("hr.absents_jour", parametres, "compare=aucune");
  const retards = useHrHistory("hr.retards_jour", parametres, "compare=aucune");
  // Classements : la période sans dimension, ventilée par site puis par type.
  const parSite = useHrHistory("hr.taux_presence_jour", sansDimension, "compare=aucune&ventilation=site");
  const parType = useHrHistory("hr.presents_jour", sansDimension, "compare=aucune&ventilation=type");

  // Le live par site / type et les constats du jour : la charge Shield partagée.
  const kpis = useShieldHrKpis();
  const constats = shieldInsights(kpis.data);
  const restrictionSite = kpis.data?.payload.by_site?.restriction;

  const etatSerie: DataState = taux.isLoading ? "connecting" : taux.isError ? (enLigne ? "error" : "offline")
    : taux.data?.status === "disconnected" ? "disconnected"
      : taux.data?.points.some((p) => p.value !== null) ? "connected" : "disconnected";
  const motifSerie = taux.data?.reason
    ?? (taux.data?.historique_depuis
      ? `Aucune journée mesurée sur la période ; l'historique commence le ${jourCourt(taux.data.historique_depuis)}.`
      : "Historique en cours de constitution : aucune journée encore collectée.");

  const pointsTaux: KSeriesPoint[] = (taux.data?.points ?? []).map((p) => ({ label: jourCourt(p.date), value: nombre(p.value) }));
  const absentsParJour = new Map((absents.data?.points ?? []).map((p) => [p.date, p.value]));
  const pointsPresents: KSeriesPoint[] = (presents.data?.points ?? []).map((p) => ({
    label: jourCourt(p.date), value: p.value, compare: absentsParJour.get(p.date) ?? null,
  }));
  const pointsRetards: KSeriesPoint[] = (retards.data?.points ?? []).map((p) => ({ label: jourCourt(p.date), value: p.value }));

  const classementSites: KBreakdownItem[] = (parSite.data?.ventilation ?? []).map((l) => ({
    key: l.code, label: l.libelle || l.code, value: nombre(l.value),
  }));
  const repartitionType: KBreakdownItem[] = (parType.data?.ventilation ?? []).map((l) => ({
    key: l.code, label: l.libelle || l.code, value: nombre(l.value),
  }));
  const n1 = taux.data?.comparaisons?.n_1;
  const ecartN1 = ecartAffiche("hr.taux_presence_jour", n1, "N-1");

  const alimentees = CARTES_PERIODE.filter((c) => valeurs[c.libelle]?.value !== null
    && valeurs[c.libelle]?.value !== undefined).length;
  const etatModule: DataState = module.isLoading ? "connecting" : module.isError ? (enLigne ? "error" : "offline")
    : alimentees ? (alimentees === CARTES_PERIODE.length ? "connected" : "partial") : "disconnected";

  return (
    <PageShell
      title="Attendance & Presence"
      subtitle="Présence, absences, retards et ponctualité mesurés par Kaydan Shield — sur la période choisie, et aujourd'hui en direct."
      icon={<CheckCircle width={22} height={22} />}
      accent={ACCENT}
    >
      <div className="space-y-8">
        <div className="rounded-[26px] px-6 py-5" style={{ ...glass, background: "rgba(255,255,255,0.54)" }}>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold text-[#171A1A]">Contrat de données gouverné</h3>
            <StateBadge state={etatModule} />
            <span className="rounded-full bg-[#F1F4F2] px-2.5 py-0.5 text-[11px] font-bold text-[#586061]">
              {alimentees}/{CARTES_PERIODE.length} indicateurs de période alimentés
            </span>
          </div>
          <p className="mt-1.5 text-[13px] font-medium leading-relaxed text-[#697071]">
            La période vient de l&apos;historique K-Insight, où chaque journée close de{" "}
            <span className="font-bold text-[#252A2B]">{SOURCE}</span> est déposée chaque nuit : la période, le site
            et le type de personnel s&apos;y appliquent. « Aujourd&apos;hui » est live et daté. Aucun chiffre n&apos;est
            inventé ; un indicateur sans source dit pourquoi.
          </p>
          <p className="mt-1.5 text-[11.5px] font-medium leading-relaxed text-[#8C9391]">
            Shield ne rattache pas ses sites aux filiales : ses chiffres sont des chiffres Groupe, et un filtre
            filiale rend ces indicateurs N/D plutôt que d&apos;y afficher le total Groupe.
          </p>
        </div>

        <section>
          <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
              Période — {module.data?.period?.label ?? libelleFiltrePeriode(filtres)}
            </h2>
            {module.data?.period ? (
              <span className="text-[11.5px] font-semibold text-[#9AA09D]">
                du {jourCourt(module.data.period.start)} au {jourCourt(module.data.period.end)} · jusqu&apos;à la veille
              </span>
            ) : null}
          </div>
          <ResponsiveGrid min={232}>
            {CARTES_PERIODE.map((carte) => (
              <CarteDePeriode key={carte.libelle} carte={carte} valeur={valeurs[carte.libelle]} chargement={chargement} />
            ))}
          </ResponsiveGrid>
        </section>

        <section>
          <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h2 className="text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
              Aujourd&apos;hui —{" "}
              {new Date().toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" })}
            </h2>
            <span className="text-[11.5px] font-semibold text-[#9AA09D]">
              live — la journée n&apos;est pas close, le filtre de période ne s&apos;y applique pas
            </span>
          </div>
          <ResponsiveGrid min={232}>
            {CARTES_JOUR.map((carte) => (
              <CarteDuJour key={carte.libelle} carte={carte} valeur={valeurs[carte.libelle]} chargement={chargement} />
            ))}
          </ResponsiveGrid>
        </section>

        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">Évolution sur la période</h2>
              {taux.data?.valeur ? (
                <p className="mt-1 text-[12px] font-semibold text-[#8C9391]">
                  {taux.data.valeur.couverture.jours_mesures} jour(s) mesuré(s) sur {taux.data.valeur.couverture.jours}
                  {taux.data.valeur.couverture.jours_mesures < taux.data.valeur.couverture.jours
                    ? " — un jour non mesuré laisse un trou, il n'est pas compté à zéro." : ""}
                </p>
              ) : null}
            </div>
            {ecartN1 ? (
              <span className="rounded-full px-3 py-1.5 text-[12px] font-bold" style={{ ...glass, color: ecartN1.favorable ? "#1E8A6E" : "#D92B55" }}>
                Taux de présence : {ecartN1.texte}
              </span>
            ) : null}
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            <div className="rounded-[26px] p-5" style={glass}>
              <TrendChart series={pointsTaux} label="Taux de présence" unit="%" state={etatSerie}
                          source={SOURCE} emptyMessage={motifSerie} />
            </div>
            <div className="rounded-[26px] p-5" style={glass}>
              <ComparisonChart series={pointsPresents} label="Présents" compareLabel="Absents" state={etatSerie}
                               source={SOURCE} emptyMessage={motifSerie} />
            </div>
            <div className="rounded-[26px] p-5 xl:col-span-2" style={glass}>
              <TrendChart series={pointsRetards} label="Retards" state={etatSerie}
                          source={SOURCE} emptyMessage={motifSerie} height={200} />
            </div>
          </div>
        </section>

        {/* Jour par jour : la carte de chaleur et la composition suivent les
            filtres ; quand un filtre les rend impossibles (croisement site × type
            non historisé, période > 92 j), le serveur dit pourquoi. */}
        <section>
          <h2 className="mb-3 text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
            Jour par jour
          </h2>
          <div className="grid gap-5 xl:grid-cols-2">
            <CarteGraphe g={CHALEUR_SITES} parametres={parametres} />
            <CarteGraphe g={PRESENTS_PAR_TYPE} parametres={parametres} index={1} large />
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">
            Sites et personnels sur la période
          </h2>
          <div className="grid gap-5 xl:grid-cols-2">
            <div className="rounded-[26px] p-5" style={glass}>
              <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">Taux de présence par site — du plus au moins performant</p>
              <BreakdownChart items={classementSites} unit="%"
                              state={parSite.isLoading ? "connecting" : classementSites.some((i) => i.value !== null) ? "connected" : "disconnected"}
                              source={SOURCE}
                              emptyMessage={parSite.data?.reason ?? "Aucun site mesuré sur la période."} />
            </div>
            <div className="rounded-[26px] p-5" style={glass}>
              <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">Présents par type · moyenne / jour</p>
              <BreakdownChart items={repartitionType}
                              state={parType.isLoading ? "connecting" : repartitionType.some((i) => i.value !== null) ? "connected" : "disconnected"}
                              source={SOURCE}
                              emptyMessage={parType.data?.reason ?? "Aucune ventilation par type mesurée sur la période."} />
            </div>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">Ventilation du jour</h2>
          <div className="grid gap-5 xl:grid-cols-3">
            <div className="rounded-[26px] p-5" style={glass}>
              <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">Présents par type</p>
              <BreakdownChart items={shieldPresenceByKind(kpis.data)}
                              state={kpis.data?.payload.by_kind?.status ?? (kpis.isLoading ? "connecting" : "disconnected")}
                              source={SOURCE} emptyMessage="Ventilation employés / ouvriers non servie aujourd'hui." />
            </div>
            <div className="rounded-[26px] p-5" style={glass}>
              <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">Présents par site</p>
              <BreakdownChart items={shieldPresenceBreakdown(kpis.data)} state={shieldBreakdownStatus(kpis.data)}
                              source={SOURCE} emptyMessage={restrictionSite ?? "Aucun site actif publié par la source."} />
            </div>
            <div className="rounded-[26px] p-5" style={glass}>
              <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">Taux de présence par site</p>
              <BreakdownChart items={shieldAttendanceRateBreakdown(kpis.data)} unit="%" state={shieldBreakdownStatus(kpis.data)}
                              source={SOURCE} emptyMessage={restrictionSite ?? "Aucun site actif publié par la source."} />
            </div>
          </div>
        </section>

        {constats.length ? (
          <section>
            <h2 className="mb-3 text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">Constats du jour</h2>
            <ResponsiveGrid min={300}>
              {constats.map((constat) => (
                <SignalCard key={constat.id} severity={constat.severity} title={constat.title}
                            description={constat.finding} source={constat.sourceLabel}
                            detectedAt={constat.detectedAt} action={constat.action} />
              ))}
            </ResponsiveGrid>
          </section>
        ) : null}

        <section>
          <h2 className="mb-3 text-[13px] font-bold uppercase tracking-[0.14em] text-[#8B9394]">Sans source aujourd&apos;hui</h2>
          <ResponsiveGrid min={232}>
            {SANS_SOURCE.map((libelle) => (
              <MetricCard key={libelle} title={libelle} value={null} state="disconnected"
                          unavailableNote={valeurs[libelle]?.reason ?? "Aucune source ne sert cet indicateur."} accent={ACCENT} />
            ))}
          </ResponsiveGrid>
        </section>
      </div>
    </PageShell>
  );
}

export default AttendancePage;
