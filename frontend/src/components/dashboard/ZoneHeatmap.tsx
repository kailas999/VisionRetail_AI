import { AlertTriangle } from "lucide-react";
import type { ZoneAnalytics } from "@/lib/store-api";

interface Props {
  zones: ZoneAnalytics[];
  dataConfidence?: boolean;  // false = <20 sessions → low-confidence notice
}

function heat(value: number, min: number, max: number) {
  const t = (value - min) / Math.max(1, max - min);
  return {
    bg: `linear-gradient(135deg, oklch(${0.30 + t * 0.25} ${0.10 + t * 0.15} ${300 - t * 120}) 0%, oklch(${0.40 + t * 0.30} ${0.15 + t * 0.10} ${300 - t * 130}) 100%)`,
    glow: t > 0.7 ? "0 0 32px oklch(0.78 0.16 180 / 0.45)" : t > 0.4 ? "0 0 18px oklch(0.58 0.24 300 / 0.35)" : "none",
    intensity: t,
  };
}

export function ZoneHeatmap({ zones, dataConfidence = true }: Props) {
  const values = zones.map(z => z.avg_dwell_seconds);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);

  return (
    <div className="surface-elevated rounded-2xl p-6 h-full">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="text-lg font-semibold">Zone Heatmap</h3>
          <p className="text-xs text-muted-foreground mt-1">Color-coded by avg dwell time</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          {/* data_confidence badge — shown when backend flags < 20 sessions */}
          {!dataConfidence && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-warn/10 border border-warn/30 text-warn">
              <AlertTriangle className="h-3 w-3 shrink-0" />
              <span className="text-[10px] font-semibold tracking-wider uppercase">Low data — indicative only</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
            <span>Low</span>
            <span className="h-2 w-24 rounded-full" style={{ background: "linear-gradient(90deg, oklch(0.30 0.10 300), oklch(0.78 0.16 180))" }} />
            <span>High</span>
          </div>
        </div>
      </div>

      {zones.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-sm">
          <span className="text-3xl mb-3">🗺️</span>
          No zone data available for today.
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {zones.map(z => {
            const h = heat(z.avg_dwell_seconds, min, max);
            return (
              <div
                key={z.zone_id || z.zone}
                className="relative rounded-xl p-4 border border-border/60 card-lift overflow-hidden"
                style={{ background: h.bg, boxShadow: h.glow }}
              >
                {/* Intensity bar at top */}
                <div
                  className="absolute top-0 left-0 right-0 h-0.5 rounded-t-xl opacity-70"
                  style={{ background: `oklch(0.90 0.18 ${180 - h.intensity * 120} / ${0.4 + h.intensity * 0.5})` }}
                />
                <div className="text-sm font-semibold text-white/95 truncate">{z.zone_name || z.zone}</div>
                <div className="mt-3 text-2xl font-bold tabular-nums text-white">
                  {Math.round(z.avg_dwell_seconds)}s
                </div>
                <div className="text-[11px] text-white/70 mt-0.5">
                  {z.visitor_count.toLocaleString()} visitors
                </div>
                {/* Intensity pill */}
                <div className="absolute top-3 right-3">
                  <span className="text-[9px] font-bold tracking-wider text-white/60 uppercase">
                    {h.intensity > 0.7 ? "🔥 Hot" : h.intensity > 0.4 ? "Warm" : "Cool"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
