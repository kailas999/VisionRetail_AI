import { Sparkles, Target, AlertTriangle, Lightbulb, TrendingDown, ArrowRight } from "lucide-react";
import type { FunnelStageRich } from "@/lib/funnel-data";
import { buildInsights } from "@/lib/funnel-data";

interface Props {
  stages: FunnelStageRich[];
}

export function FunnelInsights({ stages }: Props) {
  const { headline, cause, recommendation, bullets } = buildInsights(stages);

  return (
    <div className="surface-elevated rounded-2xl p-5 h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-primary grid place-items-center shadow-glow">
            <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
          </div>
          <h3 className="text-sm font-semibold">AI Insights</h3>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-primary font-bold">Auto-generated</span>
      </div>

      {/* Headline card */}
      <div className="rounded-xl border border-rose-500/30 bg-gradient-to-br from-rose-500/10 to-rose-500/0 p-4 mb-4">
        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-rose-700">
          <TrendingDown className="h-3 w-3" /> Largest leakage
        </div>
        <div className="mt-1 flex items-baseline gap-2 flex-wrap">
          <span className="text-xl font-bold">{headline.stage.name}</span>
          <span className="text-[11px] text-muted-foreground">
            {headline.stage.lost_users.toLocaleString()} visitors lost
          </span>
        </div>
        <div className="mt-2 text-xs">
          Estimated revenue impact:{" "}
          <span className="font-bold text-rose-600 tabular-nums">
            ₹{headline.lost_revenue.toLocaleString("en-IN")}
          </span>
        </div>
      </div>

      {/* Bullets */}
      <ul className="space-y-1.5 mb-4">
        {bullets.map((b, i) => (
          <li
            key={i}
            className="flex items-center justify-between gap-2 text-xs py-1.5 px-2.5 rounded-lg bg-muted/40 border border-border"
          >
            <span className="text-muted-foreground">{b.label}</span>
            <span
              className={`font-bold tabular-nums ${
                b.tone === "critical" ? "text-rose-600" :
                b.tone === "warning"  ? "text-amber-600" :
                b.tone === "positive" ? "text-emerald-600" : "text-foreground"
              }`}
            >
              {b.value}
            </span>
          </li>
        ))}
      </ul>

      {/* Root cause */}
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 mb-3">
        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-amber-700">
          <AlertTriangle className="h-3 w-3" /> Likely root cause
        </div>
        <p className="text-xs leading-snug mt-1">{cause}</p>
      </div>

      {/* Recommendation */}
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-3 mt-auto">
        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-700">
          <Lightbulb className="h-3 w-3" /> Recommended action
        </div>
        <p className="text-xs leading-snug mt-1">{recommendation}</p>
        <button className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-bold text-emerald-700 hover:gap-2.5 transition-all">
          Assign to store manager <ArrowRight className="h-3 w-3" />
        </button>
      </div>

      {/* Target marker */}
      <div className="mt-3 flex items-center justify-between text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Target className="h-3 w-3" /> Target stage uplift
        </span>
        <span className="font-bold tabular-nums text-foreground">+8.0 pts in 7 days</span>
      </div>
    </div>
  );
}
