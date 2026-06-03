import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { FiltersBar } from "@/components/heatmap/FiltersBar";
import { StoreLayoutHeatmap } from "@/components/heatmap/StoreLayoutHeatmap";
import { InsightsPanel } from "@/components/heatmap/InsightsPanel";
import { ZoneRankingCard } from "@/components/heatmap/ZoneRankingCard";
import { api } from "@/lib/store-api";
import { ZONE_ANALYTICS, scoreTier, type DateRange, type PerformanceFilter, type ZoneId } from "@/lib/store-layout";
import { AppShell, LiveBadge, PageHeader } from "@/components/layout/AppShell";

export const Route = createFileRoute("/heatmap")({
  head: () => ({
    meta: [
      { title: "Zone Heatmap · VisionRetail AI" },
      { name: "description", content: "Real-time store-floor heatmap and AI insights — engagement, conversion, and anomalies per zone." },
      { property: "og:title", content: "Zone Heatmap · VisionRetail AI" },
      { property: "og:description", content: "Real-time store-floor heatmap and AI insights per zone." },
    ],
  }),
  component: HeatmapPage,
});

function HeatmapPage() {
  const [storeId, setStoreId] = useState("STORE_BLR_002");
  const [dateRange, setDateRange] = useState<DateRange>("today");
  const [perf, setPerf] = useState<PerformanceFilter>("all");
  const [zoneFilter, setZoneFilter] = useState<string>("all");

  const zonesQuery = useQuery({
    queryKey: ["zones", storeId],
    queryFn: () => api.zones(storeId),
    refetchInterval: 15000,
  });

  const dataConfidence = zonesQuery.data?.data_confidence ?? true;

  const zones = useMemo(() => {
    if (!zonesQuery.data?.zones) return ZONE_ANALYTICS;
    const rawZones = zonesQuery.data.zones;

    return rawZones.map((rz) => {
      const matchedStatic = ZONE_ANALYTICS.find(
        (sz) => sz.name.toLowerCase() === (rz.zone_name || "").toLowerCase() || sz.zone_id.toLowerCase() === (rz.zone_id || "").toLowerCase(),
      );

      const zoneId = (matchedStatic?.zone_id ?? rz.zone_id.toUpperCase()) as ZoneId;
      const name = matchedStatic?.name ?? rz.zone_name;

      const score = Math.min(100, Math.round((rz.avg_dwell_seconds / 500) * 50 + (rz.visitor_count / 1000) * 50)) || 50;

      return {
        zone_id: zoneId,
        name: name,
        avg_dwell: Math.round(rz.avg_dwell_seconds),
        visitors: rz.visitor_count,
        conversion_rate: matchedStatic?.conversion_rate ?? 20,
        trend: matchedStatic?.trend ?? 5.0,
        score: score,
        peak_hour: matchedStatic?.peak_hour ?? "18:00",
        anomalies: matchedStatic?.anomalies ?? 0,
        zone_enter_count: (rz as { zone_enter_count?: number }).zone_enter_count ?? 0,
        zone_exit_count: (rz as { zone_exit_count?: number }).zone_exit_count ?? 0,
      };
    });
  }, [zonesQuery.data]);

  const rankings = useMemo(
    () => [...zones].sort((a, b) => b.score - a.score).map((z, i) => ({ id: z.zone_id, rank: i + 1 })),
    [zones],
  );

  const highlightedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const z of zones) {
      const tier = scoreTier(z.score);
      const passesPerf = perf === "all" || tier === perf;
      const passesZone = zoneFilter === "all" || z.zone_id === zoneFilter;
      if (passesPerf && passesZone) ids.add(z.zone_id);
    }
    return ids;
  }, [zones, perf, zoneFilter]);

  return (
    <AppShell
      pageLabel="Zone Heatmap"
      storeId={storeId}
      status={
        <>
          {!dataConfidence && (
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-warn/30 bg-warn/10 text-warn">
              <AlertTriangle className="h-3.5 w-3.5" />
              <span className="text-xs font-semibold tracking-wider uppercase">Low data</span>
            </div>
          )}
          <LiveBadge live={dataConfidence} label={dataConfidence ? "Live" : "Low Confidence"} />
        </>
      }
    >
      <PageHeader
        title={
          <>
            Heatmap <span className="text-gradient">Analytics</span>
          </>
        }
        subtitle="Composite performance score per zone — engagement, conversion, anomalies, trend."
        trailing={
          <div className="text-xs text-muted-foreground tabular-nums px-3 py-1.5 rounded-lg bg-muted/50 border border-border/60">
            {zones.length} zones · {rankings.length} ranked
          </div>
        }
      />

      <div className="space-y-5">
        <FiltersBar
          storeId={storeId}
          dateRange={dateRange}
          perf={perf}
          zoneFilter={zoneFilter}
          onChange={(p) => {
            if (p.storeId !== undefined) setStoreId(p.storeId);
            if (p.dateRange !== undefined) setDateRange(p.dateRange);
            if (p.perf !== undefined) setPerf(p.perf);
            if (p.zoneFilter !== undefined) setZoneFilter(p.zoneFilter);
          }}
        />

        <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5 items-start">
          <StoreLayoutHeatmap
            zones={zones}
            rankings={rankings}
            highlightedIds={perf === "all" && zoneFilter === "all" ? undefined : highlightedIds}
          />

          <aside className="space-y-5">
            <InsightsPanel zones={zones} />
            <ZoneRankingCard zones={zones} variant="top" />
            <ZoneRankingCard zones={zones} variant="bottom" />
          </aside>
        </div>
      </div>
    </AppShell>
  );
}
