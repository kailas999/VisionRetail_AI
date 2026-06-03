import { ArrowDownRight, ArrowUpRight, AlertTriangle } from "lucide-react";
import type { ZoneAnalyticsRich } from "@/lib/store-layout";
import { scoreTier } from "@/lib/store-layout";

interface Props {
  zone: ZoneAnalyticsRich;
  rank: number;
  total: number;
  isActive?: boolean;
  isDimmed?: boolean;
  onHover: (zone: ZoneAnalyticsRich | null, rect: DOMRect | null) => void;
  onClick?: () => void;
}

// Tier → solid color + soft surface tint
const tierStyle = {
  high:   { ring: "ring-emerald-500/40", bar: "bg-emerald-500", surface: "from-emerald-500/20 to-emerald-500/5", text: "text-emerald-700 dark:text-emerald-400", label: "High" },
  medium: { ring: "ring-amber-500/40",   bar: "bg-amber-500",   surface: "from-amber-500/20 to-amber-500/5",     text: "text-amber-700 dark:text-amber-400",   label: "Medium" },
  low:    { ring: "ring-rose-500/40",    bar: "bg-rose-500",    surface: "from-rose-500/20 to-rose-500/5",       text: "text-rose-700 dark:text-rose-400",     label: "Low" },
  idle:   { ring: "ring-zinc-400/30",    bar: "bg-zinc-400",    surface: "from-zinc-400/15 to-zinc-400/5",       text: "text-zinc-600",                         label: "Idle" },
} as const;

function fmtDwell(s: number) {
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

export function ZoneTile({ zone, rank, total, isActive, isDimmed, onHover, onClick }: Props) {
  const tier = scoreTier(zone.score);
  const style = tierStyle[tier];
  const trendUp = zone.trend >= 0;

  return (
    <button
      type="button"
      onMouseEnter={(e) => onHover(zone, (e.currentTarget as HTMLElement).getBoundingClientRect())}
      onMouseLeave={() => onHover(null, null)}
      onFocus={(e) => onHover(zone, (e.currentTarget as HTMLElement).getBoundingClientRect())}
      onBlur={() => onHover(null, null)}
      onClick={onClick}
      className={`group relative h-full w-full text-left rounded-xl border bg-gradient-to-br ${style.surface} border-border overflow-hidden
        transition-all duration-300 ease-out card-lift
        ${isActive ? `ring-2 ${style.ring}` : ""}
        ${isDimmed ? "opacity-40 saturate-50" : "opacity-100"}
        animate-[fade-in_400ms_ease-out]
      `}
      style={{ animationDelay: `${rank * 40}ms` }}
    >
      {/* Score bar */}
      <div className="absolute left-0 top-0 bottom-0 w-1">
        <div className={`${style.bar} h-full`} style={{ opacity: 0.85 }} />
      </div>

      {/* Anomaly indicator */}
      {zone.anomalies > 0 && (
        <span className="absolute top-2 right-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-critical/15 text-critical text-[9px] font-bold border border-critical/30">
          <AlertTriangle className="h-2.5 w-2.5" />
          {zone.anomalies}
        </span>
      )}

      <div className="relative p-3 pl-4 h-full flex flex-col justify-between min-h-[88px]">
        <div>
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
              #{rank}/{total}
            </span>
            <span className={`text-[9px] font-bold uppercase tracking-wider ${style.text}`}>· {style.label}</span>
          </div>
          <div className="text-sm font-semibold leading-tight mt-0.5 truncate">{zone.name}</div>
        </div>

        <div className="grid grid-cols-3 gap-1 mt-2">
          <Stat label="Dwell" value={fmtDwell(zone.avg_dwell)} />
          <Stat label="Visits" value={zone.visitors.toLocaleString()} />
          <Stat
            label="Conv"
            value={`${zone.conversion_rate}%`}
            trend={
              <span className={`inline-flex items-center text-[9px] font-bold ${trendUp ? "text-emerald-600" : "text-rose-600"}`}>
                {trendUp ? <ArrowUpRight className="h-2.5 w-2.5" /> : <ArrowDownRight className="h-2.5 w-2.5" />}
                {Math.abs(zone.trend).toFixed(1)}%
              </span>
            }
          />
        </div>
      </div>
    </button>
  );
}

function Stat({ label, value, trend }: { label: string; value: string; trend?: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground truncate">{label}</div>
      <div className="text-[11px] font-semibold tabular-nums truncate flex items-center gap-1">{value}{trend}</div>
    </div>
  );
}
