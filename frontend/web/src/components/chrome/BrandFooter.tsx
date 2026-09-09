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

/** Pied de page commun : copyright K-Insight + logo du Groupe + crédit Datarium. */
export function BrandFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-[#E2E6E2]/90 pt-5 text-[12px] text-[#8A8F8E]">
      <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
        © {year} K-Insight — Plateforme de gouvernance du Groupe
        {/* Le logo suit le copyright, dont il est la signature. Dimensions
            explicites : sans elles, l'image arrive après le texte et pousse la
            ligne, ce qui décale le pied de page une fois la mise en page déjà
            peinte. La hauteur est fixée et la largeur suit le rapport réel du
            fichier (786 × 330), donc aucune déformation. */}
        <img
          src="/assets/logo_kaydanG_B.png"
          alt="Groupe Kaydan"
          width={57}
          height={24}
          loading="lazy"
          decoding="async"
          className="h-6 w-auto shrink-0"
        />
      </span>
      <span className="flex items-center gap-2 font-semibold text-[#5B6470]">
        Réalisé par
        <DatariumLogo />
        <span className="text-[#2C3132]">Datarium</span>
      </span>
    </footer>
  );
}
