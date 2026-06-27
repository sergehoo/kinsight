/** Logo Datarium : barres de données ascendantes sur badge indigo. */
function DatariumLogo() {
  return (
    <span className="grid h-6 w-6 shrink-0 place-items-center rounded-[7px] shadow-[0_4px_10px_rgba(79,70,229,0.28)]" style={{ background: "linear-gradient(135deg,#4F46E5,#7C3AED)" }} aria-hidden>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
        <rect x="4" y="13" width="3.4" height="7" rx="1.2" fill="#fff" />
        <rect x="10.3" y="9" width="3.4" height="11" rx="1.2" fill="#fff" />
        <rect x="16.6" y="5" width="3.4" height="15" rx="1.2" fill="#fff" fillOpacity="0.85" />
      </svg>
    </span>
  );
}

/** Pied de page commun : copyright K-Insight + crédit Datarium. */
export function BrandFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-[#E2E6E2]/90 pt-5 text-[12px] text-[#8A8F8E]">
      <span>© {year} K-Insight — Plateforme de gouvernance du Groupe</span>
      <span className="flex items-center gap-2 font-semibold text-[#5B6470]">
        Réalisé par
        <DatariumLogo />
        <span className="text-[#2C3132]">Datarium</span>
      </span>
    </footer>
  );
}
