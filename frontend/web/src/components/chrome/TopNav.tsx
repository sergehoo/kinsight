import { Link, useLocation } from "react-router-dom";

import { BarChart } from "@/components/overview/icons";

import { BLACK, glass } from "./theme";

interface NavItem {
  label: string;
  to: string;
  icon?: React.ReactNode;
  match: (pathname: string) => boolean;
}

const ITEMS: NavItem[] = [
  { label: "Dashboard", to: "/dashboard", match: (p) => p.startsWith("/dashboard") },
  {
    label: "Analytics",
    to: "/",
    icon: <BarChart width={18} height={18} />,
    match: (p) => p === "/" || p.startsWith("/d/"),
  },
  { label: "Timeline", to: "/modules/timeline", match: (p) => p === "/modules/timeline" },
  { label: "Work areas", to: "/modules/work-areas", match: (p) => p === "/modules/work-areas" },
];

/** Barre de navigation principale : liens réels avec état actif déduit de l'URL. */
export function TopNav() {
  const { pathname } = useLocation();
  return (
    <nav className="flex items-center gap-1 rounded-full px-2 py-1.5" style={glass} aria-label="Navigation principale">
      {ITEMS.map((item) => {
        const active = item.match(pathname);
        return (
          <Link
            key={item.label}
            to={item.to}
            className="flex h-11 items-center gap-2 rounded-full px-6 text-[16px] font-medium transition-transform hover:-translate-y-0.5"
            style={active ? { background: BLACK, color: "#fff", boxShadow: "0 18px 32px rgba(0,0,0,0.18)" } : { color: "#222" }}
            aria-current={active ? "page" : undefined}
          >
            {item.icon}
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
