import type * as React from "react";

export const ORANGE = "#FF8735";
export const BLACK = "#060606";

/** Surface « verre » partagée par toute l'application (header, cartes, rails). */
export const glass: React.CSSProperties = {
  background: "rgba(255,255,255,0.66)",
  border: "1px solid rgba(255,255,255,0.72)",
  boxShadow: "0 18px 42px rgba(40,44,48,0.08)",
  backdropFilter: "blur(18px)",
  WebkitBackdropFilter: "blur(18px)",
};

/** Dégradé de fond du cadre principal, réutilisé par le shell et les pages. */
export const FRAME_BG =
  "bg-[radial-gradient(circle_at_14%_22%,rgba(236,242,221,0.72),transparent_33%),radial-gradient(circle_at_84%_18%,rgba(218,229,246,0.78),transparent_38%),linear-gradient(90deg,rgba(246,249,241,0.96),rgba(238,244,247,0.92))]";
