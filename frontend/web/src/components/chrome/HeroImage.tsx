/** Visuel de héros d'un domaine, servi en variantes responsives.
 *
 *  Les sources d'origine pèsent de 6 à 24 Mo pour être affichées dans un bloc de
 *  quelques centaines de pixels : le navigateur téléchargeait donc l'intégralité
 *  d'un fichier 6666×3749 avant de peindre le héros. On sert désormais AVIF puis
 *  WebP, en 640/1024/1600, avec repli sur le fichier d'origine si une variante
 *  manque — aucun écran ne se retrouve sans image.
 */
import * as React from "react";

export interface HeroImageProps {
  /** Base des variantes optimisées, sans largeur ni extension (dossier /assets/opt). */
  slug?: string;
  /** Chemin du fichier d'origine, utilisé en repli. */
  fallback: string;
  /** Description réelle du contenu ; chaîne vide si l'image est décorative. */
  alt: string;
  /** true pour le visuel de héros : il est le LCP, on ne le retarde pas. */
  priority?: boolean;
  className?: string;
  /** `contain` conserve la silhouette (visuels détourés), `cover` remplit le cadre. */
  fit?: "cover" | "contain";
}

const WIDTHS = [640, 1024, 1600];

/** Largeurs MESURÉES du cadre, pas estimées : à 1440 px de fenêtre, le visuel
 *  occupe 428 px (la colonne principale est amputée du rail et de la colonne KPI).
 *  Un `sizes` trop généreux faisait télécharger la variante 1600 pour un cadre de
 *  428 px — soit 231 Ko au lieu de 143 Ko sur le chemin critique du LCP. */
const SIZES = "(max-width: 640px) 92vw, (max-width: 1024px) 55vw, (max-width: 1536px) 32vw, 480px";

export function HeroImage({ slug, fallback, alt, priority = false, className = "", fit = "cover" }: HeroImageProps) {
  const [failed, setFailed] = React.useState(false);
  const useOptimized = Boolean(slug) && !failed;
  const srcSet = (ext: string) => WIDTHS.map((w) => `/assets/opt/${slug}-${w}.${ext} ${w}w`).join(", ");

  const imgClass =
    `h-full w-full ${fit === "cover" ? "rounded-[28px] object-cover opacity-[0.94]" : "scale-[1.05] object-contain drop-shadow-[0_30px_44px_rgba(32,34,34,0.16)]"} ${className}`;

  const common = {
    alt,
    className: imgClass,
    // Le héros est le plus grand élément peint : le charger tôt protège le LCP.
    loading: priority ? ("eager" as const) : ("lazy" as const),
    fetchPriority: priority ? ("high" as const) : ("auto" as const),
    decoding: priority ? ("sync" as const) : ("async" as const),
    // Une variante absente ne doit pas laisser un trou : on repasse à l'original.
    onError: () => setFailed(true),
  };

  if (!useOptimized) return <img src={fallback} {...common} />;

  return (
    <picture>
      <source type="image/avif" srcSet={srcSet("avif")} sizes={SIZES} />
      <source type="image/webp" srcSet={srcSet("webp")} sizes={SIZES} />
      <img src={`/assets/opt/${slug}-1024.webp`} {...common} />
    </picture>
  );
}
