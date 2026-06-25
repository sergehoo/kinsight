const LINE = "#343434";
const FAINT = "#8F959A";
const ORANGE = "#F27A2D";

export function BuildingWireframe({ className }: { className?: string }) {
  const guideLines = Array.from({ length: 11 }, (_, i) => 70 + i * 58);
  const scaffoldLevels = [104, 142, 180, 218, 256, 294, 332];

  return (
    <svg
      viewBox="0 0 760 480"
      className={className}
      fill="none"
      aria-hidden
    >
      <defs>
        <linearGradient id="wood-panel" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#D39868" />
          <stop offset="45%" stopColor="#A76036" />
          <stop offset="100%" stopColor="#6D3D27" />
        </linearGradient>
        <linearGradient id="glass-panel" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.88" />
          <stop offset="100%" stopColor="#A8B4BB" stopOpacity="0.26" />
        </linearGradient>
        <filter id="soft-building-shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="22" stdDeviation="18" floodColor="#1E2227" floodOpacity="0.12" />
        </filter>
      </defs>

      <g stroke={FAINT} strokeWidth="0.8" strokeOpacity="0.26">
        {guideLines.map((x) => (
          <path key={`v-${x}`} d={`M${x} 34v378`} />
        ))}
        {scaffoldLevels.map((y) => (
          <path key={`h-${y}`} d={`M82 ${y}h616`} />
        ))}
        <path d="M86 392h622" />
        <path d="M96 355 668 92" />
        <path d="M142 416 710 172" />
        <path d="M92 228 650 420" />
      </g>

      <g filter="url(#soft-building-shadow)">
        <path
          d="M162 304 300 246 600 272 492 342Z"
          fill="#DBDFE0"
          fillOpacity="0.42"
          stroke={LINE}
          strokeOpacity="0.24"
        />

        <path
          d="M190 200 326 118 610 146 464 234Z"
          fill="#FFFFFF"
          fillOpacity="0.8"
          stroke={LINE}
          strokeWidth="1.6"
          strokeOpacity="0.36"
        />
        <path
          d="M326 118 448 60 610 146"
          fill="#F3F1EE"
          fillOpacity="0.74"
          stroke={LINE}
          strokeWidth="1.6"
          strokeOpacity="0.36"
        />
        <path
          d="M347 122 448 78 580 144"
          stroke={LINE}
          strokeWidth="1"
          strokeOpacity="0.22"
        />

        <path
          d="M190 200 464 234 464 342 190 308Z"
          fill="#F7F8F6"
          stroke={LINE}
          strokeWidth="1.5"
          strokeOpacity="0.38"
        />
        <path
          d="M464 234 610 146 610 262 464 342Z"
          fill="#EEF0EF"
          stroke={LINE}
          strokeWidth="1.5"
          strokeOpacity="0.36"
        />

        <path
          d="M230 211 330 225 330 318 230 305Z"
          fill="url(#wood-panel)"
          fillOpacity="0.86"
          stroke={LINE}
          strokeOpacity="0.25"
        />
        <path
          d="M351 229 438 240 438 331 351 320Z"
          fill="url(#glass-panel)"
          stroke={LINE}
          strokeOpacity="0.22"
        />
        <path
          d="M484 238 576 184 576 258 484 315Z"
          fill="url(#wood-panel)"
          fillOpacity="0.74"
          stroke={LINE}
          strokeOpacity="0.24"
        />

        <g stroke="#2B2B2B" strokeOpacity="0.23">
          <path d="M250 214v94M276 218v94M304 222v94" />
          <path d="M366 231v92M392 234v92M418 237v92" />
          <path d="M230 244l208 25M230 277l208 25" />
          <path d="M505 226v76M532 210v76M558 196v74" />
          <path d="M484 265l92-54M484 292l92-54" />
        </g>

        <path
          d="M183 199 326 110 617 141"
          stroke={LINE}
          strokeWidth="2"
          strokeOpacity="0.48"
        />
        <path
          d="M464 233 464 350"
          stroke={LINE}
          strokeWidth="1.2"
          strokeOpacity="0.34"
        />
      </g>

      <g stroke={LINE} strokeWidth="1" strokeOpacity="0.30">
        <path d="M108 105h548M108 143h548M108 181h548M108 219h548M108 257h548M108 295h548M108 333h548" />
        <path d="M112 92v284M158 82v306M204 74v324M250 64v346M296 55v365M342 50v376M388 48v382M434 52v374M480 62v350M526 78v314M572 98v274M618 122v232" />
        <path d="M112 106 158 143 112 181M158 143 204 106M204 181 158 143M204 106 250 143 204 181M250 143 296 106M296 181 250 143M296 106 342 143 296 181M342 143 388 106M388 181 342 143M388 106 434 143 388 181M434 143 480 106M480 181 434 143M480 106 526 143 480 181M526 143 572 106M572 181 526 143M572 106 618 143 572 181" />
      </g>

      <g stroke={ORANGE} strokeLinecap="round">
        <path d="M196 345c46 10 99 14 158 12 51-2 106-10 165-24" strokeWidth="3" strokeOpacity="0.24" />
        <path d="M333 88 448 42 608 126" strokeWidth="2" strokeOpacity="0.58" />
      </g>
    </svg>
  );
}
