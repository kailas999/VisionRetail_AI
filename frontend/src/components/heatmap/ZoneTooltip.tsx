import { useEffect, useState } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { ZoneAnalyticsRich } from "@/lib/store-layout";

interface Props {
  zone: ZoneAnalyticsRich;
  rect: DOMRect;
  rank: number;
  total: number;
}

export function ZoneTooltip({ zone, rect, rank, total }: Props) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const tooltipW = 260;
  const tooltipH = 240;
  const padding = 12;
  let left = rect.left + rect.width / 2 - tooltipW / 2;
  let top = rect.top - tooltipH - padding;
  if (top < 8) top = rect.bottom + padding;
  if (left < 8) left = 8;
  if (left + tooltipW > window.innerWidth - 8) left = window.innerWidth - tooltipW - 8;

  const trendUp = zone.trend >= 0;

  return (
    <div
      role="tooltip"
      className="fixed z-50 pointer-events-none transition-all duration-150"
      style={{
        left,
        top,
        width: tooltipW,
        opacity: mounted ? 1 : 0,
        transform: mounted ? "translateY(0) scale(1)" : "translateY(4px) scale(0.98)",
      }}
    >
      <div className="surface rounded-xl p-3.5 shadow-glow border-primary/30">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-bold">{zone.name}</div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
            Rank #{rank}/{total}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs">
          <Field label="Avg Dwell" value={`${zone.avg_dwell}s`} />
          <Field label="Visitors" value={zone.visitors.toLocaleString()} />
          <Field label="Conversion" value={`${zone.conversion_rate}%`} />
          <Field
            label="Trend"
            value={
              <span className={`inline-flex items-center gap-0.5 font-bold ${trendUp ? "text-emerald-600" : "text-rose-600"}`}>
                {trendUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {Math.abs(zone.trend).toFixed(1)}%
              </span>
            }
          />
          <Field label="Zone Enter" value={zone.zone_enter_count?.toLocaleString() || "0"} />
          <Field label="Zone Exit" value={zone.zone_exit_count?.toLocaleString() || "0"} />
          <Field label="Peak Hour" value={zone.peak_hour} />
          <Field
            label="Anomalies"
            value={
              <span className={zone.anomalies > 0 ? "text-critical font-bold" : "text-muted-foreground"}>
                {zone.anomalies}
              </span>
            }
          />
        </div>

        <div className="mt-3 pt-2.5 border-t border-border">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            <span>Performance Score</span>
            <span className="font-bold text-foreground tabular-nums">{zone.score}/100</span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-gradient-teal transition-all duration-500"
              style={{ width: `${zone.score}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-xs font-semibold tabular-nums mt-0.5">{value}</div>
    </div>
  );
}
