import { ArrowDownRight, ArrowUpRight, AlertTriangle } from "lucide-react";
import type { FunnelStageRich } from "@/lib/funnel-data";
import { STATUS_STYLE } from "@/lib/funnel-data";

interface Props {
  stages: FunnelStageRich[];
}

export function StageAnalysis({ stages }: Props) {
  return (
    <div className="surface-elevated rounded-2xl p-5 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold">Stage Analysis</h3>
          <p className="text-xs text-muted-foreground mt-1">Per-stage performance vs industry benchmark</p>
        </div>
      </div>

      <div className="space-y-3 overflow-y-auto pr-1 -mr-1 flex-1">
        {stages.map((s, i) => {
          const status = STATUS_STYLE[s.status];
          const trendUp = s.trend >= 0;
          const benchDelta = s.conversion_rate - s.benchmark;
          const benchUp = benchDelta >= 0;
          const conversionPct = Math.min(100, s.conversion_rate);
          const benchmarkPct = Math.min(100, s.benchmark);
          return (
            <div
              key={s.id}
              className="rounded-xl border border-border bg-muted/30 p-4 animate-[fade-in_400ms_ease-out]"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              {/* Header row */}
              <div className="flex items-start justify-between gap-2 mb-2.5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-muted-foreground tabular-nums">{String(i + 1).padStart(2, "0")}</span>
                    <h4 className="text-sm font-semibold truncate">{s.name}</h4>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{s.description}</p>
                </div>
                <span className={`shrink-0 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-bold border ${status.bg} ${status.text} ${status.border}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
                  {status.label}
                </span>
              </div>

              {/* Stats grid */}
              <div className="grid grid-cols-4 gap-2 mb-3">
                <Stat label="Visitors" value={s.visitors.toLocaleString()} />
                <Stat label="Conversion" value={`${s.conversion_rate}%`} />
                <Stat
                  label="Drop-off"
                  value={`${s.dropoff_rate}%`}
                  tone={s.dropoff_rate > 40 ? "critical" : s.dropoff_rate > 25 ? "warn" : "neutral"}
                />
                <Stat
                  label="Trend"
                  value={
                    <span className={`inline-flex items-center gap-0.5 font-bold ${trendUp ? "text-emerald-600" : "text-rose-600"}`}>
                      {trendUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                      {Math.abs(s.trend).toFixed(1)}%
                    </span>
                  }
                />
              </div>

              {/* Benchmark comparison bar */}
              <div>
                <div className="flex items-center justify-between text-[10px] mb-1">
                  <span className="uppercase tracking-wider text-muted-foreground">vs Industry benchmark</span>
                  <span className={`font-bold tabular-nums ${benchUp ? "text-emerald-600" : "text-rose-600"}`}>
                    {benchUp ? "+" : ""}{benchDelta.toFixed(1)} pts
                  </span>
                </div>
                <div className="relative h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary to-teal transition-all duration-700"
                    style={{ width: `${conversionPct}%` }}
                  />
                  {/* Benchmark marker */}
                  <div
                    className="absolute inset-y-0 w-px bg-foreground/70"
                    style={{ left: `${benchmarkPct}%` }}
                    aria-label="benchmark"
                  />
                </div>
                <div className="flex justify-between text-[10px] text-muted-foreground mt-1 tabular-nums">
                  <span>0%</span>
                  <span>Current {s.conversion_rate}% · Avg {s.benchmark}%</span>
                  <span>100%</span>
                </div>
              </div>

              {s.anomalies > 0 && (
                <div className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-critical">
                  <AlertTriangle className="h-3 w-3" /> {s.anomalies} active anomaly
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: React.ReactNode;
  tone?: "neutral" | "warn" | "critical";
}) {
  const toneClass =
    tone === "critical" ? "text-rose-600" : tone === "warn" ? "text-amber-600" : "text-foreground";
  return (
    <div className="min-w-0">
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground truncate">{label}</div>
      <div className={`text-xs font-semibold tabular-nums truncate mt-0.5 ${toneClass}`}>{value}</div>
    </div>
  );
}
