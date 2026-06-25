import * as React from "react";
import { Link } from "react-router-dom";

import { BLACK, glass } from "./theme";

interface CircleButtonProps {
  label: string;
  children: React.ReactNode;
  active?: boolean;
  alert?: boolean;
  /** Route interne ; si absent, le bouton se comporte comme un <button> (onClick). */
  to?: string;
  onClick?: () => void;
}

/** Bouton circulaire « verre » : devient un lien quand `to` est fourni. */
export function CircleButton({ label, children, active, alert, to, onClick }: CircleButtonProps) {
  const className =
    "relative grid h-14 w-14 place-items-center rounded-full text-[#1B1D1F] transition-transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF8735]/60";
  const style = active ? { background: BLACK, color: "#fff", boxShadow: "0 14px 26px rgba(0,0,0,0.18)" } : glass;
  const badge = alert ? (
    <span className="absolute right-3.5 top-3 h-2.5 w-2.5 rounded-full border-2 border-white bg-[#E12C34]" />
  ) : null;

  if (to) {
    return (
      <Link to={to} aria-label={label} title={label} className={className} style={style}>
        {children}
        {badge}
      </Link>
    );
  }
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick} className={className} style={style}>
      {children}
      {badge}
    </button>
  );
}
