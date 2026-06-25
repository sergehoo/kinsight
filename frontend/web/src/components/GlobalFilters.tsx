import { useFilters } from "@/store/filters";

const YEARS = [2024, 2025, 2026];
const QUARTERS = [1, 2, 3, 4];

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: number;
  options: { value: number; label: string }[];
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-slate-400">{label}</span>
      <select
        className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-slate-700 shadow-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function GlobalFilters() {
  const { year, quarter, setYear, setQuarter } = useFilters();
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Select
        label="Année"
        value={year}
        onChange={setYear}
        options={YEARS.map((y) => ({ value: y, label: String(y) }))}
      />
      <Select
        label="Trimestre"
        value={quarter}
        onChange={setQuarter}
        options={QUARTERS.map((q) => ({ value: q, label: `T${q}` }))}
      />
    </div>
  );
}
