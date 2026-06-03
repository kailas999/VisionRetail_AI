import { AlertCircle, CheckCircle2, Clock, WifiOff } from "lucide-react";
import type { StoreHealthStat } from "@/lib/store-api";

interface Props {
  storeStats: StoreHealthStat[];
}

/**
 * StaleFeedPanel — Live per-store feed health panel.
 * Shows last_event_at, lag, and STALE_FEED warning for each store.
 * Driven by /health store_stats (previously static hardcoded Camera Health Panel).
 */
export function StaleFeedPanel({ storeStats }: Props) {
  if (storeStats.length === 0) return null;

  return (
    <div className="surface p-5 rounded-xl border border-border/50 shadow-sm">
      <h3 className="font-semibold text-sm text-foreground/90 uppercase tracking-wider mb-4 border-b border-border/50 pb-2 flex items-center gap-2">
        <Clock className="h-4 w-4 text-muted-foreground" />
        Feed Health · Per Store
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {storeStats.map((stat) => {
          const isStale = stat.stale_feed;
          return (
            <div
              key={stat.store_id}
              className={`flex flex-col p-3 rounded-lg border transition-colors ${
                isStale
                  ? "bg-critical/5 border-critical/30"
                  : "bg-success/5 border-success/20"
              }`}
            >
              <div className="flex justify-between items-center mb-2">
                <span className="font-mono text-sm font-bold truncate">{stat.store_id}</span>
                {isStale ? (
                  <span className="flex items-center gap-1 text-[10px] bg-critical/15 text-critical px-2 py-0.5 rounded uppercase font-semibold border border-critical/30">
                    <WifiOff className="h-3 w-3" />
                    Stale Feed
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[10px] bg-success/15 text-success px-2 py-0.5 rounded uppercase font-semibold border border-success/25">
                    <CheckCircle2 className="h-3 w-3" />
                    Live
                  </span>
                )}
              </div>
              <div className="text-xs text-muted-foreground flex justify-between mt-1">
                <span>Last Event:</span>
                <span className="font-mono text-foreground">{stat.lag_label}</span>
              </div>
              {stat.lag_seconds !== null && (
                <div className="text-xs text-muted-foreground flex justify-between mt-1">
                  <span>Lag:</span>
                  <span
                    className={`font-mono font-semibold ${
                      isStale ? "text-critical" : stat.lag_seconds > 60 ? "text-warn" : "text-success"
                    }`}
                  >
                    {stat.lag_seconds < 60
                      ? `${Math.round(stat.lag_seconds)}s`
                      : `${Math.round(stat.lag_seconds / 60)}m`}
                  </span>
                </div>
              )}
              {/* Lag progress bar */}
              <div className="mt-2.5 h-1 rounded-full bg-border/40 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${isStale ? "bg-critical" : "bg-success"}`}
                  style={{
                    width: `${Math.min(100, ((stat.lag_seconds ?? 600) / 600) * 100)}%`,
                  }}
                />
              </div>
              <div className="text-[9px] text-muted-foreground/60 mt-1 text-right">
                {isStale ? "⚠ Feed stale — check pipeline" : "Feed healthy"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * StaleFeedBanner — Inline banner when any active store has a stale feed.
 * Shown at the top of the dashboard when health check detects lag > 10min.
 */
export function StaleFeedBanner({ storeStats }: Props) {
  const staleStores = storeStats.filter((s) => s.stale_feed);
  if (staleStores.length === 0) return null;

  return (
    <div className="bg-warn/10 text-warn border border-warn/30 rounded-xl px-4 py-3 flex items-start gap-3">
      <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
      <div>
        <div className="text-sm font-semibold">
          Stale Feed Detected — {staleStores.length} store{staleStores.length > 1 ? "s" : ""}
        </div>
        <div className="text-xs mt-0.5 opacity-80">
          {staleStores.map((s) => s.store_id).join(", ")} · Last event{" "}
          {staleStores.length === 1 ? staleStores[0].lag_label : "varies"}. Metrics may be outdated.
        </div>
      </div>
    </div>
  );
}
