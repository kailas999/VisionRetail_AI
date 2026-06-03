import { CheckCircle2, AlertTriangle, Sparkles, TrendingUp, TrendingDown } from "lucide-react";
import type { ZoneAnalyticsRich } from "@/lib/store-layout";

interface Props {
  zones: ZoneAnalyticsRich[];
}

interface Insight {
  kind: "positive" | "warning";
  text: string;
}

function buildInsights(zones: ZoneAnalyticsRich[]): Insight[] {
  if (!zones.length) return [];
  const top = [...zones].sort((a, b) => b.score - a.score)[0];
  const bottom = [...zones].sort((a, b) => a.score - b.score)[0];
  const biggestDrop = [...zones].sort((a, b) => a.trend - b.trend)[0];
  const biggestGain = [...zones].sort((a, b) => b.trend - a.trend)[0];
  const lowConv = zones.filter((z) => z.conversion_rate < 15 && z.visitors > 100)[0];

  const insights: Insight[] = [];
  insights.push({ kind: "positive", text: `${top.name} leads with a ${top.score}/100 score — highest engagement in the store.` });
  if (biggestGain.trend > 0)
    insights.push({ kind: "positive", text: `${biggestGain.name} conversion improved ${biggestGain.trend.toFixed(1)}% vs last period.` });
  if (biggestDrop.trend < -10)
    insights.push({ kind: "warning", text: `${biggestDrop.name} traffic dropped ${Math.abs(biggestDrop.trend).toFixed(1)}%. Investigate visual merchandising.` });
  if (lowConv)
    insights.push({ kind: "warning", text: `${lowConv.name} conversion below benchmark at ${lowConv.conversion_rate}%. Consider promoter staffing.` });
  insights.push({ kind: "warning", text: `${bottom.name} scoring ${bottom.score}/100 — bottom of the floor.` });
  return insights.slice(0, 5);
}

export function InsightsPanel({ zones }: Props) {
  const insights = buildInsights(zones);
  const trafficTotal = zones.reduce((s, z) => s + z.visitors, 0);
  const weightedConv =
    zones.reduce((s, z) => s + z.conversion_rate * z.visitors, 0) / Math.max(1, trafficTotal);
  const avgTrend = zones.reduce((s, z) => s + z.trend, 0) / Math.max(1, zones.length);

  return (
    <div className="surface-elevated rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-primary grid place-items-center shadow-glow">
            <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
          </div>
          <h4 className="text-sm font-semibold">AI Insights</h4>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-primary font-bold">Auto-generated</span>
      </div>

      {/* Trend summary */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        <TrendStat
          label="Traffic trend"
          value={`${avgTrend >= 0 ? "+" : ""}${avgTrend.toFixed(1)}%`}
          positive={avgTrend >= 0}
        />
        <TrendStat
          label="Conv. weighted"
          value={`${weightedConv.toFixed(1)}%`}
          positive={weightedConv >= 20}
        />
      </div>

      {/* Insight list */}
      <ul className="space-y-2">
        {insights.map((i, idx) => {
          const isPos = i.kind === "positive";
          const Icon = isPos ? CheckCircle2 : AlertTriangle;
          return (
            <li
              key={idx}
              className={`flex items-start gap-2 p-2.5 rounded-lg border ${isPos ? "bg-emerald-500/5 border-emerald-500/20" : "bg-amber-500/5 border-amber-500/25"}`}
            >
              <Icon className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${isPos ? "text-emerald-600" : "text-amber-600"}`} />
              <span className="text-xs leading-snug">{i.text}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function TrendStat({ label, value, positive }: { label: string; value: string; positive: boolean }) {
  const Icon = positive ? TrendingUp : TrendingDown;
  return (
    <div className="rounded-lg border border-border bg-muted/40 p-2.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${positive ? "text-emerald-600" : "text-rose-600"}`} />
        <span className="text-base font-bold tabular-nums">{value}</span>
      </div>
    </div>
  );
}
