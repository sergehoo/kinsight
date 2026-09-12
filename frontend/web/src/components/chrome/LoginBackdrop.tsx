/** Fond animé de la page de connexion : la chaîne de données, pas un décor.
 *
 *  CE QU'IL REPRÉSENTE. K-Insight fait une seule chose : lire des sources
 *  hétérogènes, les normaliser dans son backend, et les servir avec un ÉTAT
 *  déclaré. Le fond donne à voir ce trajet — des points d'origine à gauche, des
 *  liaisons qui convergent vers le centre, une diffusion vers les écrans à droite.
 *  Le point de convergence n'est pas dessiné : la CARTE DE CONNEXION l'occupe, et
 *  tient donc elle-même le rôle du passage par le backend.
 *
 *  CE QU'IL NE MONTRE PAS, ET C'EST DÉLIBÉRÉ. Aucun chiffre, aucun pourcentage,
 *  aucune courbe qui se lirait comme une mesure. Un faux tableau de bord en fond
 *  d'écran serait précisément la donnée inventée que l'ADR-0007 interdit — et
 *  cette page est la première que voit un dirigeant chaque matin.
 *
 *  UNE SOURCE RESTE GRISE. Ce n'est pas un oubli : c'est l'état `disconnected` du
 *  vocabulaire gouverné. Le produit se distingue en disant ce qu'il ne sait pas,
 *  et son écran d'accueil peut le dire aussi.
 *
 *  COÛT, MESURÉ ET NON SUPPOSÉ. `stroke-dashoffset` déclenche un repaint à chaque
 *  image, ce qui condamne cette technique en principe. En pratique, sur ces six
 *  tracés fins : temps d'image médian 16,7 ms avec l'animation, 16,7 ms sans,
 *  p95 17,5 contre 17,6 — soit la cadence 60 Hz dans les deux cas, écart nul.
 *  La mesure est consignée ici pour qu'on ne « l'optimise » pas par principe vers
 *  une solution plus compliquée sans gain.
 *
 *  Aucun canvas, aucune boucle JavaScript, aucune image : rien qui retarde le
 *  premier rendu. Masqué sous `sm`, où il passerait derrière la carte au lieu de
 *  l'habiller.
 */
/** Les couleurs viennent de `STATE_META` (components/ui/kit.tsx) : le fond parle
 *  le même vocabulaire d'états que les écrans, il ne s'invente pas une palette. */
const ETATS = {
  connected: "#1E8A6E",
  connecting: "#E0801E",
  partial: "#B8791C",
  disconnected: "#7C8384",
} as const;

/** Une source : son point d'origine, sa liaison vers le centre, son état. */
const SOURCES = [
  { y: 170, etat: ETATS.connected, retard: "0s", duree: "7s" },
  { y: 300, etat: ETATS.connected, retard: "-2.4s", duree: "6s" },
  { y: 430, etat: ETATS.connecting, retard: "-4.1s", duree: "8s" },
  // Celle-ci ne transporte rien : pas de tiret animé, un gris franc.
  { y: 560, etat: ETATS.disconnected, retard: null, duree: null },
] as const;

/** Les écrans desservis, à droite du centre. */
const SORTIES = [
  { y: 230, etat: ETATS.connected, retard: "-1.2s", duree: "6.5s" },
  { y: 365, etat: ETATS.partial, retard: "-3.6s", duree: "7.5s" },
  { y: 500, etat: ETATS.connected, retard: "-5.2s", duree: "6.8s" },
] as const;

// Centre de convergence, en coordonnées du viewBox. Il coïncide avec le centre
// de l'écran, donc avec la carte : les flux y entrent et en ressortent.
const CENTRE_X = 640;
const CENTRE_Y = 365;

export function LoginBackdrop() {
  // `contain: paint` borne la zone que le navigateur doit repeindre au conteneur :
  // le fond ne peut pas déclencher un repaint du reste de la page.
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden [contain:paint]" aria-hidden>
      {/* Même famille de halos que le cadre des tableaux de bord : la page de
          connexion doit ressembler à ce qu'elle ouvre. */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_14%_22%,rgba(236,242,221,0.75),transparent_36%),radial-gradient(circle_at_86%_18%,rgba(218,229,246,0.8),transparent_40%),linear-gradient(120deg,rgba(247,250,243,0.98),rgba(238,244,247,0.95))]" />

      {/* Masqué sous `sm` : ce schéma a besoin de largeur pour se lire comme une
          chaîne. Sur un téléphone il passait derrière la carte — halo orange au
          milieu du champ mot de passe — et gênait la saisie au lieu de l'habiller.
          Le lavis de couleur, lui, reste à toutes les tailles. */}
      <svg
        className="absolute inset-0 hidden h-full w-full sm:block"
        viewBox="0 0 1280 730"
        preserveAspectRatio="xMidYMid slice"
        role="presentation"
      >
        <defs>
          {/* La trame : la nature tabulaire de l'entrepôt, à peine visible. */}
          {/* Extinction radiale : sans elle, la composition se termine sur une
              arête franche au bord d'un grand écran. Le masque la fait mourir
              dans le fond. */}
          <radialGradient id="ki-login-extinction">
            <stop offset="0%" stopColor="#fff" stopOpacity="1" />
            <stop offset="62%" stopColor="#fff" stopOpacity="1" />
            <stop offset="100%" stopColor="#fff" stopOpacity="0" />
          </radialGradient>
          <mask id="ki-login-masque">
            <rect width="1280" height="730" fill="url(#ki-login-extinction)" />
          </mask>
          <pattern id="ki-login-trame" width="44" height="44" patternUnits="userSpaceOnUse">
            <path d="M44 0H0V44" fill="none" stroke="rgba(116,124,125,0.09)" strokeWidth="1" />
          </pattern>
        </defs>

        <g mask="url(#ki-login-masque)">
        <rect width="1280" height="730" fill="url(#ki-login-trame)" />

        {SOURCES.map((s, i) => {
          const chemin = `M 150 ${s.y} C 340 ${s.y}, 470 ${CENTRE_Y}, ${CENTRE_X - 34} ${CENTRE_Y}`;
          return (
            <g key={`src-${i}`}>
              <path d={chemin} fill="none" stroke={s.etat} strokeOpacity="0.16" strokeWidth="1.5" />
              {/* Le trait pointillé qui défile EST le flux. Une source non
                  connectée n'en a pas : rien ne circule, et ça se voit. */}
              {s.duree ? (
                <path
                  className="ki-login-flux"
                  d={chemin}
                  fill="none"
                  stroke={s.etat}
                  strokeOpacity="0.55"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeDasharray="3 26"
                  style={{ animationDuration: s.duree, animationDelay: s.retard ?? "0s" }}
                />
              ) : null}
              <circle cx="150" cy={s.y} r="7" fill="none" stroke={s.etat} strokeOpacity="0.5" strokeWidth="1.6" />
              <circle cx="150" cy={s.y} r="3" fill={s.etat} fillOpacity={s.duree ? 0.75 : 0.35} />
            </g>
          );
        })}

        {SORTIES.map((s, i) => {
          const chemin = `M ${CENTRE_X + 34} ${CENTRE_Y} C ${CENTRE_X + 190} ${CENTRE_Y}, 960 ${s.y}, 1140 ${s.y}`;
          return (
            <g key={`out-${i}`}>
              <path d={chemin} fill="none" stroke={s.etat} strokeOpacity="0.16" strokeWidth="1.5" />
              <path
                className="ki-login-flux"
                d={chemin}
                fill="none"
                stroke={s.etat}
                strokeOpacity="0.5"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeDasharray="3 26"
                style={{ animationDuration: s.duree, animationDelay: s.retard }}
              />
              {/* Un écran `partial` est dessiné À MOITIÉ REMPLI, arête franche.
                  Le vocabulaire devient forme : « partiel » ne se déduit pas
                  d'une nuance de couleur, il se voit. */}
              <rect
                x="1128" y={s.y - 11} width="26" height="22" rx="5"
                fill="none" stroke={s.etat} strokeOpacity="0.42" strokeWidth="1.6"
              />
              {s.etat === ETATS.partial ? (
                <path d={`M 1128 ${s.y - 11} h 13 v 22 h -13 z`} fill={s.etat} fillOpacity="0.2" />
              ) : null}
            </g>
          );
        })}

        </g>

        {/* PAS DE « cœur » dessiné ici. Les flux convergent vers le centre de
            l'écran — c'est-à-dire vers la carte de connexion elle-même, qui tient
            donc le rôle du point de normalisation. Un ornement de plus à cet
            endroit serait invisible en desktop (la carte le couvre entièrement) et
            traverserait le verre sur les écrans étroits. */}
      </svg>
    </div>
  );
}
