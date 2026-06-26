import { useLocation, useNavigate, useParams } from "react-router-dom";

import { Building, Help, Logout, Users, Wallet } from "@/components/overview/icons";
import { MODULES } from "@/lib/modules";

import { CircleButton } from "./CircleButton";

const DASHBOARDS = [
  { key: "realEstate", label: "Real Estate", icon: <Building width={20} height={20} /> },
  { key: "hr", label: "Ressources humaines", icon: <Users width={21} height={21} /> },
  { key: "finance", label: "Finance", icon: <Wallet width={20} height={20} /> },
] as const;

const REAL_ESTATE_MODULES = [
  "executive",
  "portfolio",
  "land",
  "construction",
  "vrd",
  "commercialisation",
  "rental",
  "finance",
  "treasury",
  "accounting",
  "inventory",
  "patrimoine",
  "maintenance",
  "chantier-resources",
  "security",
  "clients",
  "risques",
  "ai",
  "alerts",
  "reports",
] as const;

/** Rail latéral : dashboards live + vues du cockpit Real Estate. */
export function SideRail() {
  const navigate = useNavigate();
  const { dashboard } = useParams();
  const { pathname } = useLocation();
  const moduleKey = pathname.startsWith("/modules/") ? pathname.split("/").at(-1) : undefined;
  const activeDashboard = dashboard ?? (pathname === "/" ? "realEstate" : undefined);

  const logout = () => {
    try {
      localStorage.removeItem("k-insight-token");
    } catch {
      /* stockage indisponible : ignore */
    }
    navigate("/");
  };

  return (
    <aside
      className="absolute left-3 top-[184px] z-30 flex max-h-[calc(100%-212px)] w-[72px] flex-col rounded-full px-2 py-4 sm:left-5 lg:left-[2.2%] lg:top-[205px]"
      style={{
        background: "rgba(255,255,255,0.66)",
        border: "1px solid rgba(255,255,255,0.72)",
        boxShadow: "0 18px 42px rgba(40,44,48,0.08)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
      }}
    >
      <div
        className="flex min-h-0 flex-1 flex-col items-center gap-3 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        style={{ scrollbarWidth: "none" }}
      >
        {DASHBOARDS.map((d) => (
          <CircleButton key={d.key} label={d.label} to={`/d/${d.key}`} active={activeDashboard === d.key}>
            {d.icon}
          </CircleButton>
        ))}

        <span className="my-1 h-px w-8 shrink-0 bg-[#DDE2E0]" />

        {REAL_ESTATE_MODULES.map((key) => {
          const module = MODULES[key];
          return (
            <CircleButton key={module.key} label={module.title} to={`/modules/${module.key}`} active={moduleKey === module.key}>
              <span className="grid place-items-center [&_svg]:h-5 [&_svg]:w-5">{module.icon}</span>
            </CircleButton>
          );
        })}
      </div>

      <div className="mt-3 flex shrink-0 flex-col items-center gap-3 border-t border-[#DDE2E0]/80 pt-3">
        <CircleButton label="Aide" to="/modules/aide" active={moduleKey === "aide"}>
          <Help width={20} height={20} />
        </CircleButton>
        <CircleButton label="Deconnexion" onClick={logout}>
          <Logout width={20} height={20} />
        </CircleButton>
      </div>
    </aside>
  );
}
