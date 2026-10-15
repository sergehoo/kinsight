/** Signaux RH : pilotage par exception sur la période filtrée.
 *
 *  Neuf règles de seuil évaluées par le serveur (`governance/signaux_rh.py`) sur
 *  l'historique réel, sous les filtres et le périmètre de l'utilisateur. Ce
 *  panneau n'évalue rien : il affiche l'état, la valeur, la règle, les seuils
 *  (et s'ils sont arbitrés ou par défaut), la comparaison, la source, la
 *  couverture et la confiance — tout ce qu'il faut pour vérifier un signal
 *  avant d'agir. Un signal sans mesure est « non mesuré », jamais « normal ».
 *
 *  Les seuils se règlent ici, par la DRH Groupe ou l'administration (le serveur
 *  en décide) ; les autres les lisent.
 */
import * as React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import {
  useHrSignals,
  useHrThresholds,
  useSaveHrThreshold,
  type EtatSignal,
  type SeuilRhLigne,
  type SeuilsSignal,
  type SignalRh,
} from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { parametresFiltres, useFilters } from "@/store/filters";

const NOMBRE = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 1 });
const fr = (n: number) => NOMBRE.format(n);

export const ETATS: Record<EtatSignal, { libelle: string; couleur: string; fond: string }> = {
  critique: { libelle: "Critique", couleur: "#D92B55", fond: "rgba(217,43,85,0.10)" },
  surveillance: { libelle: "Surveillance", couleur: "#C77314", fond: "rgba(224,128,30,0.12)" },
  normal: { libelle: "Normal", couleur: "#1E8A6E", fond: "rgba(66,191,160,0.14)" },
  non_mesure: { libelle: "Non mesuré", couleur: "#7B8484", fond: "rgba(123,132,132,0.12)" },
};

function estRefus(erreur: unknown): boolean {
  return erreur instanceof Error && /Erreur API 403/.test(erreur.message);
}

function PastilleEtat({ etat, n }: { etat: EtatSignal; n?: number }) {
  const e = ETATS[etat];
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold"
          style={{ background: e.fond, color: e.couleur }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: e.couleur }} />
      {n !== undefined ? `${n} ` : ""}{e.libelle}
    </span>
  );
}

/** « Surveillance < 85 % · critique < 70 % » — le sens dit lequel des deux côtés est mauvais. */
function texteSeuils(cle: string, s: SeuilsSignal): string {
  const op = s.sens === "bas" ? "<" : ">";
  const quoi = cle === "effectif_critique" ? "baisse " : "";
  return `Surveillance : ${quoi}${op} ${fr(s.surveillance)} % · critique : ${quoi}${op} ${fr(s.critique)} %`
    + (s.par_defaut ? " (seuils par défaut)" : " (seuils arbitrés)");
}

function valeurAffichee(sig: SignalRh): string | null {
  if (sig.valeur === null || sig.valeur === undefined) return null;
  if (sig.cle === "effectif_critique") {
    return sig.valeur >= 0 ? `Baisse de ${fr(sig.valeur)} %` : `Hausse de ${fr(-sig.valeur)} %`;
  }
  if (sig.cle === "site_sous_effectif" && sig.pire) return `${sig.pire.libelle} : ${fr(sig.pire.valeur)} %`;
  return `${fr(sig.valeur)} %`;
}

function texteComparaison(sig: SignalRh): { texte: string; favorable: boolean } | null {
  const c = sig.comparaison;
  if (!c || c.value === null || c.value === undefined) return null;
  if (sig.cle === "effectif_critique") {
    return { texte: `Effectif ${fr(sig.effectif ?? 0)} contre ${fr(c.value)} sur la période précédente`,
             favorable: (sig.valeur ?? 0) <= 0 };
  }
  if (c.ecart === null || c.ecart === undefined) return null;
  const sens = sig.seuils?.sens ?? "bas";
  const signe = c.ecart > 0 ? "+" : c.ecart < 0 ? "−" : "";
  return {
    texte: c.ecart === 0 ? "stable vs période préc." : `${signe}${fr(Math.abs(c.ecart))} pt${Math.abs(c.ecart) >= 2 ? "s" : ""} vs période préc.`,
    favorable: sens === "bas" ? c.ecart >= 0 : c.ecart <= 0,
  };
}

function LigneSignal({ sig, periode, index }: { sig: SignalRh; periode?: string; index: number }) {
  const e = ETATS[sig.etat];
  const valeur = valeurAffichee(sig);
  const comparaison = texteComparaison(sig);
  return (
    <motion.article
      className="rounded-[20px] bg-white/70 px-4 py-3.5"
      style={{ borderLeft: `3px solid ${e.couleur}` }}
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.05 + index * 0.03, duration: 0.35, ease: EASE_OUT }}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <PastilleEtat etat={sig.etat} />
            <h4 className="text-[14px] font-semibold text-[#16191A]">{sig.libelle}</h4>
          </div>
          <p className="mt-1 text-[11.5px] font-medium leading-snug text-[#7C8384]" title={sig.metric_id ?? undefined}>
            {sig.regle}
          </p>
        </div>
        {valeur ? (
          <div className="text-right">
            <div className="text-[18px] font-extrabold leading-tight" style={{ color: e.couleur }}>{valeur}</div>
            {comparaison ? (
              <div className="text-[11px] font-bold" style={{ color: comparaison.favorable ? "#1E8A6E" : "#C43252" }}>
                {comparaison.texte}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {sig.etat === "non_mesure" && sig.motif ? (
        <p className="mt-2 text-[12px] font-medium leading-snug text-[#8A6E36]">{sig.motif}</p>
      ) : null}

      {sig.details?.length ? (
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {sig.details.slice(0, 8).map((d) => (
            <li key={d.code} className="rounded-full px-2.5 py-0.5 text-[11px] font-bold"
                style={{ background: ETATS[d.etat].fond, color: ETATS[d.etat].couleur }}>
              {d.libelle} · {fr(d.valeur)} %
            </li>
          ))}
          {sig.details.length > 8 ? (
            <li className="px-1 text-[11px] font-bold text-[#8A9291]">+{sig.details.length - 8} site(s)</li>
          ) : null}
        </ul>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10.5px] font-semibold text-[#8A9291]">
        <span>
          {[sig.source, periode, sig.confiance && sig.couverture
            ? `confiance ${sig.confiance} (${sig.couverture.jours_mesures}/${sig.couverture.jours} j mesurés)`
            : sig.cle === "site_sous_effectif" && sig.sites_mesures ? `${sig.sites_mesures} site(s) mesuré(s)` : null]
            .filter(Boolean).join(" · ")}
          {sig.seuils ? <span className="block text-[#A0A6A3]">{texteSeuils(sig.cle, sig.seuils)}</span> : null}
        </span>
        <Link to={sig.lien} className="shrink-0 rounded-full bg-white px-2.5 py-1 text-[11px] font-bold text-[#2C3132] hover:bg-[#F1F4F2]">
          Voir le détail →
        </Link>
      </div>
    </motion.article>
  );
}

/* ── Réglage des seuils ────────────────────────────────────────────────── */

function LigneReglage({ ligne, modifiable }: { ligne: SeuilRhLigne; modifiable: boolean }) {
  const enregistrer = useSaveHrThreshold();
  const [surveillance, setSurveillance] = React.useState(String(ligne.surveillance));
  const [critique, setCritique] = React.useState(String(ligne.critique));
  React.useEffect(() => {
    setSurveillance(String(ligne.surveillance));
    setCritique(String(ligne.critique));
  }, [ligne.surveillance, ligne.critique]);
  const op = ligne.sens === "bas" ? "<" : ">";
  const modifie = Number(surveillance) !== ligne.surveillance || Number(critique) !== ligne.critique;

  return (
    <li className="rounded-[16px] bg-white/70 px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[13px] font-semibold text-[#1B1D1D]">{ligne.libelle}</span>
        <span className="text-[10.5px] font-semibold text-[#8A9291]">
          {ligne.par_defaut ? "Par défaut" : `Arbitré${ligne.modifie_par ? ` par ${ligne.modifie_par}` : ""}${
            ligne.modifie_le ? ` le ${new Date(ligne.modifie_le).toLocaleDateString("fr-FR")}` : ""}`}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        {([["Surveillance", surveillance, setSurveillance], ["Critique", critique, setCritique]] as const).map(
          ([libelle, valeur, changer]) => (
            <label key={libelle} className="grid gap-1 text-[11px] font-bold text-[#586061]">
              {libelle} ({op} %)
              <input type="number" min={0} max={100} step={0.5} value={valeur} disabled={!modifiable}
                     onChange={(ev) => changer(ev.target.value)}
                     className="w-24 rounded-lg border border-[#DDE2E0] bg-white px-2 py-1 text-[13px] font-semibold text-[#16191A] disabled:bg-[#F4F6F5]" />
            </label>
          ))}
        {modifiable ? (
          <>
            <button type="button" disabled={!modifie || enregistrer.isPending}
                    onClick={() => enregistrer.mutate({ signal: ligne.signal, surveillance: Number(surveillance), critique: Number(critique) })}
                    className="rounded-full bg-[#16191A] px-3.5 py-1.5 text-[12px] font-bold text-white disabled:opacity-40">
              Enregistrer
            </button>
            {!ligne.par_defaut ? (
              <button type="button" disabled={enregistrer.isPending}
                      onClick={() => enregistrer.mutate({ signal: ligne.signal, reinitialiser: true })}
                      className="rounded-full bg-white px-3.5 py-1.5 text-[12px] font-bold text-[#2C3132] disabled:opacity-40">
                Rétablir le défaut ({fr(ligne.defaut.surveillance)} / {fr(ligne.defaut.critique)})
              </button>
            ) : null}
          </>
        ) : null}
      </div>
      {enregistrer.isError ? (
        <p className="mt-1.5 text-[11.5px] font-semibold text-[#C43252]">{(enregistrer.error as Error).message}</p>
      ) : null}
    </li>
  );
}

function ReglageSeuils() {
  const { data, isLoading, isError } = useHrThresholds();
  if (isLoading) return <p className="text-[12px] font-semibold text-[#8A9291]">Chargement des seuils…</p>;
  if (isError || !data) return <p className="text-[12px] font-semibold text-[#C43252]">Seuils momentanément illisibles.</p>;
  return (
    <div className="mt-4 rounded-[20px] bg-white/45 p-4">
      <p className="text-[12px] font-medium leading-snug text-[#697071]">
        {data.modifiable
          ? "Les seuils valent pour tout le Groupe : ils jugent ces signaux, la carte de chaleur et les constats du jour. Chaque arbitrage est tracé (avant / après)."
          : "Lecture seule : seule la DRH Groupe ou l'administration arbitre ces seuils."}
      </p>
      <ul className="mt-3 grid gap-2.5 lg:grid-cols-2">
        {data.seuils.map((l) => <LigneReglage key={l.signal} ligne={l} modifiable={data.modifiable} />)}
      </ul>
    </div>
  );
}

/* ── Le panneau ────────────────────────────────────────────────────────── */

export function SignauxRh({ compact = false }: { compact?: boolean }) {
  const filtres = useFilters();
  const { data, isLoading, isError, error } = useHrSignals(parametresFiltres(filtres).toString());
  const [reglage, setReglage] = React.useState(false);

  const signaux = data?.signaux ?? [];
  const visibles = compact ? signaux.filter((s) => s.etat === "critique" || s.etat === "surveillance").slice(0, 3) : signaux;
  const compteurs = data?.compteurs;

  return (
    <motion.section
      className="rounded-[30px] p-6"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.84),rgba(243,248,249,0.55))" }}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: EASE_OUT }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8A9291]">Pilotage par exception</p>
          <h3 className="mt-1 text-[20px] font-semibold text-[#151818]">Signaux RH</h3>
          {data?.periode ? (
            <p className="mt-0.5 text-[12px] font-semibold text-[#8C9391]">{data.periode.libelle} · jusqu&apos;à la veille</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {compteurs
            ? (["critique", "surveillance", "normal", "non_mesure"] as const).map((e) => <PastilleEtat key={e} etat={e} n={compteurs[e]} />)
            : null}
          {compact ? (
            <Link to="/dashboard/capital-humain/alertes" className="rounded-full bg-white px-3 py-1 text-[11.5px] font-bold text-[#2C3132]">
              Centre d&apos;alertes →
            </Link>
          ) : data ? (
            <button type="button" onClick={() => setReglage((v) => !v)}
                    className="rounded-full bg-white px-3 py-1 text-[11.5px] font-bold text-[#2C3132]">
              {reglage ? "Fermer les seuils" : data.seuils_modifiables ? "Arbitrer les seuils" : "Voir les seuils"}
            </button>
          ) : null}
        </div>
      </div>

      {reglage && !compact ? <ReglageSeuils /> : null}

      <div className="mt-4 grid gap-2.5">
        {isLoading ? (
          <div className="rounded-xl bg-white/60 px-4 py-6 text-center text-[13px] font-semibold text-[#8A9291]">Évaluation des signaux…</div>
        ) : isError ? (
          <div className="rounded-xl bg-white/60 px-4 py-6 text-center text-[12.5px] font-semibold text-[#8A6E36]">
            {estRefus(error) ? "Accès non autorisé : les signaux RH relèvent du domaine Capital Humain."
              : (error as Error)?.message?.includes("Erreur API 4") ? "Filtres refusés par le serveur."
                : "Signaux momentanément indisponibles."}
          </div>
        ) : visibles.length ? (
          visibles.map((s, i) => <LigneSignal key={s.cle} sig={s} periode={data?.periode.libelle} index={i} />)
        ) : compact ? (
          <div className="rounded-xl bg-white/60 px-4 py-4 text-[12.5px] font-semibold text-[#586061]">
            Aucun signal en surveillance ni critique sur la période
            {compteurs?.non_mesure ? ` — ${compteurs.non_mesure} signal(s) non mesuré(s), voir le centre d'alertes.` : "."}
          </div>
        ) : null}
      </div>
    </motion.section>
  );
}
