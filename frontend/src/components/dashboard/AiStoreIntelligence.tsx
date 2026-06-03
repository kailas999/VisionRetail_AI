import { useEffect, useState } from "react";
import { api, type AiStoreSummaryResponse } from "@/lib/store-api";
import { Sparkles, TrendingUp, AlertCircle, CheckCircle2, ChevronRight, Activity, DollarSign, Target } from "lucide-react";

interface Props {
  storeId?: string;
}

export function AiStoreIntelligence({ storeId = "STORE_BLR_002" }: Props) {
  const [summary, setSummary] = useState<AiStoreSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const fetchSummary = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.aiSummary(storeId);
        if (mounted) setSummary(data);
      } catch (err: any) {
        if (mounted) setError(err.message || "Failed to load AI Intelligence Summary");
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchSummary();
    return () => { mounted = false; };
  }, [storeId]);

  if (loading) {
    return (
      <div className="surface-elevated p-5 rounded-2xl animate-pulse min-h-[220px]">
        <div className="h-5 w-48 bg-muted rounded mb-6"></div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="h-24 bg-muted/50 rounded-xl md:col-span-2"></div>
          <div className="h-24 bg-muted/50 rounded-xl"></div>
          <div className="h-24 bg-muted/50 rounded-xl"></div>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="surface-elevated p-5 rounded-2xl min-h-[220px] flex flex-col items-center justify-center text-center">
        <AlertCircle className="h-8 w-8 text-muted-foreground mb-3" />
        <p className="text-sm font-medium text-foreground">AI Intelligence Unavailable</p>
        <p className="text-xs text-muted-foreground mt-1 max-w-sm">{error || "Failed to generate summary"}</p>
      </div>
    );
  }

  return (
    <div className="surface-elevated p-5 rounded-2xl relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />
      
      <div className="relative z-10">
        {/* Header */}
        <div className="flex items-center justify-between mb-5 border-b border-border/40 pb-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-primary/10 border border-primary/20">
              <Sparkles className="h-4 w-4 text-primary" />
            </div>
            <h3 className="font-semibold text-[13px] text-foreground uppercase tracking-widest">
              AI Store Intelligence
            </h3>
          </div>
          
          <div className="flex items-center gap-2">
            {summary.fallback ? (
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-warn/10 text-warn border border-warn/20">
                Rule-Based Mode
              </span>
            ) : (
              <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20 flex items-center gap-1">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-primary"></span>
                </span>
                GPT-5.2 Powered
              </span>
            )}
            <span className="text-[10px] text-muted-foreground uppercase font-medium">
              Priority: <span className={`font-bold ${summary.priority_level === 'HIGH' || summary.priority_level === 'CRITICAL' ? 'text-critical' : summary.priority_level === 'MEDIUM' ? 'text-warn' : 'text-success'}`}>{summary.priority_level}</span>
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Main Executive Summary */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground mb-1.5 flex items-center gap-1.5">
                <Activity className="h-3 w-3" />
                Store Summary
              </div>
              <p className="text-sm font-medium leading-relaxed text-foreground/90">
                {summary.executive_summary}
              </p>
            </div>
            
            <div className="mt-auto pt-4 border-t border-border/40">
              <div className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground mb-1.5 flex items-center gap-1.5">
                <DollarSign className="h-3 w-3" />
                Revenue Impact
              </div>
              <p className="text-xs text-foreground/80 leading-snug">
                {summary.revenue_risk}
              </p>
            </div>
          </div>

          {/* Opportunities and Recommendations */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Top Opportunities */}
            <div className="bg-muted/30 border border-border/50 rounded-lg p-4 flex flex-col">
              <div className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground mb-3 flex items-center gap-1.5">
                <TrendingUp className="h-3 w-3 text-success" />
                Top Opportunities
              </div>
              <p className="text-xs text-foreground/80 leading-relaxed">
                {summary.top_opportunities}
              </p>
            </div>

            {/* Recommended Actions */}
            <div className="bg-muted/30 border border-border/50 rounded-lg p-4 flex flex-col">
              <div className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground mb-3 flex items-center gap-1.5">
                <Target className="h-3 w-3 text-primary" />
                Recommended Actions
              </div>
              <ul className="space-y-2">
                {summary.recommended_actions.map((action, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs text-foreground/80 leading-snug">
                    <CheckCircle2 className="h-3.5 w-3.5 text-primary/70 shrink-0 mt-0.5" />
                    <span>{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
