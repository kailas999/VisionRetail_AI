import type { FunnelStage } from "@/lib/store-api";

interface Props { stages: FunnelStage[] }

export function FunnelView({ stages }: Props) {
  const max = stages[0]?.count ?? 1;
  return (
    <div className="surface-elevated rounded-2xl p-6 h-full">
      <div className="mb-5">
        <h3 className="text-lg font-semibold">Conversion Funnel</h3>
        <p className="text-xs text-muted-foreground mt-1">Entry → Engagement → Billing → Converted</p>
      </div>
      <div className="space-y-3">
        {stages.map((s, i) => {
          const width = (s.count / max) * 100;
          const dropoff = i > 0 ? ((stages[i - 1].count - s.count) / stages[i - 1].count) * 100 : 0;
          return (
            <div key={s.stage}>
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="font-medium text-foreground/90">{s.stage}</span>
                <span className="text-muted-foreground tabular-nums">
                  {s.count.toLocaleString()} · {(s.rate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="relative h-10 rounded-xl bg-muted/40 overflow-hidden border border-border/60">
                <div
                  className="h-full bg-gradient-teal shadow-glow-teal flex items-center justify-end pr-3 text-xs font-semibold text-teal-foreground transition-all duration-700"
                  style={{ width: `${width}%` }}
                >
                  {width > 18 && `${(s.rate * 100).toFixed(1)}%`}
                </div>
              </div>
              {i > 0 && (
                <div className="text-[11px] text-critical/90 mt-1 ml-1">
                  ▼ {dropoff.toFixed(1)}% drop-off
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
