import { Funnel, FunnelChart as RcFunnelChart, LabelList, ResponsiveContainer, Tooltip, Cell } from "recharts";
import { useState } from "react";
import type { FunnelStageRich } from "@/lib/funnel-data";
import { useTheme } from "@/hooks/use-theme";
import { getChartTheme } from "@/lib/chart-theme";

interface Props {
  stages: FunnelStageRich[];
  comparison: Record<string, number>;
  comparisonLabel: string;
}

// Color ramp top→bottom: primary → teal (top-of-funnel rich, bottom-of-funnel high-intent)
const STAGE_COLORS = [
  "oklch(0.52 0.22 300)",
  "oklch(0.58 0.20 280)",
  "oklch(0.62 0.16 230)",
  "oklch(0.62 0.13 180)",
];

export function FunnelVisualization({ stages, comparison, comparisonLabel }: Props) {
  const [hoverId, setHoverId] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();
  const chart = getChartTheme(resolvedTheme === "dark");

  const data = stages.map((s, i) => ({
    name: s.name,
    value: s.visitors,
    fill: STAGE_COLORS[i % STAGE_COLORS.length],
    stage: s,
  }));

  return (
    <div className="surface-elevated rounded-2xl p-5 h-full flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="text-lg font-semibold">Conversion Funnel</h3>
          <p className="text-xs text-muted-foreground mt-1">Entry → Engagement → Billing → Purchase</p>
        </div>
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
          <span className="h-2 w-6 rounded-full bg-gradient-to-r from-primary to-teal" />
          High intent
        </div>
      </div>

      {/* Funnel chart */}
      <div className="h-72 -mx-2">
        <ResponsiveContainer width="100%" height="100%">
          <RcFunnelChart>
            <Tooltip
              cursor={{ fill: chart.cursor }}
              contentStyle={chart.tooltip}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const p = payload[0].payload as { stage: FunnelStageRich };
                const s = p.stage;
                return (
                  <div className="surface rounded-xl p-3 min-w-[200px] border-primary/30">
                    <div className="text-sm font-bold mb-1.5">{s.name}</div>
                    <Row label="Visitors" value={s.visitors.toLocaleString()} />
                    <Row label="Conversion" value={`${s.conversion_rate}%`} />
                    <Row label="Drop-off" value={`${s.dropoff_rate}%`} />
                    <Row label="Avg dwell" value={s.avg_dwell ? `${s.avg_dwell}s` : "—"} />
                    <Row label="Anomalies" value={String(s.anomalies)} highlight={s.anomalies > 0} />
                  </div>
                );
              }}
            />
            <Funnel
              dataKey="value"
              data={data}
              isAnimationActive
              animationDuration={700}
              onMouseEnter={(d: unknown) => {
                const stage = (d as { stage?: FunnelStageRich })?.stage;
                if (stage) setHoverId(stage.id);
              }}
              onMouseLeave={() => setHoverId(null)}
            >
              {data.map((d) => (
                <Cell
                  key={d.stage.id}
                  fill={d.fill}
                  stroke={chart.stroke}
                  strokeWidth={2}
                  fillOpacity={hoverId && hoverId !== d.stage.id ? 0.45 : 1}
                />
              ))}
              <LabelList
                position="right"
                fill={chart.label}
                stroke="none"
                fontSize={12}
                fontWeight={600}
                dataKey="name"
              />
            </Funnel>
          </RcFunnelChart>
        </ResponsiveContainer>
      </div>

      {/* Stage rail under the funnel with vs-comparison */}
      <div className="grid grid-cols-4 gap-2 mt-2">
        {stages.map((s, i) => {
          const compRate = comparison[s.id];
          const diff = s.conversion_rate - compRate;
          const diffUp = diff >= 0;
          return (
            <div
              key={s.id}
              className="rounded-lg border border-border bg-muted/30 p-2 text-center"
              style={{ borderTopColor: STAGE_COLORS[i], borderTopWidth: 2 }}
            >
              <div className="text-[9px] uppercase tracking-wider text-muted-foreground truncate">{s.name}</div>
              <div className="text-sm font-bold tabular-nums mt-0.5">{s.conversion_rate}%</div>
              <div className={`text-[10px] font-bold tabular-nums ${diffUp ? "text-success" : "text-critical"}`}>
                {diffUp ? "▲" : "▼"} {Math.abs(diff).toFixed(1)} vs {comparisonLabel}
              </div>
            </div>
          );
        })}
      </div>

      {/* Drop-off chevrons between stages */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        {stages.slice(1).map((s) => (
          <div
            key={`drop-${s.id}`}
            className="rounded-lg border border-critical/20 bg-critical/5 p-2 text-center"
          >
            <div className="text-[9px] uppercase tracking-wider text-critical">Drop-off</div>
            <div className="text-sm font-bold tabular-nums text-critical mt-0.5">
              ▼ {s.dropoff_rate}%
            </div>
            <div className="text-[10px] text-muted-foreground tabular-nums">
              −{s.lost_users.toLocaleString()} visitors
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex justify-between text-[11px] py-0.5">
      <span className="text-muted-foreground">{label}</span>
      <span className={`font-semibold tabular-nums ${highlight ? "text-critical" : ""}`}>{value}</span>
    </div>
  );
}
