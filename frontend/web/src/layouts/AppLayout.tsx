import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";
import {
  IconArrowDownRight,
  IconShield,
  IconTrend,
  IconUsers,
  IconWallet,
} from "@/components/icons";

const NAV = [
  { to: "/executif", label: "Exécutif", icon: IconTrend, disabled: true },
  { to: "/rh", label: "Ressources humaines", icon: IconUsers, disabled: false },
  { to: "/finance", label: "Finance", icon: IconWallet, disabled: true },
  { to: "/flotte", label: "Flotte", icon: IconArrowDownRight, disabled: true },
  { to: "/securite", label: "Sécurité", icon: IconShield, disabled: true },
];

export function AppLayout() {
  return (
    <div className="flex min-h-full">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 flex-col bg-ink-900 px-4 py-6 text-slate-300 md:flex">
        <div className="px-2 pb-8">
          <div className="text-lg font-semibold tracking-tight text-white">
            k<span className="text-brand-500">-</span>insight
          </div>
          <div className="text-[11px] uppercase tracking-widest text-slate-500">
            Pilotage Groupe
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, disabled }) =>
            disabled ? (
              <span
                key={to}
                className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500/70"
                title="Bientôt disponible"
              >
                <Icon className="h-[18px] w-[18px]" />
                {label}
              </span>
            ) : (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
                    isActive
                      ? "bg-brand-600 text-white shadow"
                      : "text-slate-300 hover:bg-ink-700 hover:text-white",
                  )
                }
              >
                <Icon className="h-[18px] w-[18px]" />
                {label}
              </NavLink>
            ),
          )}
        </nav>
        <div className="mt-auto px-2 pt-6 text-[11px] text-slate-600">
          Données issues du Data Warehouse — lecture seule.
        </div>
      </aside>

      {/* Contenu */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
