/** Rapports Capital Humain : exporter maintenant, programmer un envoi.
 *
 *  Exporter : Excel (détail + synthèse), PDF (rapport exécutif), PowerPoint
 *  (présentation Direction) — sous les filtres COURANTS ; le serveur y applique
 *  le périmètre de l'utilisateur et trace l'extraction.
 *
 *  Programmer : fréquence, format, période relative, filtres, destinataires.
 *  Chaque destinataire reçoit le rapport sous SES droits ; seuls des
 *  utilisateurs ayant accès au Capital Humain peuvent être choisis. Le journal
 *  des envois dit ce qui est parti — et ce qui n'est pas parti, avec le motif.
 */
import * as React from "react";
import { motion } from "framer-motion";

import { downloadHrReport, useEcrireRapport, useRapportsProgrammes, type RapportProgramme } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { libelleFiltrePeriode, parametresFiltres, useFilters } from "@/store/filters";

const FORMATS = [
  { ext: "xlsx", libelle: "Excel", detail: "Données détaillées + synthèse, graphiques natifs" },
  { ext: "pdf", libelle: "PDF", detail: "Rapport exécutif" },
  { ext: "pptx", libelle: "PowerPoint", detail: "Présentation Direction" },
] as const;

const STATUT_COULEUR: Record<string, string> = { envoye: "#1E8A6E", echec: "#C43252", ignore: "#8A6E36" };

function date(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";
}

function Carte({ children, titre, sousTitre }: { children: React.ReactNode; titre: string; sousTitre?: string }) {
  return (
    <motion.section className="rounded-[28px] p-6" style={{ ...glass, background: "rgba(255,255,255,0.62)" }}
                    initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: EASE_OUT }}>
      <h3 className="text-[18px] font-semibold text-[#151818]">{titre}</h3>
      {sousTitre ? <p className="mt-1 text-[12.5px] font-medium leading-relaxed text-[#697071]">{sousTitre}</p> : null}
      <div className="mt-4">{children}</div>
    </motion.section>
  );
}

function ExporterMaintenant() {
  const filtres = useFilters();
  const [enCours, setEnCours] = React.useState<string | null>(null);
  const [echec, setEchec] = React.useState<string | null>(null);
  const exporter = async (ext: "xlsx" | "pdf" | "pptx") => {
    setEnCours(ext);
    setEchec(null);
    try {
      await downloadHrReport(ext, parametresFiltres(filtres).toString(), libelleFiltrePeriode(filtres));
    } catch (e) {
      setEchec(e instanceof Error && / 403 /.test(e.message) ? "Export non autorisé pour ces filtres." : "Export impossible pour le moment.");
    } finally {
      setEnCours(null);
    }
  };
  return (
    <Carte titre="Exporter maintenant"
           sousTitre={`Sous les filtres courants (${libelleFiltrePeriode(filtres)}) et votre périmètre. Chaque extraction est tracée.`}>
      <div className="grid gap-3 sm:grid-cols-3">
        {FORMATS.map((f) => (
          <button key={f.ext} type="button" disabled={enCours !== null} onClick={() => exporter(f.ext)}
                  className="rounded-[18px] bg-white/75 px-4 py-3 text-left transition hover:bg-white disabled:opacity-50">
            <div className="text-[14px] font-bold text-[#16191A]">{enCours === f.ext ? "Génération…" : f.libelle}</div>
            <div className="text-[11.5px] font-medium text-[#7C8384]">{f.detail}</div>
          </button>
        ))}
      </div>
      {echec ? <p role="alert" className="mt-2 text-[12px] font-semibold text-[#C43252]">{echec}</p> : null}
    </Carte>
  );
}

function LigneRapport({ r }: { r: RapportProgramme }) {
  const { modifier, supprimer, envoyer } = useEcrireRapport();
  const erreur = [modifier, supprimer, envoyer].find((m) => m.isError)?.error as Error | undefined;
  return (
    <li className="rounded-[18px] bg-white/70 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[14px] font-semibold text-[#16191A]">{r.nom}</div>
          <div className="text-[11.5px] font-medium text-[#7C8384]">
            {r.frequence_libelle} · {r.format.toUpperCase()} · {r.periode_libelle}
            {Object.entries(r.filtres).filter(([k]) => k !== "periode").map(([k, v]) => ` · ${k} ${v}`).join("")}
          </div>
          <div className="text-[11.5px] font-medium text-[#7C8384]">
            Destinataires : {r.destinataires.map((d) => d.nom).join(", ")} · par {r.auteur}
          </div>
          <div className="text-[11px] font-semibold text-[#9AA09D]">
            {r.actif ? `Prochain envoi : ${date(r.prochain_envoi)}` : "Suspendu"} · dernier : {date(r.dernier_envoi)}
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <button type="button" onClick={() => envoyer.mutate(r.id)} disabled={envoyer.isPending}
                  className="rounded-full bg-[#16191A] px-3 py-1 text-[11.5px] font-bold text-white disabled:opacity-50">
            {envoyer.isPending ? "Envoi…" : "Envoyer maintenant"}
          </button>
          <button type="button" onClick={() => modifier.mutate({ id: r.id, actif: !r.actif })}
                  className="rounded-full bg-white px-3 py-1 text-[11.5px] font-bold text-[#2C3132]">
            {r.actif ? "Suspendre" : "Réactiver"}
          </button>
          <button type="button" onClick={() => { if (window.confirm(`Supprimer « ${r.nom} » ?`)) supprimer.mutate(r.id); }}
                  className="rounded-full bg-white px-3 py-1 text-[11.5px] font-bold text-[#C43252]">
            Supprimer
          </button>
        </div>
      </div>
      {erreur ? <p className="mt-1 text-[11.5px] font-semibold text-[#C43252]">{erreur.message}</p> : null}
      {r.envois.length ? (
        <ul className="mt-2 grid gap-1">
          {r.envois.map((e, i) => (
            <li key={i} className="text-[11px] font-medium text-[#586061]">
              <span className="font-bold" style={{ color: STATUT_COULEUR[e.statut] }}>{e.statut_libelle}</span>
              {" "}· {e.destinataire} · {date(e.le)}{e.detail ? ` — ${e.detail}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Programmer({ periodes, possibles, pourAutrui, moi }: {
  periodes: Record<string, string>;
  possibles: { id: number; nom: string }[];
  pourAutrui: boolean;
  moi?: number;
}) {
  const filtres = useFilters();
  const { creer } = useEcrireRapport();
  const [nom, setNom] = React.useState("");
  const [frequence, setFrequence] = React.useState<RapportProgramme["frequence"]>("hebdomadaire");
  const [format, setFormat] = React.useState<RapportProgramme["format"]>("pdf");
  const [periode, setPeriode] = React.useState("30j");
  const [avecFiltres, setAvecFiltres] = React.useState(false);
  const [choisis, setChoisis] = React.useState<number[]>([]);

  const dimensions = Object.fromEntries(
    [...parametresFiltres(filtres).entries()].filter(([k]) => ["subsidiary", "site", "type", "departement"].includes(k)),
  );
  const soumettre = (ev: React.FormEvent) => {
    ev.preventDefault();
    creer.mutate(
      { nom, frequence, format, filtres: { periode, ...(avecFiltres ? dimensions : {}) },
        destinataires: pourAutrui ? choisis : moi ? [moi] : [] },
      { onSuccess: () => { setNom(""); setChoisis([]); } },
    );
  };
  const champ = "rounded-lg border border-[#DDE2E0] bg-white px-2.5 py-1.5 text-[13px] font-semibold text-[#16191A]";
  return (
    <form onSubmit={soumettre} className="mt-4 grid gap-3 rounded-[18px] bg-white/45 p-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="grid gap-1 text-[11.5px] font-bold text-[#586061]">Nom
          <input className={champ} value={nom} onChange={(e) => setNom(e.target.value)} placeholder="Ex. Hebdo présence DRH" required />
        </label>
        <label className="grid gap-1 text-[11.5px] font-bold text-[#586061]">Fréquence
          <select className={champ} value={frequence} onChange={(e) => setFrequence(e.target.value as RapportProgramme["frequence"])}>
            <option value="quotidien">Chaque jour (07:00)</option>
            <option value="hebdomadaire">Chaque lundi (07:00)</option>
            <option value="mensuel">Le 1er du mois (07:00)</option>
          </select>
        </label>
        <label className="grid gap-1 text-[11.5px] font-bold text-[#586061]">Format
          <select className={champ} value={format} onChange={(e) => setFormat(e.target.value as RapportProgramme["format"])}>
            {FORMATS.map((f) => <option key={f.ext} value={f.ext}>{f.libelle}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-[11.5px] font-bold text-[#586061]">Période (au moment de l&apos;envoi)
          <select className={champ} value={periode} onChange={(e) => setPeriode(e.target.value)}>
            {Object.entries(periodes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
      {Object.keys(dimensions).length ? (
        <label className="flex items-center gap-2 text-[12px] font-semibold text-[#3C4142]">
          <input type="checkbox" checked={avecFiltres} onChange={(e) => setAvecFiltres(e.target.checked)} />
          Reprendre les filtres courants : {Object.entries(dimensions).map(([k, v]) => `${k} ${v}`).join(", ")}
        </label>
      ) : null}
      {pourAutrui ? (
        <fieldset className="grid gap-1.5">
          <legend className="text-[11.5px] font-bold text-[#586061]">Destinataires (utilisateurs ayant accès au Capital Humain)</legend>
          {!possibles.length ? (
            <p className="text-[12px] font-medium text-[#8A6E36]">
              Aucun utilisateur ayant accès au Capital Humain n&apos;a d&apos;adresse e-mail renseignée : renseignez-la dans
              son compte pour pouvoir lui adresser un rapport.
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {possibles.map((u) => (
              <label key={u.id} className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 text-[12px] font-semibold text-[#2C3132]">
                <input type="checkbox" checked={choisis.includes(u.id)}
                       onChange={(e) => setChoisis((c) => (e.target.checked ? [...c, u.id] : c.filter((x) => x !== u.id)))} />
                {u.nom}
              </label>
            ))}
          </div>
        </fieldset>
      ) : (
        <p className="text-[12px] font-medium text-[#697071]">Destinataire : vous-même (la DRH Groupe peut programmer pour d&apos;autres).</p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={creer.isPending || (pourAutrui && !choisis.length)}
                className="rounded-full bg-[#16191A] px-4 py-2 text-[12.5px] font-bold text-white disabled:opacity-40">
          {creer.isPending ? "Programmation…" : "Programmer"}
        </button>
        {creer.isError ? <span className="text-[12px] font-semibold text-[#C43252]">{(creer.error as Error).message}</span> : null}
      </div>
    </form>
  );
}

export function RapportsRh() {
  const { data, isLoading, isError } = useRapportsProgrammes();
  const moi = data?.destinataires_possibles.length === 1 && !data.peut_programmer_pour_autrui
    ? data.destinataires_possibles[0].id : undefined;
  return (
    <div className="space-y-5">
      <ExporterMaintenant />
      <Carte titre="Rapports programmés"
             sousTitre="Envoyés par e-mail à 07:00. Chaque destinataire reçoit le rapport établi sous ses propres droits ; la période se résout au moment de l'envoi.">
        {isLoading ? (
          <p className="text-[12px] font-semibold text-[#8A9291]">Chargement…</p>
        ) : isError || !data ? (
          <p className="text-[12px] font-semibold text-[#8A6E36]">Programmations momentanément illisibles.</p>
        ) : (
          <>
            {!data.smtp_configure ? (
              <p className="mb-3 rounded-[14px] bg-[#FFF4E5] px-3 py-2 text-[12px] font-semibold text-[#8A5A12]">
                L&apos;envoi d&apos;e-mails n&apos;est pas configuré sur le serveur : les rapports programmés ne partiront pas, et
                chaque échéance sera journalisée « Non envoyé » jusqu&apos;à ce que le SMTP soit renseigné.
              </p>
            ) : null}
            {data.rapports.length ? (
              <ul className="grid gap-2.5">{data.rapports.map((r) => <LigneRapport key={r.id} r={r} />)}</ul>
            ) : (
              <p className="text-[12.5px] font-medium text-[#697071]">Aucun rapport programmé.</p>
            )}
            <Programmer periodes={data.periodes} possibles={data.destinataires_possibles}
                        pourAutrui={data.peut_programmer_pour_autrui} moi={moi} />
          </>
        )}
      </Carte>
    </div>
  );
}
