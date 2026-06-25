import * as React from "react";
import { motion } from "framer-motion";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  title: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
  tone?: "default" | "good" | "bad";
  index?: number;
}

const toneRing: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  default: "text-brand-600 bg-brand-50",
  good: "text-emerald-600 bg-emerald-50",
  bad: "text-rose-600 bg-rose-50",
};

export function KpiCard({
  title,
  value,
  hint,
  icon,
  tone = "default",
  index = 0,
}: KpiCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06, ease: "easeOut" }}
    >
      <Card className="overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{title}</CardTitle>
          {icon && (
            <span className={cn("grid h-9 w-9 place-items-center rounded-xl", toneRing[tone])}>
              {icon}
            </span>
          )}
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-semibold tracking-tight text-slate-900">{value}</div>
          {hint && <div className="mt-1 text-xs text-slate-400">{hint}</div>}
        </CardContent>
      </Card>
    </motion.div>
  );
}
