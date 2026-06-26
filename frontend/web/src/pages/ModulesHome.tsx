import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import { ArrowUpRight } from "@/components/overview/icons";
import { PageShell } from "@/components/chrome/PageShell";
import { glass } from "@/components/chrome/theme";
import { EASE_OUT } from "@/lib/motion";
import { DASHBOARD_LINKS, HR_MODULE_KEYS, MODULES, REAL_ESTATE_MODULE_KEYS } from "@/lib/modules";

function ModuleTile({
  to,
  title,
  subtitle,
  accent,
  icon,
  index,
  live,
}: {
  to: string;
  title: string;
  subtitle: string;
  accent: string;
  icon: React.ReactNode;
  index: number;
  live?: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 + index * 0.05, duration: 0.45, ease: EASE_OUT }}
    >
      <Link
        to={to}
        className="group relative flex h-[150px] flex-col justify-between overflow-hidden rounded-[26px] p-5"
        style={{ ...glass, background: "linear-gradient(135deg,rgba(255,255,255,0.8),rgba(243,248,249,0.55))" }}
      >
        <div className="flex items-start justify-between">
          <span className="grid h-12 w-12 place-items-center rounded-2xl text-white shadow-[0_12px_24px_rgba(0,0,0,0.12)]" style={{ background: accent }}>
            {icon}
          </span>
          <span className="grid h-9 w-9 place-items-center rounded-full bg-white/65 text-[#222] transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5">
            <ArrowUpRight width={16} height={16} />
          </span>
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="truncate text-[18px] font-semibold text-[#171818]">{title}</h3>
            {live ? <span className="rounded-full bg-[#E7F6EF] px-2 py-0.5 text-[10px] font-bold text-[#1F9D6B]">LIVE</span> : null}
          </div>
          <p className="mt-1 line-clamp-2 text-[13px] font-medium text-[#7C8282]">{subtitle}</p>
        </div>
      </Link>
    </motion.div>
  );
}

export function ModulesHome() {
  const realEstateModules = REAL_ESTATE_MODULE_KEYS.map((key) => MODULES[key]);
  const hrModules = HR_MODULE_KEYS.map((key) => MODULES[key]);
  return (
    <PageShell
      title="Dashboard"
      subtitle="Cockpits de gouvernance du groupe Kaydan. Les dashboards LIVE sont servis par le backend governance."
      status="Vue d'ensemble"
    >
      <h2 className="mb-4 text-[15px] font-bold uppercase tracking-wider text-[#8A908D]">Dashboards servis</h2>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {DASHBOARD_LINKS.map((d, index) => (
          <ModuleTile
            key={d.key}
            to={`/d/${d.key}`}
            title={d.title}
            subtitle={d.subtitle}
            accent={d.accent}
            icon={d.icon}
            index={index}
            live
          />
        ))}
      </div>

      <h2 className="mb-4 mt-10 text-[15px] font-bold uppercase tracking-wider text-[#8A908D]">Real Estate Governance</h2>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {realEstateModules.map((module, index) => (
          <ModuleTile
            key={module.key}
            to={`/modules/${module.key}`}
            title={module.title}
            subtitle={module.subtitle}
            accent={module.accent}
            icon={module.icon}
            index={index + DASHBOARD_LINKS.length}
          />
        ))}
      </div>

      <h2 className="mb-4 mt-10 text-[15px] font-bold uppercase tracking-wider text-[#8A908D]">Human Resources Governance</h2>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {hrModules.map((module, index) => (
          <ModuleTile
            key={module.key}
            to={`/modules/${module.key}`}
            title={module.title}
            subtitle={module.subtitle}
            accent={module.accent}
            icon={module.icon}
            index={index + DASHBOARD_LINKS.length + realEstateModules.length}
          />
        ))}
      </div>
    </PageShell>
  );
}
