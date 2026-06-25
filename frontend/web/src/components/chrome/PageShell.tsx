import * as React from "react";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";

import { EASE_OUT } from "@/lib/motion";

import { AppHeader } from "./AppHeader";
import { SideRail } from "./SideRail";
import { FRAME_BG, glass } from "./theme";

interface PageShellProps {
  title: string;
  subtitle?: string;
  status?: string;
  icon?: React.ReactNode;
  accent?: string;
  children: React.ReactNode;
}

/** Cadre commun des pages secondaires : même fond/verre que le dashboard hero. */
export function PageShell({ title, subtitle, status, icon, accent = "#FF8735", children }: PageShellProps) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-[#B8B7B4] p-3 text-black sm:p-5 lg:p-6">
      <div className="relative mx-auto min-h-[760px] w-full max-w-[1840px] overflow-hidden rounded-[42px] border border-white/70 bg-[#F4F7F2] shadow-[0_34px_100px_rgba(36,38,38,0.22)] lg:min-h-[900px]">
        <div className={`pointer-events-none absolute inset-0 rounded-[inherit] ${FRAME_BG}`} />

        <AppHeader />
        <SideRail />

        <main className="relative z-10 px-6 pb-16 pl-24 sm:px-10 lg:pl-[8.6%] lg:pr-[4%]">
          <motion.button
            type="button"
            onClick={() => navigate(-1)}
            className="mb-7 inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold text-[#3A3E3E]"
            style={glass}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4, ease: EASE_OUT }}
            whileHover={{ x: -3 }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m15 18-6-6 6-6" />
            </svg>
            Retour
          </motion.button>

          <motion.div
            className="flex flex-wrap items-center gap-5"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: EASE_OUT }}
          >
            {icon ? (
              <span
                className="grid h-16 w-16 place-items-center rounded-[22px] text-white shadow-[0_18px_36px_rgba(0,0,0,0.12)]"
                style={{ background: accent }}
              >
                {icon}
              </span>
            ) : null}
            <div className="min-w-0">
              <h1 className="text-[38px] font-semibold leading-tight tracking-tight text-black sm:text-[46px]">{title}</h1>
              {subtitle ? <p className="mt-2 max-w-[640px] text-[15px] font-medium text-[#777C7D]">{subtitle}</p> : null}
            </div>
            {status ? (
              <span className="ml-auto inline-flex items-center gap-2 self-start rounded-full bg-white/72 px-4 py-2 text-[12px] font-semibold text-[#6D7372] shadow-sm">
                <span className="h-2 w-2 rounded-full" style={{ background: accent }} />
                {status}
              </span>
            ) : null}
          </motion.div>

          <div className="mt-9">{children}</div>
        </main>
      </div>
    </div>
  );
}
