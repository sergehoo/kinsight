import { Link } from "react-router-dom";

/** Avatar utilisateur cliquable (page profil). */
export function Avatar() {
  return (
    <Link
      to="/modules/profil"
      aria-label="Mon profil"
      title="Mon profil"
      className="relative block h-14 w-14 overflow-hidden rounded-full bg-[#C7D9E6] ring-4 ring-white/70 transition-transform hover:-translate-y-0.5"
    >
      <span className="absolute left-1/2 top-2 h-6 w-7 -translate-x-1/2 rounded-t-full bg-[#332720]" />
      <span className="absolute left-1/2 top-3 h-7 w-7 -translate-x-1/2 rounded-full bg-[#E3B79B]" />
      <span className="absolute left-[20px] top-[23px] h-1 w-1 rounded-full bg-black" />
      <span className="absolute right-[20px] top-[23px] h-1 w-1 rounded-full bg-black" />
      <span className="absolute bottom-[-12px] left-1/2 h-9 w-12 -translate-x-1/2 rounded-t-full bg-[#EAF4FA]" />
      <span className="absolute bottom-[-10px] left-1/2 h-9 w-9 -translate-x-1/2 rounded-t-full bg-[#6288A8]" />
    </Link>
  );
}
