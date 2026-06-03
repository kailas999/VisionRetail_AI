import { AlertTriangle, Info, Zap, ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Anomaly, AnomalySeverity } from "@/lib/store-api";
import { AIInsightCard } from "@/components/dashboard/AIInsightCard";

interface Props {
  anomalies: Anomaly[];
  storeId?: string;
}

const sevConfig: Record<
  AnomalySeverity,
  { icon: typeof Zap; badge: string; dot: string; color: string; border: string }
> = {
  CRITICAL: {
    icon: Zap,
    badge: "bg-critical/10 text-critical border-critical/30",
    dot: "bg-critical",
    color: "oklch(0.56 0.22 25)",
    border: "glow-border-critical",
  },
  WARN: {
    icon: AlertTriangle,
    badge: "bg-warn/10 text-warn border-warn/30",
    dot: "bg-warn",
    color: "oklch(0.62 0.17 65)",
    border: "",
  },
  INFO: {
    icon: Info,
    badge: "bg-info/10 text-info border-info/30",
    dot: "bg-info",
    color: "oklch(0.58 0.14 235)",
    border: "",
  },
};

function timeAgo(iso: string) {
  const diff = Math.max(0, Date.now() - new Date(iso).getTime());
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export function AnomaliesFeed({ anomalies, storeId = "STORE_BLR_002" }: Props) {
  const { sevData, zoneData, counts } = useMemo(() => {
    const sevCounts: Record<AnomalySeverity, number> = { CRITICAL: 0, WARN: 0, INFO: 0 };
    const zoneCounts: Record<string, number> = {};
    for (const a of anomalies) {
      sevCounts[a.severity] = (sevCounts[a.severity] || 0) + 1;
      const z = a.zone || "Other";
      zoneCounts[z] = (zoneCounts[z] || 0) + 1;
    }
    const sevData = (Object.keys(sevCounts) as AnomalySeverity[])
      .map((k) => ({ name: k, value: sevCounts[k], color: sevConfig[k].color }))
      .filter((d) => d.value > 0);
    const zoneData = Object.entries(zoneCounts)
      .map(([zone, count]) => ({ zone, count }))
      .sort((a, b) => b.count - a.count);
    return { sevData, zoneData, counts: sevCounts };
  }, [anomalies]);

  const total = anomalies.length;

  return (
    <div className="surface-elevated rounded-2xl p-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-lg font-semibold">Active Anomalies</h3>
          <p className="text-xs text-muted-foreground mt-1">
            {total} active · real-time signal
          </p>
        </div>
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md border border-success/30 bg-success/10">
          <span className="pulse-dot" />
          <span className="text-[10px] font-semibold tracking-wider uppercase text-success">
            Live
          </span>
        </div>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-3 gap-2 mb-5">
        {(["CRITICAL", "WARN", "INFO"] as AnomalySeverity[]).map((sev) => {
          const cfg = sevConfig[sev];
          const Icon = cfg.icon;
          return (
            <div
              key={sev}
              className="rounded-xl border border-border bg-muted/40 p-3 flex flex-col gap-1.5"
            >
              <div className="flex items-center gap-1.5">
                <Icon className="h-3.5 w-3.5" style={{ color: cfg.color }} />
                <span className="text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
                  {sev}
                </span>
              </div>
              <div className="text-2xl font-bold tabular-nums" style={{ color: cfg.color }}>
                {counts[sev]}
              </div>
            </div>
          );
        })}
      </div>

      {/* Charts row: donut + bar */}
      {total > 0 && (
        <div className="grid grid-cols-2 gap-3 mb-5">
          {/* Donut: severity mix */}
          <div className="rounded-xl border border-border bg-muted/30 p-3">
            <div className="text-[10px] font-bold tracking-wider uppercase text-muted-foreground mb-1">
              Severity mix
            </div>
            <div className="relative h-32">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sevData}
                    dataKey="value"
                    innerRadius={32}
                    outerRadius={52}
                    paddingAngle={3}
                    stroke="none"
                  >
                    {sevData.map((d) => (
                      <Cell key={d.name} fill={d.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "oklch(1 0 0 / 0.98)",
                      border: "1px solid oklch(0.92 0.01 280)",
                      borderRadius: 10,
                      fontSize: 11,
                      padding: "6px 10px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <div className="text-xl font-bold leading-none tabular-nums">{total}</div>
                <div className="text-[9px] uppercase tracking-wider text-muted-foreground mt-0.5">
                  alerts
                </div>
              </div>
            </div>
          </div>

          {/* Bar: by zone */}
          <div className="rounded-xl border border-border bg-muted/30 p-3">
            <div className="text-[10px] font-bold tracking-wider uppercase text-muted-foreground mb-1">
              By zone
            </div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={zoneData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
                  <defs>
                    <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="oklch(0.52 0.22 300)" stopOpacity={0.95} />
                      <stop offset="100%" stopColor="oklch(0.62 0.13 180)" stopOpacity={0.85} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="zone"
                    stroke="oklch(0.50 0.02 275)"
                    fontSize={9}
                    tickLine={false}
                    axisLine={false}
                    interval={0}
                  />
                  <YAxis
                    stroke="oklch(0.50 0.02 275)"
                    fontSize={9}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    cursor={{ fill: "oklch(0.52 0.22 300 / 0.08)" }}
                    contentStyle={{
                      background: "oklch(1 0 0 / 0.98)",
                      border: "1px solid oklch(0.92 0.01 280)",
                      borderRadius: 10,
                      fontSize: 11,
                      padding: "6px 10px",
                    }}
                  />
                  <Bar dataKey="count" fill="url(#barGrad)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Section label */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
          Recent alerts
        </span>
        <span className="text-[10px] text-muted-foreground">{anomalies.length} shown</span>
      </div>

      {/* Alert list */}
      <div className="space-y-2.5 overflow-y-auto pr-1 -mr-1 flex-1">
        {anomalies.map((a) => {
          const cfg = sevConfig[a.severity];
          const Icon = cfg.icon;
          return (
            <div
              key={a.id}
              className={`relative rounded-xl p-3.5 bg-card border border-border card-lift ${cfg.border}`}
            >
              <span
                className="absolute left-0 top-3 bottom-3 w-1 rounded-r-full"
                style={{ background: cfg.color }}
              />
              <div className="pl-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider border ${cfg.badge}`}
                    >
                      <Icon className="h-3 w-3" /> {a.severity}
                    </span>
                    <span className="text-[10px] text-muted-foreground font-mono">{a.type}</span>
                  </div>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {timeAgo(a.detected_at)}
                  </span>
                </div>
                <div className="mt-1.5 text-sm font-medium leading-snug">{a.title}</div>
                {a.zone && (
                  <div className="mt-0.5 text-[11px] text-muted-foreground">Zone · {a.zone}</div>
                )}
                <div className="mt-2.5 pt-2.5 border-t border-border/70 flex items-start gap-2">
                  <ShieldCheck className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
                  <div>
                    <div className="text-[9px] uppercase tracking-wider text-muted-foreground">
                      Suggested action
                    </div>
                    <div className="text-xs text-foreground/90 mt-0.5">{a.suggested_action}</div>
                  </div>
                </div>

                {/* AI Insight — lazy-fetched on demand */}
                <AIInsightCard anomalyId={a.id} storeId={storeId} />
              </div>
            </div>
          );
        })}
        {total === 0 && (
          <div className="text-center text-sm text-muted-foreground py-12">
            No active anomalies detected.
          </div>
        )}
      </div>
    </div>
  );
}
