import type { LucideIcon } from "lucide-react";
import { AnimatedNumber } from "@/components/dashboard/AnimatedNumber";
import { cn } from "@/lib/utils";

interface Props {
  label: string;
  value: number;
  icon: LucideIcon;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  hint?: string;
  tone?: "primary" | "teal" | "warn" | "critical";
}

const toneMap = {
  primary:  { glow: "from-primary/20 to-primary/0",  icon: "bg-primary/10 text-primary border-primary/20" },
  teal:     { glow: "from-teal/20 to-teal/0",        icon: "bg-teal/10 text-teal border-teal/20" },
  warn:     { glow: "from-warn/20 to-warn/0",       icon: "bg-warn/10 text-warn border-warn/20" },
  critical: { glow: "from-critical/20 to-critical/0", icon: "bg-critical/10 text-critical border-critical/20" },
};

export function FunnelKpiCard({ label, value, icon: Icon, prefix, suffix, decimals = 0, hint, tone = "primary" }: Props) {
  const t = toneMap[tone];
  return (
    <div className="surface-elevated card-lift rounded-2xl p-4 relative overflow-hidden group">
      <div className={cn("absolute -top-10 -right-10 h-28 w-28 rounded-full bg-gradient-to-br blur-2xl opacity-50 pointer-events-none group-hover:opacity-70 transition-opacity", t.glow)} />
      <div className="flex items-center justify-between relative">
        <span className="section-label">{label}</span>
        <div className={cn("h-8 w-8 rounded-lg grid place-items-center border", t.icon)}>
          <Icon className="h-3.5 w-3.5" />
        </div>
      </div>
      <div className="mt-3 text-2xl md:text-3xl font-bold tracking-tight tabular-nums font-[var(--font-display)]">
        <AnimatedNumber value={value} prefix={prefix} suffix={suffix} decimals={decimals} />
      </div>
      {hint && <div className="text-[11px] text-muted-foreground mt-1.5">{hint}</div>}
    </div>
  );
}
