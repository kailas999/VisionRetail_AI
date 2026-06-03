/**
 * AIInsightCard — displays a GPT-5.2 generated anomaly insight.
 *
 * States:
 *  - idle     : "Get AI Insight" button shown
 *  - loading  : shimmer skeleton
 *  - loaded   : root cause / impact / actions / priority
 *  - fallback : same layout but with a "Rule-based" badge
 *  - error    : graceful inline error message
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Sparkles,
  Brain,
  TrendingDown,
  ShieldAlert,
  ListChecks,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { api, DEFAULT_STORE_ID } from "@/lib/store-api";
import type { AnomalyInsight, InsightPriority } from "@/lib/store-api";

// ── Priority badge config ──────────────────────────────────────────────────────
const priorityConfig: Record<
  InsightPriority,
  { label: string; cls: string }
> = {
  LOW: {
    label: "Low",
    cls: "bg-success/10 text-success border-success/30",
  },
  MEDIUM: {
    label: "Medium",
    cls: "bg-warn/10 text-warn border-warn/30",
  },
  HIGH: {
    label: "High",
    cls: "bg-critical/20 text-critical border-critical/30",
  },
  CRITICAL: {
    label: "Critical",
    cls: "bg-critical/30 text-critical border-critical/50",
  },
};

interface Props {
  anomalyId: string;
  storeId?: string;
}

export function AIInsightCard({ anomalyId, storeId = DEFAULT_STORE_ID }: Props) {
  const [enabled, setEnabled] = useState(false);

  const { data, isFetching, isError, refetch } = useQuery<AnomalyInsight | null>({
    queryKey: ["insight", storeId, anomalyId],
    queryFn: () => api.insight(storeId, anomalyId) as Promise<AnomalyInsight | null>,
    enabled,
    staleTime: 14 * 60 * 1000, // 14 min — slightly under 15 min backend TTL
    retry: 1,
  });

  // ── Idle: prompt user to fetch ────────────────────────────────────────────
  if (!enabled) {
    return (
      <button
        id={`ai-insight-btn-${anomalyId}`}
        onClick={() => setEnabled(true)}
        className="ai-insight-trigger w-full mt-3 flex items-center justify-center gap-2 py-2 px-3 rounded-lg border border-primary/25 bg-primary/5 text-primary text-xs font-semibold tracking-wide hover:bg-primary/12 hover:border-primary/45 transition-all duration-200 group"
      >
        <Sparkles className="h-3.5 w-3.5 transition-transform group-hover:scale-110" />
        Get AI Insight
      </button>
    );
  }

  // ── Loading: shimmer skeleton ─────────────────────────────────────────────
  if (isFetching) {
    return (
      <div className="ai-insight-card mt-3 rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-3 animate-pulse">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 rounded-full bg-primary/20" />
          <div className="h-3.5 w-32 rounded-md bg-primary/15" />
          <div className="ml-auto h-5 w-16 rounded-full bg-primary/15" />
        </div>
        <div className="space-y-1.5">
          <div className="h-3 w-full rounded bg-muted/60" />
          <div className="h-3 w-5/6 rounded bg-muted/60" />
        </div>
        <div className="space-y-1.5">
          <div className="h-3 w-full rounded bg-muted/60" />
          <div className="h-3 w-4/6 rounded bg-muted/60" />
        </div>
        <div className="space-y-1">
          <div className="h-3 w-3/4 rounded bg-muted/60" />
          <div className="h-3 w-2/3 rounded bg-muted/60" />
          <div className="h-3 w-1/2 rounded bg-muted/60" />
        </div>
        <p className="text-[10px] text-muted-foreground text-center pt-1">
          Analysing with GPT-5.2…
        </p>
      </div>
    );
  }

  // ── Error: couldn't reach backend at all ──────────────────────────────────
  if (isError || !data) {
    return (
      <div className="ai-insight-card mt-3 rounded-xl border border-warn/30 bg-warn/5 p-3.5 flex items-start gap-2">
        <AlertCircle className="h-4 w-4 text-warn shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-warn">Insight unavailable</p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            Could not reach the AI service. Rule-based recommendations are shown above.
          </p>
        </div>
        <button
          onClick={() => refetch()}
          className="shrink-0 p-1 rounded-md hover:bg-warn/10 transition-colors"
          title="Retry"
        >
          <RefreshCw className="h-3.5 w-3.5 text-warn" />
        </button>
      </div>
    );
  }

  // ── Loaded ─────────────────────────────────────────────────────────────────
  const priority = (data.priority_level ?? "MEDIUM") as InsightPriority;
  const pCfg = priorityConfig[priority] ?? priorityConfig.MEDIUM;

  return (
    <div
      id={`ai-insight-card-${anomalyId}`}
      className="ai-insight-card mt-3 rounded-xl border border-primary/25 bg-gradient-to-br from-primary/5 via-transparent to-teal/5 p-4 space-y-3.5 ai-insight-appear"
    >
      {/* Header */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <Brain className="h-3.5 w-3.5 text-primary" />
          <span className="text-[11px] font-bold tracking-wider uppercase text-primary">
            AI Insight
          </span>
        </div>

        {data.fallback && (
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full border bg-muted/60 text-muted-foreground border-border">
            Rule-based
          </span>
        )}

        <span
          className={`ml-auto inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${pCfg.cls}`}
        >
          <ShieldAlert className="h-3 w-3" />
          {pCfg.label} Priority
        </span>
      </div>

      {/* Root Cause */}
      <div className="space-y-0.5">
        <p className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
          Root Cause
        </p>
        <p className="text-xs text-foreground/90 leading-relaxed">{data.root_cause}</p>
      </div>

      {/* Business Impact */}
      <div className="space-y-0.5">
        <div className="flex items-center gap-1">
          <TrendingDown className="h-3 w-3 text-warn" />
          <p className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
            Business Impact
          </p>
        </div>
        <p className="text-xs text-foreground/90 leading-relaxed">{data.business_impact}</p>
      </div>

      {/* Recommended Actions */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-1">
          <ListChecks className="h-3 w-3 text-success" />
          <p className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">
            Recommended Actions
          </p>
        </div>
        <ol className="space-y-1">
          {data.recommended_actions.map((action, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-foreground/90">
              <span className="shrink-0 mt-px h-4 w-4 rounded-full bg-primary/10 text-primary text-[9px] font-bold grid place-items-center">
                {i + 1}
              </span>
              <span className="leading-relaxed">{action}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-1 border-t border-border/50">
        <span className="text-[9px] text-muted-foreground">
          {data.fallback
            ? "Rule-based fallback · AI unavailable"
            : `GPT-5.2 · cached 15 min`}
        </span>
        <button
          onClick={() => refetch()}
          className="text-[9px] text-muted-foreground flex items-center gap-0.5 hover:text-primary transition-colors"
          title="Refresh insight"
        >
          <RefreshCw className="h-2.5 w-2.5" />
          Refresh
        </button>
      </div>
    </div>
  );
}
