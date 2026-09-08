import { useLocation } from "react-router-dom";

import { getModuleById, getModuleFromLegacyKey, getModuleFromPath } from "@/config/modules.config";
import { ChevronDown } from "@/components/overview/icons";
import { Menu, MenuItem } from "@/components/ui/Menu";
import { BLACK, ORANGE } from "@/components/chrome/theme";
import { TOUTES_FILIALES, libellePeriode, useFilters } from "@/store/filters";
import { useSubsidiaries } from "@/lib/subsidiaries";
import { useNavigationStore } from "@/state/navigationStore";

const pill =
  "flex h-10 items-center gap-2 rounded-full border border-white/70 bg-white/62 px-4 text-[12px] font-bold text-[#586061] shadow-sm backdrop-blur-xl transition-transform hover:-translate-y-0.5";

function FilterTrigger({ label, value }: { label: string; value?: string }) {
  return ({ open, toggle }: { open: boolean; toggle: () => void }) => (
    <button type="button" onClick={toggle} aria-haspopup="menu" aria-expanded={open} className={pill}>
      {label}
      {value ? <span className="text-[#16191A]">· {value}</span> : null}
      <ChevronDown width={14} height={14} style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }} />
    </button>
  );
}

function PeriodFilter() {
  const { year, quarter, setYear, setQuarter } = useFilters();
  return (
    <Menu align="left" width={240} trigger={FilterTrigger({ label: "Période", value: libellePeriode(year, quarter) })}>
      {() => (
        <div className="p-1">
          <div className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-[#8A908D]">Trimestre</div>
          <div className="mb-2 grid grid-cols-4 gap-1.5">
            {[1, 2, 3, 4].map((q) => (
              <button key={q} type="button" onClick={() => setQuarter(q)} className="rounded-xl py-2 text-[13px] font-semibold" style={q === quarter ? { background: ORANGE, color: "#fff" } : { background: "rgba(255,255,255,0.6)", color: "#2A2D2D" }}>T{q}</button>
            ))}
          </div>
          <div className="px-2 pb-1.5 text-[11px] font-bold uppercase tracking-wider text-[#8A908D]">Année</div>
          <div className="grid grid-cols-3 gap-1.5">
            {[2024, 2025, 2026].map((y) => (
              <button key={y} type="button" onClick={() => setYear(y)} className="rounded-xl py-2 text-[13px] font-semibold" style={y === year ? { background: BLACK, color: "#fff" } : { background: "rgba(255,255,255,0.6)", color: "#2A2D2D" }}>{y}</button>
            ))}
          </div>
        </div>
      )}
    </Menu>
  );
}

function SubsidiaryFilter() {
  const { subsidiary, setSubsidiary } = useFilters();
  const { data, isLoading, isError } = useSubsidiaries();

  // « Toutes » ne veut pas dire « toutes celles du Groupe » : le périmètre serveur
  // borne la réponse de toute façon. Pour un directeur de filiale, c'est « tout
  // mon périmètre » — et sa liste ne contient que la sienne.
  const options = [
    { code: TOUTES_FILIALES, name: "Toutes les filiales" },
    ...(data?.results ?? []),
  ];
  const courante = options.find((o) => o.code === subsidiary) ?? options[0];

  return (
    <Menu align="left" width={240} trigger={FilterTrigger({ label: "Filiale", value: courante.name })}>
      {(close) => (
        <div className="p-1">
          {isLoading ? (
            <div className="px-3 py-2 text-[11px] font-semibold text-[#9AA09D]">Chargement du référentiel…</div>
          ) : isError ? (
            /* On ne retombe PAS sur une liste codée en dur : proposer des filiales
               que le serveur n'a pas confirmées reviendrait à inventer le
               référentiel, et à en proposer hors périmètre. */
            <div className="px-3 py-2 text-[11px] font-semibold leading-relaxed text-[#A32D2D]">
              Référentiel des filiales injoignable. Le périmètre reste celui du serveur ;
              aucune liste n'est fabriquée localement.
            </div>
          ) : (
            options.map((o) => (
              <MenuItem key={o.code} onClick={() => { setSubsidiary(o.code); close(); }}>
                <span style={o.code === subsidiary ? { fontWeight: 700, color: "#16191A" } : undefined}>{o.name}</span>
              </MenuItem>
            ))
          )}
          {data && !isError ? (
            <div className="px-3 pt-1.5 text-[10.5px] font-semibold text-[#9AA09D]">
              {data.scope === "GROUP"
                ? "Périmètre Groupe — toutes les filiales actives."
                : `Périmètre restreint : ${data.results.length} filiale(s).`}
            </div>
          ) : null}
        </div>
      )}
    </Menu>
  );
}

/** Pourquoi une dimension n'est pas filtrable, dimension par dimension.
 *
 *  Le composant précédent offrait pour chacune un menu dont la seule option était
 *  « Tous », suivie de « Options à connecter au Data Warehouse ». Deux problèmes :
 *  l'option « Tous » se cliquait et ne faisait rien — un contrôle qui ne fait rien
 *  affirme une capacité inexistante —, et le motif était faux. Ce n'est pas
 *  l'entrepôt qui manque : Département et Métier sont des référentiels ODOO, dont
 *  le connecteur est inerte (aucun transport, `apps/integrations/odoo.py`) ; Site
 *  existe bien chez Shield, mais l'endpoint qui alimente les compteurs du jour
 *  (`/attendance/summary/today/`) n'accepte AUCUN filtre.
 *
 *  Nommer la cause exacte vaut mieux que promettre un branchement imminent.
 */
const MOTIFS: Record<string, string> = {
  Département:
    "Référentiel Odoo (hr.department) : le connecteur Odoo n'a pas de couche de transport, aucune donnée n'en sort.",
  Métier:
    "Référentiel Odoo (hr.job) : même connecteur, même absence de transport.",
  Site:
    "Les sites existent chez Kaydan Shield, mais les compteurs du jour proviennent d'un endpoint sans filtre. La répartition par site est servie telle quelle, sur la page Présence.",
  Collaborateur:
    "Recherche nominative : donnée à caractère personnel. L'accès (qui peut chercher qui, et sur quelle mesure) se décide avant l'implémentation.",
};

function FiltreIndisponible({ label }: { label: string }) {
  const motif = MOTIFS[label] ?? "Source non raccordée : ce filtre n'agirait sur aucune donnée.";
  return (
    <Menu align="left" width={280} trigger={FilterTrigger({ label, value: "indisponible" })}>
      {() => (
        <div className="p-1">
          <div className="px-3 py-2 text-[11.5px] font-semibold leading-relaxed text-[#586061]">
            Ce filtre n'est pas actif.
          </div>
          <div className="px-3 pb-2 text-[11px] font-medium leading-relaxed text-[#8A908D]">{motif}</div>
        </div>
      )}
    </Menu>
  );
}

export function GlobalDashboardFilters() {
  const { pathname } = useLocation();
  const { selectedModuleId } = useNavigationStore();
  const legacyKey = pathname.startsWith("/modules/") ? pathname.split("/").at(-1) : undefined;
  const module = getModuleFromPath(pathname) ?? getModuleFromLegacyKey(legacyKey) ?? getModuleById(selectedModuleId);
  if (!module) return null;
  const filters = module.filters ?? ["Période", "Filiale", "Département", "Site"];

  return (
    <div className="mt-6 flex flex-wrap items-center gap-2">
      <span className="rounded-full bg-black px-4 py-2 text-[12px] font-bold text-white shadow-[0_12px_24px_rgba(0,0,0,0.12)]">{module.label}</span>
      {filters.map((filter) =>
        filter === "Période" ? (
          <PeriodFilter key={filter} />
        ) : filter === "Filiale" ? (
          <SubsidiaryFilter key={filter} />
        ) : (
          <FiltreIndisponible key={filter} label={filter} />
        ),
      )}
    </div>
  );
}
