import { useState } from "react";
import { ZoneTile } from "./ZoneTile";
import { ZoneTooltip } from "./ZoneTooltip";
import { STORE_LAYOUT, type ZoneAnalyticsRich } from "@/lib/store-layout";

interface Props {
  zones: ZoneAnalyticsRich[];
  rankings: { id: string; rank: number }[];
  highlightedIds?: Set<string>; // if provided, only these are full-opacity
}

export function StoreLayoutHeatmap({ zones, rankings, highlightedIds }: Props) {
  const [hover, setHover] = useState<{ zone: ZoneAnalyticsRich; rect: DOMRect } | null>(null);
  const total = zones.length;

  return (
    <div className="surface-elevated rounded-2xl p-5 md:p-6">
      <div className="flex items-start justify-between mb-4 flex-wrap gap-2">
        <div>
          <h3 className="text-lg font-semibold">Store Layout Heatmap</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Live floor plan colored by composite performance score
          </p>
        </div>
        <Legend />
      </div>

      {/* Floor plan grid — mirrors STORE_LAYOUT positions */}
      <div className="relative rounded-xl bg-muted/30 border border-border p-3">
        {/* Subtle floor grid background */}
        <div
          className="absolute inset-3 rounded-lg pointer-events-none"
          style={{
            backgroundImage:
              "linear-gradient(oklch(0.20 0.03 275 / 0.05) 1px, transparent 1px), linear-gradient(90deg, oklch(0.20 0.03 275 / 0.05) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />

        <div
          className="relative grid gap-2"
          style={{
            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
            gridTemplateRows: "repeat(5, minmax(72px, 1fr))",
          }}
        >
          {STORE_LAYOUT.map((layout) => {
            const zone = zones.find((z) => z.zone_id === layout.zone_id);
            if (!zone) return null;
            const rank = rankings.find((r) => r.id === zone.zone_id)?.rank ?? 0;
            const isActive = hover?.zone.zone_id === zone.zone_id;
            const isDimmed = highlightedIds ? !highlightedIds.has(zone.zone_id) : false;
            return (
              <div
                key={zone.zone_id}
                style={{
                  gridColumn: `${layout.col} / span ${layout.colSpan}`,
                  gridRow: `${6 - layout.row - layout.rowSpan + 1} / span ${layout.rowSpan}`,
                }}
              >
                <ZoneTile
                  zone={zone}
                  rank={rank}
                  total={total}
                  isActive={isActive}
                  isDimmed={isDimmed}
                  onHover={(z, rect) => setHover(z && rect ? { zone: z, rect } : null)}
                />
              </div>
            );
          })}
        </div>

        {/* Storefront label */}
        <div className="mt-3 flex items-center justify-center gap-2 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          <span className="h-px w-12 bg-border" /> Storefront entrance <span className="h-px w-12 bg-border" />
        </div>
      </div>

      {hover && (
        <ZoneTooltip
          zone={hover.zone}
          rect={hover.rect}
          rank={rankings.find((r) => r.id === hover.zone.zone_id)?.rank ?? 0}
          total={total}
        />
      )}
    </div>
  );
}

function Legend() {
  const items = [
    { label: "High", color: "bg-emerald-500" },
    { label: "Medium", color: "bg-amber-500" },
    { label: "Low", color: "bg-rose-500" },
    { label: "Idle", color: "bg-zinc-400" },
  ];
  return (
    <div className="flex items-center gap-3 text-[10px] uppercase tracking-wider text-muted-foreground">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5">
          <span className={`h-2.5 w-2.5 rounded-sm ${i.color}`} /> {i.label}
        </span>
      ))}
    </div>
  );
}
