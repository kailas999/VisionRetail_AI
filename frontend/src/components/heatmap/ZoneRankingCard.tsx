import { ArrowDownRight, ArrowUpRight, Trophy, TrendingDown } from "lucide-react";
import type { ZoneAnalyticsRich } from "@/lib/store-layout";

interface Props {
  zones: ZoneAnalyticsRich[];
  variant: "top" | "bottom";
}

export function ZoneRankingCard({ zones, variant }: Props) {
  const Icon = variant === "top" ? Trophy : TrendingDown;
  const sorted = [...zones].sort((a, b) => (variant === "top" ? b.score - a.score : a.score - b.score)).slice(0, 3);
  const titleColor = variant === "top" ? "text-emerald-600" : "text-rose-600";
  const tintBg = variant === "top" ? "bg-emerald-500/10" : "bg-rose-500/10";

  return (
    <div className="surface-elevated rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className={`h-7 w-7 rounded-lg grid place-items-center ${tintBg}`}>
            <Icon className={`h-3.5 w-3.5 ${titleColor}`} />
          </div>
          <h4 className="text-sm font-semibold">{variant === "top" ? "Top 3 Zones" : "Bottom 3 Zones"}</h4>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">By score</span>
      </div>
      <ol className="space-y-2">
        {sorted.map((z, i) => {
          const trendUp = z.trend >= 0;
          return (
            <li
              key={z.zone_id}
              className="flex items-center gap-3 p-2.5 rounded-lg bg-muted/40 border border-border"
            >
              <div className={`h-6 w-6 rounded-md grid place-items-center text-[11px] font-bold ${tintBg} ${titleColor} shrink-0`}>
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold truncate">{z.name}</div>
                <div className="text-[10px] text-muted-foreground">{z.visitors.toLocaleString()} visitors · {z.conversion_rate}% conv</div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm font-bold tabular-nums">{z.score}</div>
                <div className={`text-[10px] font-bold inline-flex items-center justify-end gap-0.5 ${trendUp ? "text-emerald-600" : "text-rose-600"}`}>
                  {trendUp ? <ArrowUpRight className="h-2.5 w-2.5" /> : <ArrowDownRight className="h-2.5 w-2.5" />}
                  {Math.abs(z.trend).toFixed(1)}%
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
