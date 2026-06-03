/**
 * Api.ts — Low-level HTTP transport for the VisionRetail backend.
 *
 * Design decisions:
 *   • Zero external deps (no axios) — uses native fetch.
 *   • Every backend endpoint is typed with raw backend response shapes.
 *   • Trace ID forwarding: generates a UUID per request for correlation.
 *   • Configurable base URL via VITE_API_BASE_URL env var.
 *   • Timeout support via AbortController.
 *   • Centralised error class (ApiError) for uniform handling.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Configuration
// ─────────────────────────────────────────────────────────────────────────────

/** Base URL resolves from env → falls back to localhost:8000 for local dev. */
const BASE_URL: string =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_BASE_URL) ||
  "http://localhost:8000";

/** Default timeout per request (ms). */
const DEFAULT_TIMEOUT_MS = 15_000;

// ─────────────────────────────────────────────────────────────────────────────
// Error types
// ─────────────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly body: unknown,
    public readonly traceId?: string,
  ) {
    super(`API ${status} ${statusText}`);
    this.name = "ApiError";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Backend response types (mirrors Pydantic schemas 1:1)
// ─────────────────────────────────────────────────────────────────────────────

/** Per-store feed freshness stat returned by /health */
export interface StoreHealthStat {
  store_id: string;
  last_event_at: string | null;   // ISO UTC timestamp
  lag_seconds: number | null;
  stale_feed: boolean;            // true if lag > 10 min
}

/** GET /health */
export interface HealthResponse {
  status: string;
  database: string;
  version: string;
  environment: string;
  store_stats: StoreHealthStat[];  // per-store feed freshness
}

/** GET /stores/:id/metrics → hourly row */
export interface HourlyMetricsRow {
  hour_bucket: string;          // ISO datetime
  unique_visitors: number;
  conversions: number;
  avg_dwell_seconds: number;
  max_queue_depth: number;
  abandonment_count: number;
  conversion_rate: number;
}

/** GET /stores/:id/metrics */
export interface StoreMetricsResponse {
  store_id: string;
  date: string | null;
  unique_visitors: number;
  staff_count: number;
  conversions: number;
  conversion_rate: number;
  avg_dwell_seconds: number;
  peak_hour: number | null;
  max_queue_depth: number;
  abandonment_count: number;
  reentry_count: number;
  total_revenue: number;
  total_visitors?: number;
  visitors_after_reid?: number;
  entry_count?: number;
  exit_count?: number;
  zone_engagement_count?: number;
  billing_queue_count?: number;
  purchases_count?: number;
  cross_camera_match_rate?: number;
  hourly_breakdown: HourlyMetricsRow[];
}

/** GET /stores/:id/funnel → single stage */
export interface FunnelStageRow {
  stage: string;
  count: number;
  rate: number;
}

/** GET /stores/:id/funnel */
export interface FunnelResponse {
  store_id: string;
  date: string | null;
  stages: FunnelStageRow[];
}

/** GET /stores/:id/heatmap → single zone */
export interface ZoneHeatmapPoint {
  zone_id: string;
  zone_name: string;
  zone_type: string;
  avg_dwell_seconds: number;
  visitor_count: number;
  polygon: number[][];
  intensity: number;
}

/** GET /stores/:id/heatmap */
export interface HeatmapResponse {
  store_id: string;
  date: string | null;
  data_source: string;
  data_confidence: boolean;   // false if fewer than 20 unique sessions in window
  zones: ZoneHeatmapPoint[];
}

/** GET /stores/:id/anomalies → single anomaly */
export interface AnomalyRow {
  anomaly_id: string;
  store_id: string;
  detected_at: string;
  anomaly_type: string;
  /** Backend emits: CRITICAL | HIGH | MEDIUM | WARN */
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "WARN";
  confidence: number;
  metric_value: number;
  baseline_value: number;
  z_score: number;
  affected_zone_id: string | null;
  recommended_action: string;
  is_resolved: boolean;
}

/** GET /stores/:id/anomalies */
export interface AnomaliesResponse {
  store_id: string;
  active_count: number;
  anomalies: AnomalyRow[];
}

/** GET /stores/:id/anomalies/:anomaly_id/insight */
export interface AnomalyInsightResponse {
  anomaly_id: string;
  store_id: string;
  anomaly_type: string;
  root_cause: string;
  business_impact: string;
  recommended_actions: string[];
  priority_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  fallback: boolean;          // true when OpenAI was unavailable
  fallback_reason?: string | null;
  generated_at?: string | null;
}

/** POST /copilot/query request body */
export interface CopilotQueryPayload {
  store_id: string;
  question: string;
  date?: string | null;
  include_context?: boolean;
}

/** POST /copilot/query → evidence item */
export interface CopilotEvidence {
  metric: string;
  value: unknown;
  context: string;
}

/** POST /copilot/query */
export interface CopilotResponse {
  store_id: string;
  question: string;
  observations: string[];
  evidence: CopilotEvidence[];
  conclusion: string;
  confidence: number;
  insufficient_data: boolean;
  trace_id: string;
}

/** POST /events/ingest request body */
export interface EventIngestPayload {
  events: Array<{
    event_id?: string;
    store_id: string;
    camera_id: string;
    visitor_id: string;
    event_type: string;
    timestamp: string;
    zone_id?: string | null;
    dwell_ms?: number;
    is_staff?: boolean;
    confidence?: number;
    metadata?: Record<string, unknown> | null;
  }>;
}

/** POST /events/ingest */
export interface EventIngestResponse {
  ingested: number;
  duplicates: number;
  errors: number;
  trace_id: string;
}

/** GET /stores/:id/event-stream — entrance section */
export interface EventStreamEntrance {
  entry_count: number;
  exit_count: number;
  reentry_count: number;
  current_occupancy: number;
}

/** GET /stores/:id/event-stream — zone section */
export interface EventStreamZone {
  zone_enter_count: number;
  zone_exit_count: number;
  zone_dwell_count: number;
  avg_dwell_seconds: number;
}

/** GET /stores/:id/event-stream — billing section */
export interface EventStreamBilling {
  queue_join_count: number;
  queue_abandon_count: number;
  purchase_count: number;
  queue_abandon_rate: number;
  billing_conversion_rate: number;
}

/** GET /stores/:id/event-stream — re-id section */
export interface EventStreamReid {
  cross_camera_matches: number;
  match_rate: number;
  fragmented_visitors: number;
  avg_confidence: number;
}

/** GET /stores/:id/event-stream */
export interface EventStreamResponse {
  entrance: EventStreamEntrance;
  zone: EventStreamZone;
  billing: EventStreamBilling;
  reid: EventStreamReid;
}

/** GET /stores/:id/ai-summary */
export interface AiStoreSummaryResponse {
  store_id: string;
  executive_summary: string;
  revenue_risk: string;
  top_opportunities: string;
  recommended_actions: string[];
  priority_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  fallback: boolean;
  fallback_reason?: string | null;
  generated_at?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function uuid(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Core fetch wrapper
// ─────────────────────────────────────────────────────────────────────────────

interface FetchOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined | null>;
  timeoutMs?: number;
}

async function request<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { method = "GET", body, params, timeoutMs = DEFAULT_TIMEOUT_MS } = opts;

  // Build URL with query params
  let url = `${BASE_URL}${path}`;
  if (params) {
    const qs = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null) {
        qs.set(key, String(val));
      }
    }
    const qsStr = qs.toString();
    if (qsStr) url += `?${qsStr}`;
  }

  // Abort controller for timeout
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const traceId = uuid();

  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Trace-ID": traceId,
  };

  const init: RequestInit = {
    method,
    headers,
    signal: controller.signal,
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  try {
    const res = await fetch(url, init);

    if (!res.ok) {
      let errorBody: unknown;
      try {
        errorBody = await res.json();
      } catch {
        errorBody = await res.text();
      }
      throw new ApiError(
        res.status,
        res.statusText,
        errorBody,
        res.headers.get("X-Trace-ID") ?? traceId,
      );
    }

    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API client
// ─────────────────────────────────────────────────────────────────────────────

export const ApiClient = {
  // ── Health ──────────────────────────────────────────────────────────────
  /** GET /health */
  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  // ── Root ────────────────────────────────────────────────────────────────
  /** GET / */
  root(): Promise<{ service: string; version: string; status: string }> {
    return request("/");
  },

  // ── Metrics ─────────────────────────────────────────────────────────────
  /** GET /stores/{storeId}/metrics?date=YYYY-MM-DD */
  metrics(storeId: string, date?: string): Promise<StoreMetricsResponse> {
    return request<StoreMetricsResponse>(`/stores/${storeId}/metrics`, {
      params: { date },
    });
  },

  /** GET /stores/{storeId}/ai-summary */
  aiSummary(storeId: string): Promise<AiStoreSummaryResponse> {
    return request<AiStoreSummaryResponse>(`/stores/${storeId}/ai-summary`, {
      timeoutMs: 35_000,
    });
  },

  // ── Event Stream ────────────────────────────────────────────────────────────
  /** GET /stores/{storeId}/event-stream?date=YYYY-MM-DD */
  eventStream(storeId: string, date?: string): Promise<EventStreamResponse> {
    return request<EventStreamResponse>(`/stores/${storeId}/event-stream`, {
      params: { date },
    });
  },

  // ── Funnel ──────────────────────────────────────────────────────────────
  /** GET /stores/{storeId}/funnel?date=YYYY-MM-DD */
  funnel(storeId: string, date?: string): Promise<FunnelResponse> {
    return request<FunnelResponse>(`/stores/${storeId}/funnel`, {
      params: { date },
    });
  },

  // ── Heatmap ─────────────────────────────────────────────────────────────
  /** GET /stores/{storeId}/heatmap?date=YYYY-MM-DD */
  heatmap(storeId: string, date?: string): Promise<HeatmapResponse> {
    return request<HeatmapResponse>(`/stores/${storeId}/heatmap`, {
      params: { date },
    });
  },

  // ── Anomalies ───────────────────────────────────────────────────────────
  /** GET /stores/{storeId}/anomalies */
  anomalies(storeId: string): Promise<AnomaliesResponse> {
    return request<AnomaliesResponse>(`/stores/${storeId}/anomalies`);
  },

  /** GET /stores/{storeId}/anomalies/{anomalyId}/insight */
  insightForAnomaly(storeId: string, anomalyId: string): Promise<AnomalyInsightResponse> {
    return request<AnomalyInsightResponse>(`/stores/${storeId}/anomalies/${anomalyId}/insight`, {
      timeoutMs: 35_000, // GPT-5.2 can take up to ~30 s on first call
    });
  },

  // ── Copilot ─────────────────────────────────────────────────────────────
  /** POST /copilot/query */
  copilotQuery(payload: CopilotQueryPayload): Promise<CopilotResponse> {
    return request<CopilotResponse>("/copilot/query", {
      method: "POST",
      body: payload,
    });
  },

  // ── Event Ingestion ─────────────────────────────────────────────────────
  /** POST /events/ingest */
  ingestEvents(payload: EventIngestPayload): Promise<EventIngestResponse> {
    return request<EventIngestResponse>("/events/ingest", {
      method: "POST",
      body: payload,
    });
  },
} as const;

export default ApiClient;