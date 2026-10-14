import * as React from "react";

import { BLACK, ORANGE } from "@/components/chrome/theme";
import { anneesDisponibles, hierIso, type ModePeriode, useFilters } from "@/store/filters";

/** LE sélecteur de période du cockpit.
 *
 *  Il en existait quatre copies (barre de filtres, accueil de domaine, vue
 *  gouvernance, tableau RH historique), chacune avec ses années écrites en dur
 *  et son propre libellé. Une seule subsiste : elle écrit dans le store que
 *  tous les écrans lisent, et c'est le backend qui en déduit les bornes. */
const FENETRES: Array<[ModePeriode, string]> = [["7j", "7 j"], ["30j", "30 j"], ["90j", "90 j"]];
const titre = "px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-[#8A908D]";
const actif = { background: ORANGE, color: "#fff" };
const actifNoir = { background: BLACK, color: "#fff" };
const repos = { background: "rgba(255,255,255,0.6)", color: "#2A2D2D" };

export function PeriodePicker({ onChoisi }: { onChoisi?: () => void }) {
  const { periode, year, quarter, dateFrom, dateTo, setPeriode, setYear, setQuarter, setDates } = useFilters();
  const [debut, setDebut] = React.useState(dateFrom);
  const [fin, setFin] = React.useState(dateTo);
  const hier = hierIso();
  const datesValides = Boolean(debut && fin && debut <= fin && fin <= hier);

  return (
    <div className="grid gap-2 p-1">
      <div>
        <div className={titre}>Fenêtre glissante</div>
        <div className="grid grid-cols-3 gap-1.5">
          {FENETRES.map(([mode, libelle]) => (
            <button key={mode} type="button" onClick={() => { setPeriode(mode); onChoisi?.(); }}
                    className="rounded-xl py-2 text-[13px] font-semibold" style={periode === mode ? actif : repos}>
              {libelle}
            </button>
          ))}
        </div>
      </div>
      <div>
        <div className={titre}>Trimestre</div>
        <div className="grid grid-cols-4 gap-1.5">
          {[1, 2, 3, 4].map((t) => (
            <button key={t} type="button" onClick={() => { setQuarter(t); onChoisi?.(); }}
                    className="rounded-xl py-2 text-[13px] font-semibold"
                    style={periode === "trimestre" && t === quarter ? actif : repos}>
              T{t}
            </button>
          ))}
        </div>
      </div>
      <div>
        <div className={titre}>Année</div>
        <div className="grid grid-cols-3 gap-1.5">
          {anneesDisponibles().map((a) => (
            <button key={a} type="button" onClick={() => setYear(a)}
                    className="rounded-xl py-2 text-[13px] font-semibold"
                    style={a === year ? actifNoir : repos}>
              {a}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => { setPeriode("annee"); onChoisi?.(); }}
                className="mt-1.5 w-full rounded-xl py-2 text-[12.5px] font-semibold"
                style={periode === "annee" ? actif : repos}>
          Toute l&apos;année {year}
        </button>
      </div>
      <div>
        <div className={titre}>Personnalisée</div>
        <div className="grid grid-cols-2 gap-1.5">
          <input type="date" value={debut} max={hier} onChange={(e) => setDebut(e.target.value)}
                 aria-label="Début de période" className="h-9 rounded-lg border border-[#DDE2E0] bg-white px-2 text-[12px]" />
          <input type="date" value={fin} max={hier} onChange={(e) => setFin(e.target.value)}
                 aria-label="Fin de période" className="h-9 rounded-lg border border-[#DDE2E0] bg-white px-2 text-[12px]" />
        </div>
        <button type="button" disabled={!datesValides}
                onClick={() => { setDates(debut, fin); onChoisi?.(); }}
                className="mt-1.5 w-full rounded-xl py-2 text-[12.5px] font-semibold disabled:opacity-40"
                style={periode === "personnalisee" ? actif : repos}>
          Appliquer
        </button>
        <p className="px-2 pt-1 text-[10.5px] font-medium leading-snug text-[#9AA09D]">
          Une période s&apos;arrête à la veille : la journée en cours reste live.
        </p>
      </div>
    </div>
  );
}
