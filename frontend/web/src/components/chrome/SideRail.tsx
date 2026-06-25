import { useNavigate, useParams, useLocation } from "react-router-dom";

import { Building, ChartPie, Cog, Help, Layers, Logout, Users, Wallet } from "@/components/overview/icons";

import { CircleButton } from "./CircleButton";

const DASHBOARDS = [
  { key: "realEstate", label: "Real Estate", icon: <Building width={20} height={20} /> },
  { key: "hr", label: "Ressources humaines", icon: <Users width={21} height={21} /> },
  { key: "finance", label: "Finance", icon: <Wallet width={20} height={20} /> },
] as const;

/** Rail latéral : sélection de dashboard (via URL) + accès aux modules transverses. */
export function SideRail() {
  const navigate = useNavigate();
  const { dashboard } = useParams();
  const { pathname } = useLocation();
  const activeKey = dashboard ?? (pathname === "/" ? "realEstate" : undefined);

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
      className="absolute bottom-auto left-3 top-[220px] z-30 flex h-[520px] w-[72px] flex-col justify-between rounded-full px-2 py-4 sm:left-5 lg:bottom-[4%] lg:left-[2.2%] lg:top-[33%] lg:h-auto"
      style={{
        background: "rgba(255,255,255,0.66)",
        border: "1px solid rgba(255,255,255,0.72)",
        boxShadow: "0 18px 42px rgba(40,44,48,0.08)",
        backdropFilter: "blur(18px)",
        WebkitBackdropFilter: "blur(18px)",
      }}
    >
      <div className="flex flex-col items-center gap-3">
        {DASHBOARDS.map((d) => (
          <CircleButton key={d.key} label={d.label} to={`/d/${d.key}`} active={activeKey === d.key}>
            {d.icon}
          </CircleButton>
        ))}
        <CircleButton label="Vue groupe" to="/modules/groupe" active={pathname === "/modules/groupe"}>
          <Layers width={20} height={20} />
        </CircleButton>
        <CircleButton label="Risques" to="/modules/risques" active={pathname === "/modules/risques"}>
          <ChartPie width={20} height={20} />
        </CircleButton>
        <CircleButton label="Parametres" to="/modules/parametres" active={pathname === "/modules/parametres"}>
          <Cog width={21} height={21} />
        </CircleButton>
      </div>
      <div className="flex flex-col items-center gap-3">
        <CircleButton label="Aide" to="/modules/aide" active={pathname === "/modules/aide"}>
          <Help width={20} height={20} />
        </CircleButton>
        <CircleButton label="Deconnexion" onClick={logout}>
          <Logout width={20} height={20} />
        </CircleButton>
      </div>
    </aside>
  );
}
