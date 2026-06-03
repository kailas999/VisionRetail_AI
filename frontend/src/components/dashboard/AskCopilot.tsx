import { useState } from "react";
import { api } from "@/lib/store-api";
import type { CopilotResponse } from "@/services/Api";
import { Send, Bot, Sparkles, Database, AlertCircle, Loader2, Target, Info } from "lucide-react";

interface Props {
  storeId?: string;
}

const SUGGESTED_QUESTIONS = [
  "Why is the conversion rate dropping today?",
  "Which zone is performing the best?",
  "Are there any anomalies I should investigate?",
];

export function AskCopilot({ storeId = "STORE_BLR_002" }: Props) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<CopilotResponse | null>(null);

  const handleSubmit = async (e?: React.FormEvent, presetQuery?: string) => {
    if (e) e.preventDefault();
    const questionToAsk = presetQuery || query;
    if (!questionToAsk.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    // Provide query input UX feedback if clicked from suggested
    if (presetQuery) setQuery(presetQuery);

    try {
      const res = await api.copilot(storeId, questionToAsk);
      setResponse(res);
    } catch (err: any) {
      setError(err.message || "Failed to contact Copilot. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="surface-elevated p-5 rounded-2xl relative overflow-hidden flex flex-col h-full">
      {/* Background glow */}
      <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="p-1.5 rounded-md bg-primary/10 border border-primary/20">
          <Bot className="h-4 w-4 text-primary" />
        </div>
        <div>
          <h3 className="font-semibold text-[13px] text-foreground uppercase tracking-widest">
            Ask Store Copilot
          </h3>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            Powered by GPT-5.2 — Grounded in real store data
          </p>
        </div>
      </div>

      {/* Suggested Questions (only show if no response and not loading) */}
      {!response && !loading && (
        <div className="mb-4 flex flex-wrap gap-2">
          {SUGGESTED_QUESTIONS.map((sq, idx) => (
            <button
              key={idx}
              onClick={() => handleSubmit(undefined, sq)}
              className="text-[11px] bg-muted/30 hover:bg-muted/60 border border-border/50 rounded-full px-3 py-1.5 transition-colors text-foreground/80 flex items-center gap-1.5"
            >
              <Sparkles className="h-3 w-3 text-primary/70" />
              {sq}
            </button>
          ))}
        </div>
      )}

      {/* Input Form */}
      <form onSubmit={handleSubmit} className="relative mt-auto">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask anything about the store's performance..."
          className="w-full bg-background border border-border/60 rounded-xl pl-4 pr-12 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 transition-all placeholder:text-muted-foreground/60"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </button>
      </form>

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-3 rounded-lg bg-critical/10 border border-critical/20 flex items-start gap-2 text-critical text-sm">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Response Display */}
      {response && (
        <div className="mt-5 space-y-4 border-t border-border/40 pt-4 animate-in fade-in slide-in-from-bottom-2">
          {/* Status Badges */}
          <div className="flex items-center gap-2">
            {response.insufficient_data ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-warn/10 border border-warn/20 text-warn text-[10px] font-bold uppercase tracking-wider">
                <AlertCircle className="h-3 w-3" /> Insufficient Data
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-success/10 border border-success/20 text-success text-[10px] font-bold uppercase tracking-wider">
                <Target className="h-3 w-3" /> Data Grounded
              </span>
            )}
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Confidence: {(response.confidence * 100).toFixed(0)}%
            </span>
          </div>

          {/* Conclusion */}
          <div className="bg-primary/5 border border-primary/10 rounded-lg p-4">
            <h4 className="text-[10px] uppercase font-bold text-primary mb-2 flex items-center gap-1.5">
              <Sparkles className="h-3 w-3" /> Copilot Answer
            </h4>
            <p className="text-sm font-medium leading-relaxed text-foreground/90 whitespace-pre-wrap">
              {response.conclusion}
            </p>
          </div>

          {/* Observations & Evidence */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-muted/20 border border-border/50 rounded-lg p-3">
              <h4 className="text-[10px] uppercase font-bold text-muted-foreground mb-2 flex items-center gap-1.5">
                <Info className="h-3 w-3" /> Observations
              </h4>
              <ul className="space-y-1.5 text-xs text-foreground/80 list-disc pl-4">
                {response.observations.map((obs, i) => (
                  <li key={i} className="leading-snug">
                    {obs}
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-muted/20 border border-border/50 rounded-lg p-3">
              <h4 className="text-[10px] uppercase font-bold text-muted-foreground mb-2 flex items-center gap-1.5">
                <Database className="h-3 w-3" /> Retrieved Evidence
              </h4>
              {response.evidence.length === 0 ? (
                <div className="text-xs text-muted-foreground/60 italic">No direct evidence retrieved.</div>
              ) : (
                <div className="space-y-2">
                  {response.evidence.map((ev, i) => (
                    <div key={i} className="text-[11px] bg-background/50 border border-border/30 rounded p-2">
                      <div className="font-semibold text-foreground">{ev.metric}</div>
                      <div className="text-muted-foreground mt-0.5 line-clamp-2" title={ev.context}>{ev.context}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
