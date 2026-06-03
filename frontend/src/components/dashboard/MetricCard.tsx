import type { LucideIcon } from "lucide-react";
import { AnimatedNumber } from "./AnimatedNumber";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: number;
  icon: LucideIcon;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  delta?: { value: number; positive?: boolean };
  accent?: "primary" | "teal" | "warn";
}

const accentMap = {
  primary: {
    glow: "from-primary/20 to-primary/0",
    icon: "bg-primary/10 text-primary border-primary/20",
    bar: "bg-primary",
  },
  teal: {
    glow: "from-teal/20 to-teal/0",
    icon: "bg-teal/10 text-teal border-teal/20",
    bar: "bg-teal",
  },
  warn: {
    glow: "from-warn/20 to-warn/0",
    icon: "bg-warn/10 text-warn border-warn/20",
    bar: "bg-warn",
  },
};

export function MetricCard({ label, value, icon: Icon, suffix, prefix, decimals = 0, delta, accent = "primary" }: Props) {
  const styles = accentMap[accent];

  return (
    <div className="surface-elevated card-lift rounded-2xl p-5 relative overflow-hidden group">
      <div className={cn("absolute -top-16 -right-16 h-36 w-36 rounded-full bg-gradient-to-br blur-3xl opacity-50 pointer-events-none transition-opacity duration-300 group-hover:opacity-70", styles.glow)} />
      <div className={cn("absolute bottom-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-60 transition-opacity duration-300", styles.bar)} />

      <div className="flex items-center justify-between relative">
        <span className="section-label">{label}</span>
        <div className={cn("h-9 w-9 rounded-xl grid place-items-center border", styles.icon)}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div className="mt-4 flex items-baseline gap-2 relative">
        <div className="text-3xl md:text-4xl font-bold font-[var(--font-display)] tracking-tight tabular-nums">
          <AnimatedNumber value={value} suffix={suffix} prefix={prefix} decimals={decimals} />
        </div>
        {delta && (
          <span
            className={cn(
              "text-xs font-semibold px-1.5 py-0.5 rounded-md",
              delta.positive ? "text-success bg-success/10" : "text-critical bg-critical/10",
            )}
          >
            {delta.positive ? "▲" : "▼"} {Math.abs(delta.value).toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}
