import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Users, Percent, IndianRupee, AlertOctagon } from "lucide-react";
import { FunnelKpiCard } from "@/components/funnel/FunnelKpiCard";
import { FunnelVisualization } from "@/components/funnel/FunnelVisualization";
import { StageAnalysis } from "@/components/funnel/StageAnalysis";
import { FunnelInsights } from "@/components/funnel/FunnelInsights";
import { ComparisonToggle } from "@/components/funnel/ComparisonToggle";
import { api, DEFAULT_STORE_ID } from "@/lib/store-api";
import {
  FUNNEL_STAGES,
  COMPARISON_SNAPSHOT,
  COMPARE_PERIODS,
  computeKpis,
  type ComparePeriod,
  type FunnelStageRich,
} from "@/lib/funnel-data";
import { AppShell, PageHeader } from "@/components/layout/AppShell";

export const Route = createFileRoute("/funnel")({
  head: () => ({
    meta: [
      { title: "Conversion Funnel Intelligence · VisionRetail AI" },
      { name: "description", content: "Stage-by-stage funnel intelligence — visitors, drop-off, lost revenue, and AI-driven recommendations." },
      { property: "og:title", content: "Conversion Funnel Intelligence" },
      { property: "og:description", content: "Stage-by-stage funnel intelligence with lost-revenue impact." },
    ],
  }),
  component: FunnelPage,
});

function FunnelPage() {
  const [period, setPeriod] = useState<ComparePeriod>("7d");
  const storeId = DEFAULT_STORE_ID;

  const funnelQuery = useQuery({
    queryKey: ["funnel", storeId],
    queryFn: () => api.funnel(storeId),
    refetchInterval: 15000,
  });

  const stages = useMemo(() => {
    if (!funnelQuery.data?.stages) return FUNNEL_STAGES;
    const rawStages = funnelQuery.data.stages;

    const entryCount = rawStages.find((s) => s.stage.toUpperCase() === "ENTRY")?.count ?? 0;
    const engCount = rawStages.find((s) => s.stage.toUpperCase() === "ZONE_ENGAGEMENT" || s.stage.toUpperCase() === "ZONE ENGAGEMENT")?.count ?? 0;
    const billingCount = rawStages.find((s) => s.stage.toUpperCase() === "BILLING_ZONE_REACHED" || s.stage.toUpperCase() === "BILLING ZONE")?.count ?? 0;
    const purchaseCount = rawStages.find((s) => s.stage.toUpperCase() === "CONVERTED")?.count ?? 0;

    const round = (val: number, decimals: number) => {
      const mult = Math.pow(10, decimals);
      return Math.round(val * mult) / mult;
    };

    const mapped: FunnelStageRich[] = [
      {
        id: "ENTRY",
        name: "Entry",
        description: "Customers who walked through the storefront sensor.",
        visitors: entryCount,
        conversion_rate: 100,
        dropoff_rate: 0,
        lost_users: 0,
        trend: 8.4,
        benchmark: 100,
        avg_dwell: 42,
        anomalies: 0,
        status: "healthy",
        revenue_per_visitor: 0,
      },
      {
        id: "ENGAGEMENT",
        name: "Zone Engagement",
        description: "Stopped in at least one merchandised zone for >30s.",
        visitors: engCount,
        conversion_rate: entryCount > 0 ? round((engCount / entryCount) * 100, 1) : 0,
        dropoff_rate: entryCount > 0 ? round(((entryCount - engCount) / entryCount) * 100, 1) : 0,
        lost_users: Math.max(0, entryCount - engCount),
        trend: 2.1,
        benchmark: 72,
        avg_dwell: 287,
        anomalies: 0,
        status: (entryCount > 0 ? engCount / entryCount : 0) >= 0.7 ? "healthy" : (entryCount > 0 ? engCount / entryCount : 0) >= 0.6 ? "watch" : "attention",
        revenue_per_visitor: 0,
      },
      {
        id: "BILLING",
        name: "Billing Zone",
        description: "Reached the checkout queue with intent to purchase.",
        visitors: billingCount,
        conversion_rate: entryCount > 0 ? round((billingCount / entryCount) * 100, 1) : 0,
        dropoff_rate: engCount > 0 ? round(((engCount - billingCount) / engCount) * 100, 1) : 0,
        lost_users: Math.max(0, engCount - billingCount),
        trend: -6.2,
        benchmark: 42,
        avg_dwell: 96,
        anomalies: 1,
        status: (engCount > 0 ? (engCount - billingCount) / engCount : 0) > 0.45 ? "critical" : "attention",
        revenue_per_visitor: 0,
      },
      {
        id: "PURCHASE",
        name: "Purchase",
        description: "Completed transaction at the counter.",
        visitors: purchaseCount,
        conversion_rate: entryCount > 0 ? round((purchaseCount / entryCount) * 100, 1) : 0,
        dropoff_rate: billingCount > 0 ? round(((billingCount - purchaseCount) / billingCount) * 100, 1) : 0,
        lost_users: Math.max(0, billingCount - purchaseCount),
        trend: 1.4,
        benchmark: 28,
        avg_dwell: 0,
        anomalies: 0,
        status: (entryCount > 0 ? purchaseCount / entryCount : 0) >= 0.25 ? "healthy" : "watch",
        revenue_per_visitor: 1650,
      },
    ];
    return mapped;
  }, [funnelQuery.data]);

  const kpis = useMemo(() => computeKpis(stages), [stages]);
  const comparison = COMPARISON_SNAPSHOT[period];
  const periodLabel = COMPARE_PERIODS.find((p) => p.id === period)?.label ?? "";

  return (
    <AppShell
      pageLabel="Conversion Funnel"
      storeId={storeId}
      actions={<ComparisonToggle value={period} onChange={setPeriod} />}
    >
      <PageHeader
        title={
          <>
            Funnel <span className="text-gradient">Intelligence</span>
          </>
        }
        subtitle="Where customers drop off, why, and what revenue is at stake — answered."
      />

      <div className="space-y-5">
        {(() => {
          const entry = stages.find((s) => s.id === "ENTRY")?.visitors || 0;
          const eng = stages.find((s) => s.id === "ENGAGEMENT")?.visitors || 0;
          const bill = stages.find((s) => s.id === "BILLING")?.visitors || 0;
          const pur = stages.find((s) => s.id === "PURCHASE")?.visitors || 0;
          const isValid = pur <= bill && bill <= eng && eng <= entry;

          if (!isValid) {
            return (
              <div className="surface-elevated rounded-xl p-4 flex items-start gap-3 border-critical/30 bg-critical/5">
                <AlertOctagon className="h-5 w-5 text-critical shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-critical">Data Validation Warning</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    The funnel pipeline formula (Purchase ≤ Billing ≤ Engagement ≤ Entry) is violated.
                  </p>
                  <p className="text-xs font-mono bg-muted/50 p-2 rounded-lg mt-2 text-foreground inline-block border border-border/60">
                    {pur} ≤ {bill} ≤ {eng} ≤ {entry}
                  </p>
                </div>
              </div>
            );
          }
          return null;
        })()}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <FunnelKpiCard label="Visitors today" value={kpis.visitors} icon={Users} tone="primary" hint="Storefront entries" />
          <FunnelKpiCard label="Conversion rate" value={kpis.conversion_rate} icon={Percent} suffix="%" decimals={1} tone="teal" hint="Entry → Purchase" />
          <FunnelKpiCard label="Est. revenue lost" value={kpis.lost_revenue} icon={IndianRupee} prefix="₹" tone="critical" hint="Across all leakage" />
          <FunnelKpiCard label="Critical stage" value={kpis.critical_stage.lost_users} icon={AlertOctagon} tone="warn" hint={`${kpis.critical_stage.name} · ${kpis.critical_stage.dropoff_rate}% drop`} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
          <div className="lg:col-span-5">
            <FunnelVisualization stages={stages} comparison={comparison} comparisonLabel={periodLabel} />
          </div>
          <div className="lg:col-span-4">
            <StageAnalysis stages={stages} />
          </div>
          <div className="lg:col-span-3">
            <FunnelInsights stages={stages} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
