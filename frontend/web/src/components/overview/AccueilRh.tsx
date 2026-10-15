/** Accueil Capital Humain : les sections décisionnelles, sur données réelles.
 *
 *  A. Effectifs      — Shield (déclarés) et Odoo (référentiel, départements)
 *  B. Présence       — période (historique) et aujourd'hui (live), sites, types
 *  C. Structure      — ce qu'Odoo sert (départements, postes) ; le reste N/D motivé
 *  D. Mouvements     — N/D motivé : les dates d'entrée et de sortie ne sont pas lues
 *  E. Coûts          — N/D motivé : la paie n'est pas installée dans Odoo
 *
 *  Tout chiffre vient du registre canonique (même identifiant, même nombre que sur
 *  les autres écrans) ou de l'historique ; tout manque dit sa cause. Les filtres
 *  du cockpit s'appliquent : la période et le site/type aux mesures Shield, la
 *  filiale au périmètre — et une mesure qui ne peut pas les suivre le dit.
 */
import * as React from "react";
import { Link } from "react-router-dom";

import { useHrHistory, useModuleData } from "@/api/governance";
import { BreakdownChart, TrendChart } from "@/components/charts";
import { glass } from "@/components/chrome/theme";
import { MetricCard, ResponsiveGrid, StateBadge, type DataState } from "@/components/ui/kit";
import { ecartAffiche } from "@/lib/ecarts";
import type { KBreakdownItem, KSeriesPoint } from "@/lib/kmetric";
import { useOdooHrKpis } from "@/lib/odooHr";
import { parametresFiltres, useFilters } from "@/store/filters";
import type { ModuleDataValue } from "@/types/governance";

const ACCENT = "#416FF4";

function nombre(v: number | null | undefined): number | null {
  return v === null || v === undefined ? null : Math.round(v * 10) / 10;
}

function etat(v: number | null | undefined, chargement: boolean, statut?: string): DataState {
  if (chargement) return "connecting";
  if (v !== null && v !== undefined) return "connected";
  return statut === "error" ? "error" : "disconnected";
}

function jourCourt(iso: string): string {
  const [, m, j] = iso.split("-");
  return `${j}/${m}`;
}

/** Carte de la PÉRIODE (historique), avec son écart et sa couverture. */
function CartePeriode({ titre, v, unite, chargement }: { titre: string; v?: ModuleDataValue; unite?: string; chargement: boolean }) {
  const ecart = v ? ecartAffiche(v.metric_id, v.precedente ?? undefined) : null;
  return (
    <MetricCard
      title={titre} value={nombre(v?.value)} unit={unite}
      state={etat(v?.value, chargement, v?.status)}
      trend={ecart?.texte} trendUp={ecart?.favorable}
      source={v?.source_label} scope={v?.periode?.libelle}
      unavailableNote={v?.value === null || v?.value === undefined ? v?.reason : undefined}
      accent={ACCENT}
    />
  );
}

/** Carte du JOUR (live), datée et marquée comme telle. */
function CarteDuJour({ titre, v, unite, chargement }: { titre: string; v?: ModuleDataValue; unite?: string; chargement: boolean }) {
  const live = v?.aujourd_hui;
  return (
    <MetricCard
      title={titre} value={nombre(live?.value)} unit={unite}
      state={etat(live?.value, chargement, live?.status)}
      source={v?.source_label} scope="Aujourd'hui · live" updatedAt={live?.as_of ?? undefined}
      unavailableNote={live?.value === null || live?.value === undefined ? (live?.reason ?? v?.reason) : undefined}
      accent={ACCENT}
    />
  );
}

/** Carte SANS SOURCE : le motif du registre, tel quel. */
function CarteSansSource({ titre, v, motif }: { titre: string; v?: ModuleDataValue; motif?: string }) {
  return (
    <MetricCard title={titre} value={null} state="disconnected"
                unavailableNote={v?.reason ?? motif ?? "Aucune source ne sert cet indicateur."} accent={ACCENT} />
  );
}

function Section({ lettre, titre, sousTitre, etatSection, children }: {
  lettre: string; titre: string; sousTitre: string; etatSection?: DataState; children: React.ReactNode;
}) {
  return (
    <section className="rounded-[28px] p-5 sm:p-6" style={{ ...glass, background: "rgba(246,248,246,0.6)" }}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-full text-[12px] font-bold text-white" style={{ background: ACCENT }}>
          {lettre}
        </span>
        <h2 className="text-[16px] font-semibold text-[#202020]">{titre}</h2>
        {etatSection ? <StateBadge state={etatSection} /> : null}
        <p className="w-full text-[11.5px] font-medium text-[#8C9391] sm:ml-9 sm:w-auto">{sousTitre}</p>
      </div>
      {children}
    </section>
  );
}

export function AccueilRh() {
  const filtres = useFilters();
  const parametres = parametresFiltres(filtres).toString();
  const sansDimension = parametresFiltres({ ...filtres, site: "", personnel: "", departement: "" }).toString();

  const executif = useModuleData("hr-executive", parametres);
  const presence = useModuleData("hr-attendance", parametres);
  const ex = executif.data?.values ?? {};
  const pr = presence.data?.values ?? {};
  const chargeEx = executif.isLoading;
  const chargePr = presence.isLoading;

  const tendance = useHrHistory("hr.taux_presence_jour", parametres, "compare=n-1");
  const sites = useHrHistory("hr.taux_presence_jour", sansDimension, "compare=aucune&ventilation=site");
  const odoo = useOdooHrKpis();

  const pointsTendance: KSeriesPoint[] = (tendance.data?.points ?? []).map((p) => ({
    label: jourCourt(p.date), value: nombre(p.value),
  }));
  const tendanceMesuree = pointsTendance.some((p) => p.value !== null);
  const ecartN1 = ecartAffiche("hr.taux_presence_jour", tendance.data?.comparaisons?.n_1, "N-1");

  const classes = (sites.data?.ventilation ?? []).filter((l) => l.value !== null);
  const meilleurs = classes.slice(0, 3);
  const moinsBons = classes.length > 3 ? classes.slice(-3).reverse() : [];

  const departements: KBreakdownItem[] = (odoo.data?.by_department?.rows ?? []).map((r) => ({
    key: r.department, label: r.department, value: r.headcount,
  }));
  const motifOdoo = odoo.data?.restriction ?? odoo.data?.by_department?.detail ?? odoo.data?.detail
    ?? (odoo.isError ? "Odoo injoignable depuis le serveur." : undefined);

  return (
    <div className="flex flex-col gap-6">
      <Section lettre="A" titre="Effectifs" sousTitre="Déclarés dans Shield aujourd'hui · référentiel Odoo">
        <ResponsiveGrid min={210}>
          <CarteDuJour titre="Effectif total" v={ex["Effectif total"]} chargement={chargeEx} />
          <CarteDuJour titre="Employés" v={ex["Employés"]} chargement={chargeEx} />
          <CarteDuJour titre="Ouvriers" v={ex["Ouvriers"]} chargement={chargeEx} />
          <CartePeriode titre="Effectif · variation période" v={ex["Effectif total"]} chargement={chargeEx} />
          <CarteDuJour titre="Employés actifs (Odoo)" v={ex["Employés actifs"]} chargement={chargeEx} />
          <CarteDuJour titre="Sites déclarés" v={ex["Sites"]} chargement={chargeEx} />
        </ResponsiveGrid>
        <div className="mt-4 rounded-[22px] bg-white/55 p-4">
          <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">Effectif actif par département · Odoo</p>
          <BreakdownChart items={departements} source="Odoo RH"
                          state={odoo.isLoading ? "connecting" : departements.length ? "connected" : "disconnected"}
                          emptyMessage={motifOdoo ?? "Aucun département servi par Odoo."} />
        </div>
      </Section>

      <Section lettre="B" titre="Présence" sousTitre="Période filtrée (historique) · aujourd'hui (live) · Kaydan Shield"
               etatSection={tendanceMesuree ? "connected" : tendance.isLoading ? "connecting" : "disconnected"}>
        <ResponsiveGrid min={210}>
          <CartePeriode titre="Taux de présence" unite="%" v={pr["Taux de présence"]} chargement={chargePr} />
          <CartePeriode titre="Présents · moy./jour" v={pr["Présents"]} chargement={chargePr} />
          <CartePeriode titre="Absents · moy./jour" v={pr["Absents"]} chargement={chargePr} />
          <CartePeriode titre="Retards · moy./jour" v={pr["Retards"]} chargement={chargePr} />
          <CarteDuJour titre="Employés présents" v={pr["Employés présents"]} chargement={chargePr} />
          <CarteDuJour titre="Ouvriers présents" v={pr["Ouvriers présents"]} chargement={chargePr} />
        </ResponsiveGrid>
        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="rounded-[22px] bg-white/55 p-4">
            <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[12.5px] font-bold text-[#2C3132]">Tendance du taux de présence</p>
              {ecartN1 ? (
                <span className="text-[11.5px] font-bold" style={{ color: ecartN1.favorable ? "#1E8A6E" : "#D92B55" }}>
                  {ecartN1.texte}
                </span>
              ) : null}
            </div>
            <TrendChart series={pointsTendance} label="Taux de présence" unit="%" source="Kaydan Shield" height={200}
                        state={tendance.isLoading ? "connecting" : tendanceMesuree ? "connected" : "disconnected"}
                        emptyMessage={tendance.data?.reason ?? "Historique en cours de constitution."} />
          </div>
          <div className="rounded-[22px] bg-white/55 p-4">
            <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">Sites sur la période</p>
            {classes.length ? (
              <div className="grid gap-3 text-[12.5px]">
                <div>
                  <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.08em] text-[#1E8A6E]">Les plus présents</p>
                  {meilleurs.map((l) => (
                    <div key={l.code} className="flex justify-between gap-3"><span className="truncate">{l.libelle || l.code}</span>
                      <span className="font-bold">{new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(l.value as number)} %</span></div>
                  ))}
                </div>
                {moinsBons.length ? (
                  <div>
                    <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.08em] text-[#D92B55]">Les moins présents</p>
                    {moinsBons.map((l) => (
                      <div key={l.code} className="flex justify-between gap-3"><span className="truncate">{l.libelle || l.code}</span>
                        <span className="font-bold">{new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 }).format(l.value as number)} %</span></div>
                    ))}
                  </div>
                ) : null}
                <Link to="/dashboard/capital-humain/presence" className="text-[11.5px] font-bold text-[#416FF4]">Détail par site →</Link>
              </div>
            ) : (
              <p className="text-[12px] font-medium leading-relaxed text-[#8C9391]">
                {sites.data?.reason ?? "Aucun site mesuré sur la période."}
              </p>
            )}
          </div>
        </div>
      </Section>

      <Section lettre="C" titre="Structure des effectifs" sousTitre="Référentiel Odoo">
        <ResponsiveGrid min={210}>
          <CarteDuJour titre="Départements" v={ex["Départements"]} chargement={chargeEx} />
          <CarteDuJour titre="Postes à pourvoir" v={ex["Postes à pourvoir"]} chargement={chargeEx} />
          <CarteSansSource titre="Âge et ancienneté" motif="Dates de naissance et d'entrée non lues dans Odoo : la pyramide n'est pas calculable." />
          <CarteSansSource titre="Répartition par sexe" motif="Le champ « genre » d'Odoo n'est pas encore lu." />
          <CarteSansSource titre="Contrats" motif="Les contrats (hr.contract) ne sont encore que comptés, pas ventilés par type." />
          <CarteSansSource titre="Métiers" motif="Les postes Odoo (hr.job) ne sont pas encore ventilés par métier." />
        </ResponsiveGrid>
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section lettre="D" titre="Mouvements" sousTitre="Entrées, départs, turnover">
          <ResponsiveGrid min={200}>
            <CarteSansSource titre="Recrutements" v={ex["Nouveaux employés"]} />
            <CarteSansSource titre="Départs" v={ex["Départs"]} />
            <CarteSansSource titre="Turnover" v={ex["Turnover"]} />
            <CarteSansSource titre="Promotions et mobilités" motif="Aucun historique de carrière n'est lu dans Odoo." />
          </ResponsiveGrid>
        </Section>
        <Section lettre="E" titre="Coûts" sousTitre="Masse salariale et heures">
          <ResponsiveGrid min={200}>
            <CarteSansSource titre="Masse salariale" v={ex["Masse salariale"]} />
            <CarteSansSource titre="Coût moyen par employé" motif="Dépend de la masse salariale, sans source aujourd'hui." />
            <CarteSansSource titre="Heures supplémentaires" v={ex["Heures supplémentaires"]} />
          </ResponsiveGrid>
        </Section>
      </div>
    </div>
  );
}
