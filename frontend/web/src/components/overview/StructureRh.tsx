/** Structure des effectifs — Kaydan Shield, mesure du jour.
 *
 *  Une seule lecture (`/integrations/shield/structure/`, collecte partagée côté
 *  serveur) alimente KPI, graphiques, tableau et échéances. Les listes de filtres
 *  viennent des données LIVE : aucune catégorie (CDI, CDD, département…) n'est
 *  écrite ici. Une notion que Shield n'expose pas reste N/D avec le motif du
 *  serveur. Le périmètre est appliqué par le serveur (sociétés rattachées).
 */
import * as React from "react";

import { BreakdownChart, DonutChart } from "@/components/charts";
import { glass } from "@/components/chrome/theme";
import { MetricCard, ResponsiveGrid, StateBadge, type DataState } from "@/components/ui/kit";
import type { KBreakdownItem } from "@/lib/kmetric";
import { useShieldStructure, type LigneRepartition, type ShieldStructure } from "@/lib/shieldHr";

const SOURCE = "Kaydan Shield";
const ACCENT = "#416FF4";
const ORDRE_FILTRES = ["nature", "societe", "departement", "poste", "contrat", "statut", "site", "metier"] as const;
const LIBELLE_FILTRE: Record<string, string> = {
  nature: "Personnel", societe: "Société", departement: "Département", poste: "Poste",
  contrat: "Contrat", statut: "Statut", site: "Site", metier: "Métier",
};
const NOMBRE = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });

function items(lignes: LigneRepartition[] | undefined, max = 12): KBreakdownItem[] {
  return (lignes ?? []).slice(0, max).map((l) => ({ key: l.code, label: l.libelle, value: l.valeur }));
}

function fraicheur(p?: ShieldStructure): string | undefined {
  const age = p?.cache?.age_s;
  if (age === undefined || age === null) return p?.collecte_le ? `collecté ${new Date(p.collecte_le).toLocaleTimeString("fr-FR")}` : undefined;
  return age < 90 ? "collecté à l'instant" : `collecté il y a ${Math.round(age / 60)} min`;
}

function Carte({ titre, children }: { titre: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0 rounded-[26px] p-5" style={glass}>
      <p className="mb-2 text-[12.5px] font-bold text-[#2C3132]">{titre}</p>
      {children}
    </div>
  );
}

export function StructureRh() {
  const [filtres, setFiltres] = React.useState<Record<string, string>>({});
  const [notionTableau, setNotionTableau] = React.useState("departement");
  const q = useShieldStructure(filtres);
  const p = q.data?.payload;
  const etat: DataState = q.isLoading ? "connecting" : q.isError ? "error"
    : q.data?.stale ? "stale" : (p?.status ?? "disconnected");
  const e = p?.effectifs;
  const r = p?.repartitions ?? {};
  const motif = (notion: string) => p?.motifs?.[notion] ?? p?.restriction ?? p?.detail ?? "Non servi par Shield.";
  const etatGraphe = (notion: string): DataState => (r[notion]?.length ? etat : q.isLoading ? "connecting" : "disconnected");
  const contratMajoritaire = r.contrat?.[0];

  const cartes: Array<{ titre: string; valeur: number | null | undefined; unite?: string; note?: string; comparaison?: string }> = [
    { titre: "Effectif total", valeur: e?.total },
    { titre: "Employés", valeur: e?.employes },
    { titre: "Ouvriers", valeur: e?.ouvriers },
    { titre: "Actifs", valeur: e?.actifs, note: "Aucun statut « actif » renvoyé par Shield : actifs non identifiables." },
    { titre: "Départements", valeur: r.departement?.length ?? null, note: motif("departement") },
    { titre: "Postes", valeur: r.poste?.length ?? null, note: motif("poste") },
    { titre: "Contrat majoritaire", valeur: contratMajoritaire?.part ?? null, unite: "%",
      comparaison: contratMajoritaire ? `${contratMajoritaire.libelle} · ${contratMajoritaire.valeur} personnes` : undefined,
      note: motif("contrat") },
    { titre: "Contrats à échéance ≤ 30 j", valeur: p?.contrats?.par_horizon?.["30"] ?? null,
      note: p?.contrats_motif ?? undefined },
  ];
  const tableau = r[notionTableau] ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 rounded-[22px] px-5 py-3" style={{ ...glass, background: "rgba(255,255,255,0.6)" }}>
        <span className="text-[13px] font-semibold text-[#2C3132]">{SOURCE} · aujourd&apos;hui</span>
        <StateBadge state={etat} />
        {fraicheur(p) ? <span className="text-[11.5px] font-semibold text-[#8C9391]">{fraicheur(p)}</span> : null}
        {p?.tronque ? <span className="text-[11.5px] font-semibold text-[#8A6E36]">lecture tronquée (plafond de pages)</span> : null}
        {p?.restriction ? <span className="text-[11.5px] font-semibold text-[#8A6E36]">{p.restriction}</span> : null}
      </div>

      {/* Filtres : listes construites depuis les données Shield, pas en dur. */}
      {p?.filtres && Object.keys(p.filtres).length ? (
        <div className="flex flex-wrap items-end gap-3">
          {ORDRE_FILTRES.filter((n) => p.filtres[n]?.length).map((n) => (
            <label key={n} className="grid gap-1 text-[11px] font-bold text-[#586061]">
              {LIBELLE_FILTRE[n]}
              <select value={filtres[n] ?? ""} onChange={(ev) => setFiltres((f) => ({ ...f, [n]: ev.target.value }))}
                      className="max-w-[200px] rounded-lg border border-[#DDE2E0] bg-white px-2 py-1.5 text-[12.5px] font-semibold text-[#16191A]">
                <option value="">Tous</option>
                {p.filtres[n].map((o) => <option key={o.code} value={o.code}>{o.libelle}</option>)}
              </select>
            </label>
          ))}
          {Object.values(filtres).some(Boolean) ? (
            <button type="button" onClick={() => setFiltres({})}
                    className="rounded-full bg-white px-3 py-1.5 text-[12px] font-bold text-[#2C3132]">Réinitialiser</button>
          ) : null}
        </div>
      ) : null}

      <ResponsiveGrid min={220}>
        {cartes.map((c) => (
          <MetricCard key={c.titre} title={c.titre} value={c.valeur ?? null} unit={c.unite}
                      state={c.valeur !== null && c.valeur !== undefined ? etat : q.isLoading ? "connecting" : "disconnected"}
                      source={SOURCE} scope="Aujourd'hui" comparison={c.comparaison}
                      unavailableNote={c.valeur === null || c.valeur === undefined ? (e ? (c.note ?? motif("")) : motif("")) : undefined}
                      accent={ACCENT} />
        ))}
      </ResponsiveGrid>

      <div className="grid gap-5 xl:grid-cols-2">
        <Carte titre="Répartition par type de contrat">
          <DonutChart items={items(r.contrat)} state={etatGraphe("contrat")} source={SOURCE} height={260} emptyMessage={motif("contrat")} />
        </Carte>
        <Carte titre="Effectif par département">
          <BreakdownChart items={items(r.departement)} state={etatGraphe("departement")} source={SOURCE} emptyMessage={motif("departement")} />
        </Carte>
        <Carte titre="Effectif par poste (12 premiers)">
          <BreakdownChart items={items(r.poste)} state={etatGraphe("poste")} source={SOURCE} emptyMessage={motif("poste")} />
        </Carte>
        <Carte titre="Effectif par société">
          <BreakdownChart items={items(r.societe)} state={etatGraphe("societe")} source={SOURCE} emptyMessage={motif("societe")} />
        </Carte>
        <Carte titre="Statut du personnel">
          <DonutChart items={items(r.statut)} state={etatGraphe("statut")} source={SOURCE} height={240} emptyMessage={motif("statut")} />
        </Carte>
        <Carte titre="Genre">
          <DonutChart items={items(r.genre)} state={etatGraphe("genre")} source={SOURCE} height={240} emptyMessage={motif("genre")} />
        </Carte>
        <Carte titre="Tranches d'âge">
          <BreakdownChart items={items(r.tranche_age)} state={etatGraphe("tranche_age")} source={SOURCE} emptyMessage={motif("tranche_age")} />
        </Carte>
        <Carte titre="Ancienneté">
          <BreakdownChart items={items(r.tranche_anciennete)} state={etatGraphe("tranche_anciennete")} source={SOURCE} emptyMessage={motif("tranche_anciennete")} />
        </Carte>
        <Carte titre="Ouvriers par métier">
          <BreakdownChart items={items(r.metier)} state={etatGraphe("metier")} source={SOURCE} emptyMessage={motif("metier")} />
        </Carte>
        <Carte titre="Échéances de contrat">
          {p?.contrats ? (
            <div className="grid gap-3">
              <div className="grid grid-cols-3 gap-2">
                {Object.entries(p.contrats.par_horizon).map(([h, n]) => (
                  <div key={h} className="rounded-[16px] bg-white/70 px-3 py-2 text-center">
                    <div className="text-[20px] font-extrabold text-[#16191A]">{n}</div>
                    <div className="text-[11px] font-semibold text-[#7C8384]">≤ {h} jours</div>
                  </div>
                ))}
              </div>
              <p className="text-[11.5px] font-medium text-[#697071]">
                {p.contrats.echus} contrat(s) déjà échu(s) · {p.contrats.renseignes} date(s) de fin renseignée(s)
                {p.contrats.par_contrat.length ? ` · sous 90 j : ${p.contrats.par_contrat.map((c) => `${c.libelle} ${c.valeur}`).join(", ")}` : ""}
              </p>
            </div>
          ) : (
            <p className="text-[12px] font-medium leading-snug text-[#8A6E36]">{p?.contrats_motif ?? motif("")}</p>
          )}
        </Carte>
      </div>

      {/* Tableau : une ligne par catégorie ; un clic filtre tout l'écran sur elle. */}
      <div className="rounded-[26px] p-5" style={glass}>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-[12.5px] font-bold text-[#2C3132]">Répartition détaillée par</span>
          <select value={notionTableau} onChange={(ev) => setNotionTableau(ev.target.value)}
                  className="rounded-lg border border-[#DDE2E0] bg-white px-2 py-1 text-[12.5px] font-semibold">
            {Object.keys(r).map((n) => <option key={n} value={n}>{p?.libelles?.[n] ?? n}</option>)}
          </select>
        </div>
        {tableau.length ? (
          <table className="w-full text-left text-[12.5px]">
            <thead>
              <tr className="text-[11px] font-bold uppercase tracking-[0.08em] text-[#8A9291]">
                <th className="py-1.5">Catégorie</th><th className="py-1.5 text-right">Effectif</th><th className="py-1.5 text-right">Part</th>
              </tr>
            </thead>
            <tbody>
              {tableau.map((l) => (
                <tr key={l.code} className="border-t border-white/70">
                  <td className="py-1.5">
                    {(ORDRE_FILTRES as readonly string[]).includes(notionTableau) ? (
                      <button type="button" className="font-semibold text-[#185FA5] hover:underline"
                              onClick={() => setFiltres((f) => ({ ...f, [notionTableau]: l.code }))}>{l.libelle}</button>
                    ) : <span className="font-semibold">{l.libelle}</span>}
                  </td>
                  <td className="py-1.5 text-right font-bold">{NOMBRE.format(l.valeur)}</td>
                  <td className="py-1.5 text-right text-[#697071]">{l.part !== null ? `${NOMBRE.format(l.part)} %` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-[12px] font-medium text-[#8A6E36]">{motif(notionTableau)}</p>
        )}
      </div>
    </div>
  );
}
