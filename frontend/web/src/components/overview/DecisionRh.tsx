/** Aide à la décision RH : constats prioritaires, puis synthèse sur demande.
 *
 *  Les constats viennent du `HRDecisionEngine` (backend) : des règles écrites
 *  appliquées à l'historique réel, chacune avec sa valeur, sa comparaison, sa
 *  période, sa source, sa confiance, son exploration et une action recommandée.
 *  Trois à sept, par criticité — et jamais complétés pour faire le compte.
 *
 *  La synthèse est RÉDIGÉE par un modèle à partir de ces seuls constats, et
 *  seulement quand on la demande. Le serveur retire toute phrase portant un
 *  nombre absent des constats et marque les causes comme hypothèses ; l'écran
 *  dit qui a rédigé, et combien de phrases le garde-fou a écartées.
 */
import * as React from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { useHrDecision, useHrSynthese, type ConstatRh, type SectionSynthese } from "@/api/governance";
import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { parametresFiltres, useFilters } from "@/store/filters";

const SEVERITE: Record<ConstatRh["severite"], { libelle: string; couleur: string; fond: string }> = {
  critique: { libelle: "Critique", couleur: "#D92B55", fond: "rgba(217,43,85,0.10)" },
  surveillance: { libelle: "Surveillance", couleur: "#C77314", fond: "rgba(224,128,30,0.12)" },
  info: { libelle: "À noter", couleur: "#2D74E0", fond: "rgba(45,116,224,0.10)" },
};

const SECTIONS: Array<{ cle: SectionSynthese; titre: string }> = [
  { cle: "resume", titre: "Résumé exécutif" },
  { cle: "anomalies", titre: "Anomalies" },
  { cle: "hypotheses", titre: "Causes probables — hypothèses à vérifier" },
  { cle: "risques", titre: "Risques" },
  { cle: "recommandations", titre: "Recommandations" },
  { cle: "priorites", titre: "Priorités" },
  { cle: "questions", titre: "Questions à investiguer" },
];

function estRefus(erreur: unknown): boolean {
  return erreur instanceof Error && /Erreur API 403/.test(erreur.message);
}

function CarteConstat({ c, compact, index }: { c: ConstatRh; compact: boolean; index: number }) {
  const s = SEVERITE[c.severite];
  return (
    <motion.article
      className="rounded-[18px] bg-white/70 px-4 py-3"
      style={{ borderLeft: `3px solid ${s.couleur}` }}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 + index * 0.04, duration: 0.35, ease: EASE_OUT }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full px-2 py-0.5 text-[10.5px] font-bold" style={{ background: s.fond, color: s.couleur }}>
          {s.libelle}
        </span>
        <h4 className="text-[13.5px] font-semibold leading-snug text-[#16191A]">{c.titre}</h4>
      </div>
      <p className="mt-1.5 text-[12.5px] font-medium leading-relaxed text-[#3C4142]">{c.constat}</p>
      {c.action ? (
        <p className="mt-1.5 text-[12px] font-semibold leading-snug text-[#2C3132]">
          <span className="text-[#8A9291]">Action recommandée : </span>{c.action}
        </p>
      ) : null}
      {!compact && c.regle ? (
        <p className="mt-1 text-[11px] font-medium leading-snug text-[#9AA09D]">Règle : {c.regle}</p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10.5px] font-semibold text-[#8A9291]">
        <span>{[c.source, c.periode, c.confiance ? `confiance ${c.confiance}` : null].filter(Boolean).join(" · ")}</span>
        <Link to={c.lien} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-bold text-[#2C3132] hover:bg-[#F1F4F2]">
          Explorer →
        </Link>
      </div>
    </motion.article>
  );
}

/** Les constats seuls — version compacte pour la colonne de l'accueil. */
export function ConstatsRh({ compact = false }: { compact?: boolean }) {
  const filtres = useFilters();
  const { data, isLoading, isError, error } = useHrDecision(parametresFiltres(filtres).toString());

  return (
    <section className={compact ? "rounded-[22px] p-4 sm:p-5" : "rounded-[30px] p-6"}
             style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.84),rgba(243,248,249,0.55))" }}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className={compact ? "text-[12.5px] font-semibold text-[#586061]" : "text-[20px] font-semibold text-[#151818]"}>
          Aide à la décision
        </h3>
        {data ? (
          <span className="text-[11px] font-semibold text-[#9AA09D]">
            {data.constats.length} constat(s) · {data.periode.libelle}
          </span>
        ) : null}
      </div>
      <div className="mt-3 grid gap-2.5">
        {isLoading ? (
          <p className="text-[12px] font-semibold text-[#8A9291]">Analyse de la période…</p>
        ) : isError ? (
          <p className="text-[12px] font-semibold text-[#8A6E36]">
            {estRefus(error) ? "Accès non autorisé : l'aide à la décision RH relève du domaine Capital Humain."
              : "Analyse momentanément indisponible — aucune recommandation n'est produite sans données."}
          </p>
        ) : data?.constats.length ? (
          data.constats.map((c, i) => <CarteConstat key={c.id} c={c} compact={compact} index={i} />)
        ) : (
          <p className="text-[12px] font-medium leading-relaxed text-[#697071]">
            Rien à signaler sur la période : aucun seuil franchi, aucun écart notable.
            {data?.angles_morts.length
              ? ` ${data.angles_morts.length} signal(aux) restent non mesurés — ce silence ne couvre pas ce qu'on ne voit pas.`
              : ""}
          </p>
        )}
      </div>
    </section>
  );
}

/** Le panneau complet : constats, puis synthèse rédigée sur demande. */
export function DecisionRh() {
  const filtres = useFilters();
  const parametres = parametresFiltres(filtres).toString();
  const [demandee, setDemandee] = React.useState(false);
  // Changer de filtres repose la question : une synthèse vaut pour SA période.
  React.useEffect(() => setDemandee(false), [parametres]);
  const synthese = useHrSynthese(parametres, demandee);
  const s = synthese.data?.synthese;

  return (
    <div className="space-y-5">
      <ConstatsRh />
      <section className="rounded-[30px] p-6" style={{ ...glass, background: "rgba(255,255,255,0.62)" }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-[#8A9291]">Synthèse</p>
            <h3 className="mt-1 text-[20px] font-semibold text-[#151818]">Note de synthèse RH</h3>
            <p className="mt-1 max-w-[70ch] text-[12px] font-medium leading-relaxed text-[#697071]">
              Rédigée à partir des seuls constats ci-dessus. Toute phrase qui avancerait un chiffre absent des
              constats est retirée ; les causes sont des hypothèses à vérifier, pas des conclusions.
            </p>
          </div>
          <button type="button" onClick={() => setDemandee(true)} disabled={synthese.isFetching}
                  className="rounded-full bg-[#16191A] px-4 py-2 text-[12.5px] font-bold text-white disabled:opacity-50">
            {synthese.isFetching ? "Rédaction…" : s ? "Rédigée" : "Rédiger la synthèse"}
          </button>
        </div>

        {synthese.isError ? (
          <p className="mt-3 text-[12px] font-semibold text-[#8A6E36]">Synthèse indisponible pour le moment.</p>
        ) : s ? (
          <>
            <p className="mt-3 inline-flex flex-wrap items-center gap-2 rounded-full bg-[#F1F4F2] px-3 py-1 text-[11px] font-bold text-[#586061]">
              {s.ia ? `Rédigée par IA (${s.fournisseur})` : "Sans modèle disponible : composée des constats"}
              {s.phrases_retirees ? ` · ${s.phrases_retirees} phrase(s) retirée(s) par le garde-fou` : ""}
              {s.note ? ` · ${s.note}` : ""}
            </p>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              {SECTIONS.map(({ cle, titre }) => (
                <div key={cle} className="rounded-[18px] bg-white/65 p-4">
                  <h4 className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#8A9291]">{titre}</h4>
                  {s.sections[cle]?.length ? (
                    <ul className="mt-2 grid gap-1.5">
                      {s.sections[cle].map((phrase, i) => (
                        <li key={i} className="text-[12.5px] font-medium leading-relaxed text-[#2C3132]">{phrase}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-[12px] font-medium text-[#A0A6A3]">
                      {cle === "hypotheses" ? "Aucune hypothèse formulée." : "Rien à porter ici."}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
