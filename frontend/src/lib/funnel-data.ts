// Conversion funnel intelligence — rich mock data with benchmarks,
// trends, revenue impact, and period comparisons.

export type StageId = "ENTRY" | "ENGAGEMENT" | "BILLING" | "PURCHASE";
export type StageStatus = "healthy" | "watch" | "attention" | "critical";

export interface FunnelStageRich {
  id: StageId;
  name: string;
  description: string;
  visitors: number;
  conversion_rate: number;   // % of total entry that reached this stage
  dropoff_rate: number;      // % lost from previous stage
  lost_users: number;        // absolute drop from previous stage
  trend: number;             // % vs comparison period
  benchmark: number;         // industry avg conversion %
  avg_dwell: number;         // seconds
  anomalies: number;
  status: StageStatus;
  revenue_per_visitor: number; // INR ARPU expectation if converted
}

export type ComparePeriod = "yesterday" | "7d" | "30d";

export const COMPARE_PERIODS: { id: ComparePeriod; label: string }[] = [
  { id: "yesterday", label: "Yesterday" },
  { id: "7d", label: "7-day avg" },
  { id: "30d", label: "30-day avg" },
];

// Base funnel (today)
export const FUNNEL_STAGES: FunnelStageRich[] = [
  {
    id: "ENTRY",
    name: "Entry",
    description: "Customers who walked through the storefront sensor.",
    visitors: 1420,
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
    visitors: 982,
    conversion_rate: 69.1,
    dropoff_rate: 30.8,
    lost_users: 438,
    trend: 2.1,
    benchmark: 72,
    avg_dwell: 287,
    anomalies: 0,
    status: "watch",
    revenue_per_visitor: 0,
  },
  {
    id: "BILLING",
    name: "Billing Zone",
    description: "Reached the checkout queue with intent to purchase.",
    visitors: 486,
    conversion_rate: 34.2,
    dropoff_rate: 50.5,
    lost_users: 496,
    trend: -6.2,
    benchmark: 42,
    avg_dwell: 96,
    anomalies: 1,
    status: "critical",
    revenue_per_visitor: 0,
  },
  {
    id: "PURCHASE",
    name: "Purchase",
    description: "Completed transaction at the counter.",
    visitors: 335,
    conversion_rate: 23.6,
    dropoff_rate: 31.1,
    lost_users: 151,
    trend: 1.4,
    benchmark: 28,
    avg_dwell: 0,
    anomalies: 0,
    status: "attention",
    revenue_per_visitor: 1650,
  },
];

// Comparison snapshot: percentage points for each stage's conversion_rate
export const COMPARISON_SNAPSHOT: Record<ComparePeriod, Record<StageId, number>> = {
  yesterday:  { ENTRY: 100, ENGAGEMENT: 67.4, BILLING: 36.1, PURCHASE: 22.8 },
  "7d":       { ENTRY: 100, ENGAGEMENT: 70.2, BILLING: 38.4, PURCHASE: 24.1 },
  "30d":      { ENTRY: 100, ENGAGEMENT: 71.5, BILLING: 40.0, PURCHASE: 25.2 },
};

// ---- Derivations ----

export interface FunnelKpis {
  visitors: number;
  conversion_rate: number;
  lost_revenue: number;
  critical_stage: FunnelStageRich;
  revenue_today: number;
}

export function computeKpis(stages: FunnelStageRich[]): FunnelKpis {
  const entry = stages[0];
  const purchase = stages[stages.length - 1];
  const arpu = purchase.revenue_per_visitor;
  const revenue_today = purchase.visitors * arpu;
  // Lost revenue = (entries that didn't purchase) × ARPU × intent multiplier (0.35)
  const lost_revenue = Math.round((entry.visitors - purchase.visitors) * arpu * 0.35);
  const critical_stage = [...stages].sort((a, b) => b.lost_users - a.lost_users)[0];
  return {
    visitors: entry.visitors,
    conversion_rate: purchase.conversion_rate,
    lost_revenue,
    critical_stage,
    revenue_today,
  };
}

export interface FunnelInsight {
  label: string;
  value: string;
  tone: "neutral" | "warning" | "critical" | "positive";
}

export function buildInsights(stages: FunnelStageRich[]): {
  headline: { stage: FunnelStageRich; lost_revenue: number };
  cause: string;
  recommendation: string;
  bullets: FunnelInsight[];
} {
  const purchase = stages[stages.length - 1];
  const worst = [...stages].sort((a, b) => b.lost_users - a.lost_users)[0];
  const lost_revenue = Math.round(worst.lost_users * purchase.revenue_per_visitor * 0.35);

  const causeMap: Record<StageId, string> = {
    ENTRY: "Low storefront pull-in — passing-by traffic not converting to walk-ins.",
    ENGAGEMENT: "Visual merchandising not capturing attention in the first 30 seconds.",
    BILLING: "Queue congestion at checkout causing pre-purchase abandonment.",
    PURCHASE: "Cart-stage friction — payment failures or upsell fatigue.",
  };
  const recMap: Record<StageId, string> = {
    ENTRY: "Re-position window display and route a greeter to the entrance.",
    ENGAGEMENT: "Refresh end-cap displays and brief floor staff on new launches.",
    BILLING: "Open an additional checkout counter and enable mobile billing.",
    PURCHASE: "Pre-stage bags and remove upsell prompts during peak hours.",
  };

  return {
    headline: { stage: worst, lost_revenue },
    cause: causeMap[worst.id],
    recommendation: recMap[worst.id],
    bullets: [
      { label: "Largest drop-off", value: worst.name, tone: "critical" },
      { label: "Lost visitors", value: worst.lost_users.toLocaleString(), tone: "warning" },
      { label: "Est. revenue lost", value: `₹${lost_revenue.toLocaleString("en-IN")}`, tone: "warning" },
      { label: "Industry benchmark", value: `${worst.benchmark}%`, tone: "neutral" },
      { label: "Current conversion", value: `${worst.conversion_rate}%`, tone: worst.conversion_rate < worst.benchmark ? "critical" : "positive" },
    ],
  };
}

export const STATUS_STYLE: Record<StageStatus, { label: string; dot: string; text: string; bg: string; border: string }> = {
  healthy:   { label: "Healthy",         dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
  watch:     { label: "Monitoring",      dot: "bg-sky-500",     text: "text-sky-700 dark:text-sky-400",     bg: "bg-sky-500/10",     border: "border-sky-500/30" },
  attention: { label: "Needs attention", dot: "bg-amber-500",   text: "text-amber-700 dark:text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/30" },
  critical:  { label: "Critical",        dot: "bg-rose-500",    text: "text-rose-700 dark:text-rose-400",    bg: "bg-rose-500/10",    border: "border-rose-500/30" },
};
