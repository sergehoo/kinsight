import { Link } from "react-router-dom";

/** Logo K-Insight cliquable (retour à l'accueil). */
export function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="Accueil K-Insight">
      <span className="text-[#F28B38]" aria-hidden>
        <svg width="34" height="34" viewBox="0 0 32 32" fill="none">
          <path d="M16 3.2 4.8 9.4 16 15.6 27.2 9.4 16 3.2Z" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" />
          <path d="M6.2 15.5 16 20.9l9.8-5.4" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M6.2 21.4 16 26.8l9.8-5.4" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="text-[26px] font-extrabold tracking-normal text-black">K-Insight</span>
    </Link>
  );
}
