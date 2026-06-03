import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, TrendingUp, Users } from "lucide-react";
import { api, DEFAULT_STORE_ID } from "@/lib/store-api";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { VisitorsChart } from "@/components/dashboard/VisitorsChart";
import { AiStoreIntelligence } from "@/components/dashboard/AiStoreIntelligence";
import { FunnelView } from "@/components/dashboard/FunnelView";
import { ZoneHeatmap } from "@/components/dashboard/ZoneHeatmap";
import { AnomaliesFeed } from "@/components/dashboard/AnomaliesFeed";
import { OfflineBanner } from "@/components/dashboard/OfflineBanner";
import { StaleFeedPanel, StaleFeedBanner } from "@/components/dashboard/StaleFeedPanel";
import { EventIntelligenceSection } from "@/components/dashboard/EventIntelligenceSection";
import { AskCopilot } from "@/components/dashboard/AskCopilot";
import { AppShell, LiveBadge, PageHeader } from "@/components/layout/AppShell";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Live Dashboard · VisionRetail AI" },
      { name: "description", content: "Real-time retail intelligence powered by CCTV analytics — conversion, dwell time, queue depth, and live anomalies." },
      { property: "og:title", content: "Live Dashboard · VisionRetail AI" },
      { property: "og:description", content: "Real-time retail intelligence powered by CCTV analytics." },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  const storeId = DEFAULT_STORE_ID;
  const [now, setNow] = useState<string>("");
  useEffect(() => {
    const tick = () => setNow(new Date().toLocaleTimeString());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const metrics = useQuery({ queryKey: ["metrics", storeId], queryFn: () => api.metrics(storeId), refetchInterval: 5000 });
  const funnel = useQuery({ queryKey: ["funnel", storeId], queryFn: () => api.funnel(storeId), refetchInterval: 5000 });
  const anomalies = useQuery({ queryKey: ["anomalies", storeId], queryFn: () => api.anomalies(storeId), refetchInterval: 5000 });
  const zones = useQuery({ queryKey: ["zones", storeId], queryFn: () => api.zones(storeId), refetchInterval: 5000 });
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.health(), refetchInterval: 5000 });

  const m = metrics.data;
  const isLive = health.data?.status === "ok";
  const storeStats = health.data?.store_stats ?? [];
  const dataConfidence = zones.data?.data_confidence ?? true;

  return (
    <AppShell
      pageLabel="Live Dashboard"
      storeId={storeId}
      status={<LiveBadge live={isLive} />}
    >
      <PageHeader
        title={
          <>
            Live <span className="text-gradient">Overview</span>
          </>
        }
        subtitle="Real-time signals from CCTV detections, aggregated into business metrics."
        trailing={
          <div className="chip tabular-nums">
            Last sync · <span className="text-foreground font-semibold">{now || "—"}</span>
          </div>
        }
      />

      <div className="space-y-6">
        {metrics.data === null && <OfflineBanner />}
        {storeStats.length > 0 && <StaleFeedBanner storeStats={storeStats} />}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard label="Unique Visitors" value={m?.unique_visitors ?? 0} icon={Users} accent="primary" delta={{ value: 12.4, positive: true }} />
          <MetricCard label="Conversion Rate" value={(m?.conversion_rate ?? 0) * 100} icon={TrendingUp} suffix="%" decimals={1} accent="teal" delta={{ value: 2.1, positive: true }} />
          <MetricCard label="Avg Dwell Time" value={m?.avg_dwell_seconds ?? 0} icon={Clock} suffix="s" accent="primary" delta={{ value: 3.6, positive: false }} />
          <MetricCard label="Max Queue Depth" value={m?.max_queue_depth ?? 0} icon={Activity} accent="warn" delta={{ value: 18.0, positive: false }} />
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { label: "Total Visitors", value: m?.total_visitors ?? 0, highlight: false },
            { label: "Unique Visitors", value: m?.unique_visitors ?? 0, highlight: false },
            { label: "After Re-ID", value: m?.visitors_after_reid ?? 0, highlight: true },
            { label: "Match Rate", value: `${((m?.cross_camera_match_rate ?? 0) * 100).toFixed(1)}%`, highlight: "success" as const },
            { label: "Entry / Exit / Reentry", value: `${m?.entry_count ?? 0} / ${m?.exit_count ?? 0} / ${m?.reentry_count ?? 0}`, small: true },
            { label: "Engage / Queue / Purchases", value: `${m?.zone_engagement_count ?? 0} / ${m?.billing_queue_count ?? 0} / ${m?.purchases_count ?? 0}`, small: true },
          ].map((stat) => (
            <div key={stat.label} className="stat-pill flex flex-col justify-between gap-2">
              <span className="section-label">{stat.label}</span>
              <span
                className={`font-mono font-bold leading-none tabular-nums ${
                  stat.small ? "text-[13px]" : "text-xl"
                } ${
                  stat.highlight === "success"
                    ? "text-success"
                    : stat.highlight
                      ? "text-primary"
                      : "text-foreground"
                }`}
              >
                {stat.value}
              </span>
            </div>
          ))}
        </div>

        <EventIntelligenceSection storeId={storeId} />

        {storeStats.length > 0 && <StaleFeedPanel storeStats={storeStats} />}

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-2">
            <VisitorsChart data={m?.hourly_breakdown ?? []} />
          </div>
          <div>
            <AnomaliesFeed anomalies={anomalies.data?.anomalies ?? []} storeId={storeId} />
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div className="xl:col-span-8">
            <AiStoreIntelligence storeId={storeId} />
          </div>
          <div className="xl:col-span-4">
            <AskCopilot storeId={storeId} />
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <div className="xl:col-span-1">
            <FunnelView stages={funnel.data?.stages ?? []} />
          </div>
          <div className="xl:col-span-2">
            <ZoneHeatmap zones={zones.data?.zones ?? []} dataConfidence={dataConfidence} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
