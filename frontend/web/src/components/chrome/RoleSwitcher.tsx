import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { ChevronDown, Shield } from "@/components/overview/icons";
import { EASE_OUT } from "@/lib/motion";
import { getCurrentRole, setRole, type Role } from "@/lib/permissions";

import { glass } from "./theme";

const ROLES: { value: Role; label: string; scope: string }[] = [
  { value: "SUPER_ADMIN", label: "Super Admin", scope: "Tous les domaines" },
  { value: "DG", label: "DG / CODIR", scope: "Tous les domaines" },
  { value: "DAF", label: "DAF", scope: "Finance · Rapports · Groupe" },
  { value: "RH", label: "DRH", scope: "Capital Humain" },
  { value: "DIR_IMMO", label: "Directeur Immobilier", scope: "Immobilier · Opérations · Commercial" },
  { value: "READER", label: "Lecteur", scope: "Groupe · Rapports" },
];

/** Sélecteur de rôle (démo SSO) : applique le périmètre de permissions et recharge. */
export function RoleSwitcher() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = getCurrentRole();
  const currentLabel = ROLES.find((role) => role.value === current)?.label ?? "Super Admin";

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    return () => window.removeEventListener("mousedown", onClick);
  }, [open]);

  const choose = (role: Role) => {
    setRole(role);
    setOpen(false);
    window.location.href = "/dashboard";
  };

  return (
    <div ref={ref} className="relative hidden sm:block">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex h-14 items-center gap-2 rounded-full px-4 text-[13px] font-bold text-[#1B1D1F] transition-transform hover:-translate-y-0.5"
        style={glass}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Changer de rôle (démo des permissions)"
      >
        <Shield width={17} height={17} />
        <span className="hidden max-w-[150px] truncate md:inline">{currentLabel}</span>
        <span style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .2s" }}>
          <ChevronDown width={15} height={15} />
        </span>
      </button>

      <AnimatePresence>
        {open ? (
          <motion.div
            role="menu"
            className="absolute right-0 top-[60px] z-50 w-[260px] rounded-[22px] p-2"
            style={glass}
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: EASE_OUT }}
          >
            <p className="px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[#9AA09D]">Rôle / périmètre</p>
            {ROLES.map((role) => {
              const active = role.value === current;
              return (
                <button
                  key={role.value}
                  type="button"
                  role="menuitem"
                  onClick={() => choose(role.value)}
                  className="flex w-full flex-col items-start rounded-[14px] px-3 py-2 text-left transition-colors hover:bg-white/65"
                  style={active ? { background: "#0B0B0C", color: "#fff" } : { color: "#2C3132" }}
                >
                  <span className="text-[13.5px] font-bold">{role.label}</span>
                  <span className={`text-[11px] font-semibold ${active ? "text-white/65" : "text-[#838A8B]"}`}>{role.scope}</span>
                </button>
              );
            })}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
