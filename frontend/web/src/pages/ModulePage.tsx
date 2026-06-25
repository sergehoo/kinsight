import { motion } from "framer-motion";
import { Navigate, useParams } from "react-router-dom";

import { AnimatedNumber } from "@/components/overview/AnimatedNumber";
import { Gauge } from "@/components/overview/Gauge";
import { ArrowUpRight, TriDown, TriUp } from "@/components/overview/icons";
import { PageShell } from "@/components/chrome/PageShell";
import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { getModule, type ModuleDef, type ModuleKpi, type ModuleRow } from "@/lib/modules";

function KpiCard({ kpi, index }: { kpi: ModuleKpi; index: number }) {
  return (
    <motion.article
      className="relative h-[188px] overflow-hidden rounded-[28px] p-6"
      style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.78),rgba(243,248,249,0.56))" }}
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -5, transition: { duration: 0.25, ease: EASE_OUT } }}
      transition={{ delay: 0.12 + index * 0.09, duration: 0.55, ease: EASE_OUT }}
    >
      <h3 className="max-w-[170px] text-[16px] font-semibold leading-tight text-[#1A1C1C]">{kpi.label}</h3>
      <span
        className="absolute left-6 top-[78px] inline-flex items-center gap-1.5 text-[14px] font-semibold"
        style={{ color: kpi.up ? "#202526" : "#C43252" }}
      >
        {kpi.delta}
        {kpi.up ? <TriUp width={12} height={12} /> : <TriDown width={12} height={12} />}
      </span>
      <AnimatedNumber value={kpi.value} className="absolute bottom-7 left-6 text-[34px] font-semibold leading-none text-black" />
      <div className="absolute -bottom-[18px] right-[-34px] h-[128px] w-[206px] opacity-95">
        <Gauge value={kpi.gauge} color={kpi.color} />
      </div>
    </motion.article>
  );
}

function RowList({ rows, showArrow }: { rows: ModuleRow[]; showArrow?: boolean }) {
  return (
    <div className="grid gap-3">
      {rows.map((row, index) => (
        <motion.div
          key={row.title}
          className="flex items-center gap-4 rounded-[22px] px-5 py-4"
          style={glass}
          initial={{ opacity: 0, x: -14 }}
          animate={{ opacity: 1, x: 0 }}
          whileHover={{ x: 4, transition: { duration: 0.2, ease: EASE_OUT } }}
          transition={{ delay: 0.1 + index * 0.07, duration: 0.45, ease: EASE_OUT }}
        >
          <span className="h-10 w-1.5 shrink-0 rounded-full" style={{ background: row.accent }} />
          <div className="min-w-0 flex-1">
            <div className="truncate text-[16px] font-semibold text-[#1B1D1D]">{row.title}</div>
            <div className="truncate text-[13px] font-medium text-[#7C8282]">{row.detail}</div>
          </div>
          {showArrow ? (
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/65 text-[#222]">
              <ArrowUpRight width={16} height={16} />
            </span>
          ) : null}
        </motion.div>
      ))}
    </div>
  );
}

function ModuleBody({ module }: { module: ModuleDef }) {
  if (module.kind !== "default" && module.rows) {
    return <RowList rows={module.rows} showArrow={module.kind === "notifications" || module.kind === "help"} />;
  }
  return (
    <>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {(module.kpis ?? []).map((kpi, index) => (
          <KpiCard key={kpi.label} kpi={kpi} index={index} />
        ))}
      </div>
      <motion.p
        className="mt-6 rounded-[22px] px-6 py-5 text-[14px] font-medium text-[#5F6663]"
        style={{ ...glass, background: "rgba(255,255,255,0.5)" }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.45, duration: 0.5 }}
      >
        Ce module est en préparation. Les valeurs affichées sont des données de démonstration : le branchement
        au backend governance se fait dès que le mart correspondant est matérialisé (lecture seule, ancrage strict).
      </motion.p>
    </>
  );
}

export function ModulePage() {
  const { key } = useParams();
  const module = getModule(key);
  if (!module) {
    return <Navigate to="/dashboard" replace />;
  }
  return (
    <PageShell
      title={module.title}
      subtitle={module.subtitle}
      status={module.status}
      icon={module.icon}
      accent={module.accent}
    >
      <ModuleBody module={module} />
    </PageShell>
  );
}
