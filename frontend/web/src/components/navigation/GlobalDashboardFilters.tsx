import { useLocation } from "react-router-dom";

import { getModuleById, getModuleFromLegacyKey, getModuleFromPath } from "@/config/modules.config";
import { ChevronDown } from "@/components/overview/icons";
import { Menu, MenuItem } from "@/components/ui/Menu";
import { BLACK, ORANGE } from "@/components/chrome/theme";
import { SUBSIDIARIES, useFilters } from "@/store/filters";
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
    <Menu align="left" width={240} trigger={FilterTrigger({ label: "Période", value: `T${quarter} ${year}` })}>
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
  const current = SUBSIDIARIES.find((s) => s.code === subsidiary) ?? SUBSIDIARIES[0];
  return (
    <Menu align="left" width={220} trigger={FilterTrigger({ label: "Filiale", value: current.label })}>
      {(close) => (
        <div className="p-1">
          {SUBSIDIARIES.map((s) => (
            <MenuItem key={s.code} onClick={() => { setSubsidiary(s.code); close(); }}>
              <span style={s.code === subsidiary ? { fontWeight: 700, color: "#16191A" } : undefined}>{s.label}</span>
            </MenuItem>
          ))}
        </div>
      )}
    </Menu>
  );
}

function GenericFilter({ label }: { label: string }) {
  return (
    <Menu align="left" width={220} trigger={FilterTrigger({ label, value: "Tous" })}>
      {(close) => (
        <div className="p-1">
          <MenuItem onClick={close}><span className="font-bold text-[#16191A]">Tous</span></MenuItem>
          <div className="px-3 py-2 text-[11px] font-semibold text-[#9AA09D]">Options « {label} » à connecter au Data Warehouse</div>
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
          <GenericFilter key={filter} label={filter} />
        ),
      )}
    </div>
  );
}
