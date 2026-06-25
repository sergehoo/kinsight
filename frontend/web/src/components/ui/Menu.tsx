import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";

import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";

interface MenuProps {
  /** Rendu du déclencheur ; reçoit l'état ouvert et la bascule. */
  trigger: (props: { open: boolean; toggle: () => void }) => React.ReactNode;
  children: (close: () => void) => React.ReactNode;
  align?: "left" | "right";
  width?: number;
}

/** Petit popover « verre » avec fermeture au clic extérieur / Échap. */
export function Menu({ trigger, children, align = "right", width = 230 }: MenuProps) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      {trigger({ open, toggle: () => setOpen((value) => !value) })}
      <AnimatePresence>
        {open ? (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.18, ease: EASE_OUT }}
            className="absolute z-50 mt-2 overflow-hidden rounded-2xl p-2"
            style={{ ...glass, width, [align]: 0 } as React.CSSProperties}
            role="menu"
          >
            {children(() => setOpen(false))}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

/** Élément cliquable standard d'un menu. */
export function MenuItem({
  children,
  onClick,
  active,
}: {
  children: React.ReactNode;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-[14px] font-medium text-[#2A2D2D] transition-colors hover:bg-white/70"
      style={active ? { background: "rgba(255,135,53,0.16)", color: "#B65A14" } : undefined}
    >
      {children}
    </button>
  );
}
