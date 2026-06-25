import * as React from "react";

type P = React.SVGProps<SVGSVGElement>;
const svg = (p: P) => ({
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...p,
});

export const Layers = (p: P) => (
  <svg {...svg(p)}><path d="M12 3 3 8l9 5 9-5-9-5Z" /><path d="m3 13 9 5 9-5" /></svg>
);
export const Building = (p: P) => (
  <svg {...svg(p)}><path d="M5 21V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v16" /><path d="M14 9h4a1 1 0 0 1 1 1v11" /><path d="M3 21h18M8 7h2M8 11h2M8 15h2" /></svg>
);
export const ChartPie = (p: P) => (
  <svg {...svg(p)}><path d="M12 3a9 9 0 1 0 9 9h-9V3Z" /><path d="M16 8a6 6 0 0 0-4-4" /></svg>
);
export const Cog = (p: P) => (
  <svg {...svg(p)}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 0 1-4 0v-.1A1.7 1.7 0 0 0 7 19.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0-1.2-2.9H3a2 2 0 0 1 0-4h.1A1.7 1.7 0 0 0 4.7 7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H10A1.7 1.7 0 0 0 11 3.1V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 2.9 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V10a1.7 1.7 0 0 0 1.6 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></svg>
);
export const Folder = (p: P) => (
  <svg {...svg(p)}><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" /></svg>
);
export const Help = (p: P) => (
  <svg {...svg(p)}><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 0 1 4.5 1.5c0 1.5-2 2-2 3.5" /><path d="M12 17h.01" /></svg>
);
export const Logout = (p: P) => (
  <svg {...svg(p)}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5M21 12H9" /></svg>
);
export const Bell = (p: P) => (
  <svg {...svg(p)}><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 0 1-3.4 0" /></svg>
);
export const Briefcase = (p: P) => (
  <svg {...svg(p)}><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18" /></svg>
);
export const ChevronDown = (p: P) => (
  <svg {...svg(p)}><path d="m6 9 6 6 6-6" /></svg>
);
export const ArrowUpRight = (p: P) => (
  <svg {...svg(p)}><path d="M7 17 17 7M8 7h9v9" /></svg>
);
export const Dots = (p: P) => (
  <svg {...svg(p)}><circle cx="5" cy="12" r="1.4" /><circle cx="12" cy="12" r="1.4" /><circle cx="19" cy="12" r="1.4" /></svg>
);
export const Pen = (p: P) => (
  <svg {...svg(p)}><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" /></svg>
);
export const User = (p: P) => (
  <svg {...svg(p)}><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a6 6 0 0 1 12 0v1" /></svg>
);
export const TriUp = (p: P) => (
  <svg {...svg({ ...p, fill: "currentColor", stroke: "none" })}><path d="M12 7l5 8H7l5-8Z" /></svg>
);
export const TriDown = (p: P) => (
  <svg {...svg({ ...p, fill: "currentColor", stroke: "none" })}><path d="M12 17l-5-8h10l-5 8Z" /></svg>
);
export const Home = (p: P) => (
  <svg {...svg(p)}><path d="m3 11 9-8 9 8" /><path d="M5 10v10h14V10" /><path d="M10 20v-6h4v6" /></svg>
);
export const Grid = (p: P) => (
  <svg {...svg(p)}><rect x="4" y="4" width="6" height="6" rx="1.2" /><rect x="14" y="4" width="6" height="6" rx="1.2" /><rect x="4" y="14" width="6" height="6" rx="1.2" /><rect x="14" y="14" width="6" height="6" rx="1.2" /></svg>
);
export const BarChart = (p: P) => (
  <svg {...svg(p)}><path d="M4 19V5" /><path d="M4 19h16" /><rect x="7" y="11" width="2.8" height="5" rx="1" /><rect x="12" y="7" width="2.8" height="9" rx="1" /><rect x="17" y="9" width="2.8" height="7" rx="1" /></svg>
);
export const Users = (p: P) => (
  <svg {...svg(p)}><circle cx="9" cy="8" r="3.2" /><path d="M3.5 20a5.5 5.5 0 0 1 11 0" /><path d="M16 11a3 3 0 0 0 0-6" /><path d="M18 19a4.2 4.2 0 0 0-3-4" /></svg>
);
export const Network = (p: P) => (
  <svg {...svg(p)}><circle cx="7" cy="7" r="3" /><circle cx="17" cy="7" r="3" /><circle cx="12" cy="17" r="3" /><path d="m9.5 8.5 2 5.5M14.5 8.5l-2 5.5M10 7h4" /></svg>
);
export const Wallet = (p: P) => (
  <svg {...svg(p)}><path d="M20 8V6.5A2.5 2.5 0 0 0 17.5 4h-12A2.5 2.5 0 0 0 3 6.5v11A2.5 2.5 0 0 0 5.5 20H20v-4" /><path d="M17 12a2 2 0 0 0 0 4h4v-4Z" /><path d="M7 8h7" /></svg>
);
export const FileText = (p: P) => (
  <svg {...svg(p)}><path d="M6 3h8l4 4v14H6Z" /><path d="M14 3v5h5" /><path d="M9 13h6M9 17h6M9 9h2" /></svg>
);
export const Shield = (p: P) => (
  <svg {...svg(p)}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" /><path d="m9 12 2 2 4-4" /></svg>
);
export const Mail = (p: P) => (
  <svg {...svg(p)}><rect x="3.5" y="5.5" width="17" height="13" rx="2" /><path d="m4.5 7 7.5 6 7.5-6" /></svg>
);
export const BriefcaseBusiness = (p: P) => (
  <svg {...svg(p)}><rect x="4" y="7" width="16" height="12" rx="2" /><path d="M9 7V5.5A1.5 1.5 0 0 1 10.5 4h3A1.5 1.5 0 0 1 15 5.5V7" /><path d="M4 12h16" /></svg>
);
export const DollarCircle = (p: P) => (
  <svg {...svg(p)}><circle cx="12" cy="12" r="9" /><path d="M12 7v10M15 9.5c-.7-.7-1.7-1-3-1-1.6 0-2.6.8-2.6 1.9 0 1.2 1.1 1.7 2.9 2.1 1.7.4 2.7.9 2.7 2.1 0 1.2-1.1 1.9-2.9 1.9-1.2 0-2.3-.4-3.1-1.1" /></svg>
);
export const Receipt = (p: P) => (
  <svg {...svg(p)}><path d="M6 3h12v18l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2L6 21Z" /><path d="M9 8h6M9 12h6M9 16h4" /></svg>
);
export const Calculator = (p: P) => (
  <svg {...svg(p)}><rect x="6" y="3" width="12" height="18" rx="2" /><path d="M9 7h6" /><path d="M9 11h.01M12 11h.01M15 11h.01M9 15h.01M12 15h.01M15 15h.01M9 18h.01M12 18h.01M15 18h.01" /></svg>
);
export const Target = (p: P) => (
  <svg {...svg(p)}><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" /><path d="m15 9 4-4M18 5h3v3" /></svg>
);
export const Cart = (p: P) => (
  <svg {...svg(p)}><circle cx="9" cy="20" r="1.4" /><circle cx="18" cy="20" r="1.4" /><path d="M3 4h2l2.2 11.5a2 2 0 0 0 2 1.5h8.6a2 2 0 0 0 2-1.6L21 8H7" /></svg>
);
export const Calendar = (p: P) => (
  <svg {...svg(p)}><rect x="4" y="5" width="16" height="15" rx="2" /><path d="M8 3v4M16 3v4M4 10h16" /></svg>
);
export const CheckCircle = (p: P) => (
  <svg {...svg(p)}><circle cx="12" cy="12" r="9" /><path d="m8.5 12.5 2.2 2.2 4.8-5.2" /></svg>
);
