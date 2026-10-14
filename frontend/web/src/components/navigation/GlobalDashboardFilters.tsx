import { useLocation } from "react-router-dom";

import { getModuleById, getModuleFromLegacyKey, getModuleFromPath } from "@/config/modules.config";
import { ChevronDown } from "@/components/overview/icons";
import { Menu, MenuItem } from "@/components/ui/Menu";
import { TOUTES_FILIALES, libelleFiltrePeriode, useFilters } from "@/store/filters";
import { PeriodePicker } from "@/components/navigation/PeriodePicker";
import { useHrDimensions } from "@/api/governance";
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
  const filtres = useFilters();
  return (
    <Menu align="left" width={280} trigger={FilterTrigger({ label: "Période", value: libelleFiltrePeriode(filtres) })}>
      {(close) => <PeriodePicker onChoisi={close} />}
    </Menu>
  );
}

/** Un filtre de dimension RÉEL : ses options sont les codes que l'historique a
 *  effectivement mesurés (`/governance/hr/dimensions/`), jamais une liste écrite
 *  ici. Un périmètre restreint reçoit une liste vide et le motif. */
function DimensionFilter({ label, options, courant, onChange, restriction, chargement }: {
  label: string;
  options: { code: string; libelle: string }[];
  courant: string;
  onChange: (code: string) => void;
  restriction?: string;
  chargement: boolean;
}) {
  const choisi = options.find((o) => o.code === courant);
  return (
    <Menu align="left" width={260} trigger={FilterTrigger({ label, value: choisi?.libelle ?? (courant ? courant : "Tous") })}>
      {(close) => (
        <div className="max-h-[320px] overflow-auto p-1">
          <MenuItem onClick={() => { onChange(""); close(); }}>
            <span style={!courant ? { fontWeight: 700, color: "#16191A" } : undefined}>Tous</span>
          </MenuItem>
          {chargement ? (
            <div className="px-3 py-2 text-[11px] font-semibold text-[#9AA09D]">Chargement…</div>
          ) : options.length ? (
            options.map((o) => (
              <MenuItem key={o.code} onClick={() => { onChange(o.code); close(); }}>
                <span style={o.code === courant ? { fontWeight: 700, color: "#16191A" } : undefined}>{o.libelle}</span>
              </MenuItem>
            ))
          ) : (
            <div className="px-3 py-2 text-[11px] font-medium leading-relaxed text-[#8A908D]">
              {restriction ?? "Aucune valeur mesurée pour l'instant : l'historique se constitue à chaque collecte."}
            </div>
          )}
        </div>
      )}
    </Menu>
  );
}

function FiltresDimensionsRh({ filtre }: { filtre: string }) {
  const { site, personnel, departement, setSite, setPersonnel, setDepartement } = useFilters();
  const { data, isLoading } = useHrDimensions();
  if (filtre === "Site") {
    return <DimensionFilter label="Site" options={data?.site ?? []} courant={site} onChange={setSite}
                            restriction={data?.restriction} chargement={isLoading} />;
  }
  if (filtre === "Personnel") {
    // Les deux types sont ceux de Shield (`holder_kind`) : ils existent même avant
    // la première collecte, ce sont des valeurs du modèle, pas des données.
    const types = [{ code: "employee", libelle: "Employés" }, { code: "worker", libelle: "Ouvriers" }];
    return <DimensionFilter label="Personnel" options={data?.restriction ? [] : types} courant={personnel}
                            onChange={(c) => setPersonnel(c as "" | "employee" | "worker")}
                            restriction={data?.restriction} chargement={false} />;
  }
  return <DimensionFilter label="Département" options={data?.departement ?? []} courant={departement}
                          onChange={setDepartement} restriction={data?.restriction} chargement={isLoading} />;
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
  Métier:
    "Les postes Odoo (hr.job) sont comptés mais pas encore ventilés : aucun historique par métier n'existe, ce filtre n'agirait sur rien.",
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
        ) : module.id === "capital-humain" && ["Site", "Personnel", "Département"].includes(filter) ? (
          <FiltresDimensionsRh key={filter} filtre={filter} />
        ) : (
          <FiltreIndisponible key={filter} label={filter} />
        ),
      )}
    </div>
  );
}
