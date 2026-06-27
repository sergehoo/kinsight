const COUNT = 54;
const START = 20;
const END = 38;

const BARS = Array.from({ length: COUNT }, (_, i) => {
  const bump = Math.exp(-(((i - 26) ** 2) / 230));
  const wave = 0.5 + 0.5 * Math.sin(i * 0.7 + 0.5);
  return Math.min(96, 14 + bump * 74 + wave * 20);
});

const TICKS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

/** Coupe 2D façon référence Structo : histogramme fin orange/gris + slider à 2 poignées.
 *  Visualisation décorative gouvernée (aucune donnée chiffrée servie). */
export function CrossSectionChart({ accent = "#FF8735" }: { accent?: string }) {
  const leftPct = (START / COUNT) * 100;
  const widthPct = ((END - START + 1) / COUNT) * 100;

  return (
    <div className="flex h-full flex-col">
      <div className="relative min-h-[120px] flex-1">
        <div className="absolute inset-0 flex items-end gap-[3px]">
          {BARS.map((h, i) => {
            const active = i >= START && i <= END;
            return (
              <div
                key={i}
                className="flex-1 rounded-t-[4px]"
                style={{
                  height: `${h}%`,
                  background: active
                    ? `linear-gradient(180deg, ${accent} 0%, ${accent}b3 65%, ${accent}1f 100%)`
                    : "linear-gradient(180deg, rgba(222,226,222,0.9), rgba(238,240,238,0.35))",
                }}
              />
            );
          })}
        </div>
        <div className="absolute top-0 bottom-0 w-px" style={{ left: `${leftPct}%`, background: "rgba(213,46,87,0.5)" }} />
        <div className="absolute top-0 bottom-0 w-px" style={{ left: `${leftPct + widthPct}%`, background: "rgba(213,46,87,0.5)" }} />
      </div>

      <div className="mt-3 flex justify-between px-1 text-[11px] font-semibold text-[#9AA09D]">
        {TICKS.map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>

      <div className="relative mt-3 h-9">
        <div className="absolute inset-x-0 top-1/2 h-9 -translate-y-1/2 rounded-full bg-[#ECEDE8]" />
        <div
          className="absolute top-1/2 h-9 -translate-y-1/2 rounded-full"
          style={{ left: `${leftPct}%`, width: `${widthPct}%`, background: `linear-gradient(90deg, ${accent}, ${accent}cc)` }}
        />
        {[leftPct, leftPct + widthPct].map((pos) => (
          <span
            key={pos}
            className="absolute top-1/2 h-11 w-[3px] -translate-y-1/2 rounded-full"
            style={{ left: `${pos}%`, background: "#D52E57" }}
          />
        ))}
      </div>
    </div>
  );
}
