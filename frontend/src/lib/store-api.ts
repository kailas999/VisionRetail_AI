// Store Intelligence API client
// All data fetching for the dashboard flows through this module.
// Uses ApiClient (services/Api.ts) as the HTTP transport layer.

import {
  ApiClient,
  type StoreMetricsResponse,
  type FunnelResponse as BackendFunnelResponse,
  type AnomaliesResponse as BackendAnomaliesResponse,
  type HeatmapResponse,
  type HealthResponse as BackendHealthResponse,
  type AnomalyInsightResponse,
  type StoreHealthStat as BackendStoreHealthStat,
  type EventStreamResponse as BackendEventStreamResponse,
  type AiStoreSummaryResponse as BackendAiStoreSummaryResponse,
} from "@/services/Api";
import { appConfig } from "@/lib/app-config";

export const DEFAULT_STORE_ID = appConfig.storeId;

// Re-export the configured base URL for reference
export { ApiClient } from "@/services/Api";

// ─────────────────────────────────────────────────────────────────────────────
// Frontend-facing types (consumed by components)
// ─────────────────────────────────────────────────────────────────────────────

export interface HourlyPoint {
  hour: string;
  visitors: number;
  conversions: number;
}

export interface StoreMetrics {
  store_id: string;
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
  total_visitors: number;
  visitors_after_reid: number;
  entry_count: number;
  exit_count: number;
  zone_engagement_count: number;
  billing_queue_count: number;
  purchases_count: number;
  cross_camera_match_rate: number;
  hourly_breakdown: HourlyPoint[];
}

export interface FunnelStage {
  stage: string;
  count: number;
  rate: number;
}

export interface FunnelResponse {
  store_id: string;
  stages: FunnelStage[];
}

export type AnomalySeverity = "INFO" | "WARN" | "CRITICAL";

export interface Anomaly {
  id: string;
  severity: AnomalySeverity;
  type: string;
  title: string;
  zone?: string;
  detected_at: string;
  suggested_action: string;
}

export interface AnomaliesResponse {
  store_id: string;
  anomalies: Anomaly[];
}

export type InsightPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface AnomalyInsight {
  anomaly_id: string;
  store_id: string;
  anomaly_type: string;
  root_cause: string;
  business_impact: string;
  recommended_actions: string[];
  priority_level: InsightPriority;
  /** true when OpenAI was unavailable and rule-based fallback was used */
  fallback: boolean;
  fallback_reason?: string | null;
  generated_at?: string | null;
}

export interface ZoneAnalytics {
  zone_id: string;
  zone_name: string;
  zone: string;
  avg_dwell_seconds: number;
  visitor_count: number;
}

export interface ZonesResponse {
  zones: ZoneAnalytics[];
  data_confidence: boolean;   // false = <20 sessions, treat stats as indicative only
}

export interface EventStreamResponse {
  entrance: {
    entry_count: number;
    exit_count: number;
    reentry_count: number;
    current_occupancy: number;
  };
  zone: {
    zone_enter_count: number;
    zone_exit_count: number;
    zone_dwell_count: number;
    avg_dwell_seconds: number;
  };
  billing: {
    queue_join_count: number;
    queue_abandon_count: number;
    purchase_count: number;
    queue_abandon_rate: number;
    billing_conversion_rate: number;
  };
  reid: {
    cross_camera_matches: number;
    match_rate: number;
    fragmented_visitors: number;
    avg_confidence: number;
  };
}

/** Per-store feed freshness stat (from /health store_stats) */
export interface StoreHealthStat {
  store_id: string;
  last_event_at: string | null;
  lag_seconds: number | null;
  stale_feed: boolean;
  /** Derived: human-readable lag label */
  lag_label: string;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  version?: string;
  store_stats: StoreHealthStat[];
}

export interface AiStoreSummaryResponse {
  store_id: string;
  executive_summary: string;
  revenue_risk: string;
  top_opportunities: string;
  recommended_actions: string[];
  priority_level: InsightPriority;
  fallback: boolean;
  fallback_reason?: string | null;
  generated_at?: string | null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Backend → Frontend mappers
// ─────────────────────────────────────────────────────────────────────────────

function mapMetrics(raw: StoreMetricsResponse): StoreMetrics {
  return {
    store_id: raw.store_id,
    unique_visitors: raw.unique_visitors,
    staff_count: raw.staff_count,
    conversions: raw.conversions,
    conversion_rate: raw.conversion_rate,
    avg_dwell_seconds: raw.avg_dwell_seconds,
    peak_hour: raw.peak_hour,
    max_queue_depth: raw.max_queue_depth,
    abandonment_count: raw.abandonment_count,
    reentry_count: raw.reentry_count,
    total_revenue: raw.total_revenue,
    total_visitors: raw.total_visitors ?? raw.unique_visitors,
    visitors_after_reid: raw.visitors_after_reid ?? raw.unique_visitors,
    entry_count: raw.entry_count ?? raw.unique_visitors,
    exit_count: raw.exit_count ?? 0,
    zone_engagement_count: raw.zone_engagement_count ?? 0,
    billing_queue_count: raw.billing_queue_count ?? 0,
    purchases_count: raw.purchases_count ?? raw.conversions,
    cross_camera_match_rate: raw.cross_camera_match_rate ?? 0.0,
    hourly_breakdown: (raw.hourly_breakdown ?? []).map((h) => {
      const d = new Date(h.hour_bucket);
      const hour = `${d.getHours().toString().padStart(2, "0")}:00`;
      return {
        hour,
        visitors: h.unique_visitors,
        conversions: h.conversions,
      };
    }),
  };
}

function mapFunnel(raw: BackendFunnelResponse): FunnelResponse {
  return {
    store_id: raw.store_id,
    stages: raw.stages.map((s) => ({
      stage: formatStageName(s.stage),
      count: s.count,
      rate: s.rate,
    })),
  };
}

function formatStageName(raw: string): string {
  const map: Record<string, string> = {
    ENTRY: "Entry",
    ZONE_ENGAGEMENT: "Zone Engagement",
    BILLING_ZONE_REACHED: "Billing Zone",
    CONVERTED: "Converted",
  };
  return map[raw] ?? raw.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function mapSeverity(raw: string): AnomalySeverity {
  const upper = raw.toUpperCase();
  if (upper === "CRITICAL") return "CRITICAL";
  if (upper === "HIGH" || upper === "MEDIUM") return "WARN";
  return "INFO";
}

function anomalyTitle(a: BackendAnomaliesResponse["anomalies"][number]): string {
  const typeLabel = a.anomaly_type.replace(/_/g, " ");
  if (a.anomaly_type === "DEAD_ZONE") {
    const mins = a.metric_value?.toFixed(0) ?? "?";
    const zone = a.affected_zone_id ? ` · ${a.affected_zone_id}` : "";
    return `Zone inactive for ${mins} min${zone}`;
  }
  if (a.z_score === 0) return `${typeLabel} detected`;
  return `${typeLabel} detected (z = ${a.z_score.toFixed(1)}, ${(a.confidence * 100).toFixed(0)}% confidence)`;
}

function mapAnomalies(raw: BackendAnomaliesResponse): AnomaliesResponse {
  return {
    store_id: raw.store_id,
    anomalies: raw.anomalies.map((a) => ({
      id: a.anomaly_id,
      severity: mapSeverity(a.severity),
      type: a.anomaly_type,
      title: anomalyTitle(a),
      zone: a.affected_zone_id ?? undefined,
      detected_at: a.detected_at,
      suggested_action: a.recommended_action,
    })),
  };
}

function mapHeatmapToZones(raw: HeatmapResponse): ZonesResponse {
  return {
    data_confidence: raw.data_confidence ?? true,
    zones: raw.zones.map((z) => ({
      zone_id: z.zone_id,
      zone_name: z.zone_name,
      zone: z.zone_name,
      avg_dwell_seconds: z.avg_dwell_seconds,
      visitor_count: z.visitor_count,
    })),
  };
}

function lagLabel(lagSeconds: number | null): string {
  if (lagSeconds === null) return "No events";
  if (lagSeconds < 60) return `${Math.round(lagSeconds)}s ago`;
  if (lagSeconds < 3600) return `${Math.round(lagSeconds / 60)}m ago`;
  return `${Math.round(lagSeconds / 3600)}h ago`;
}

function mapHealth(raw: BackendHealthResponse): HealthResponse {
  return {
    status: raw.status === "healthy" ? "ok" : raw.status === "degraded" ? "degraded" : "down",
    version: raw.version,
    store_stats: (raw.store_stats ?? []).map((s) => ({
      store_id: s.store_id,
      last_event_at: s.last_event_at,
      lag_seconds: s.lag_seconds,
      stale_feed: s.stale_feed,
      lag_label: lagLabel(s.lag_seconds),
    })),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Safe fetch wrapper (CF-02: return null on error, no silent fallbacks)
// ─────────────────────────────────────────────────────────────────────────────

async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch (err) {
    console.error("[store-api] Backend API error:", err);
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API — consumed by dashboard components via useQuery
// ─────────────────────────────────────────────────────────────────────────────

export const api = {
  health: () =>
    safeFetch(
      async () => mapHealth(await ApiClient.health()),
    ),

  metrics: (storeId = DEFAULT_STORE_ID, date?: string) =>
    safeFetch(
      async () => mapMetrics(await ApiClient.metrics(storeId, date)),
    ),

  funnel: (storeId = DEFAULT_STORE_ID, date?: string) =>
    safeFetch(
      async () => mapFunnel(await ApiClient.funnel(storeId, date)),
    ),

  anomalies: (storeId = DEFAULT_STORE_ID) =>
    safeFetch(
      async () => mapAnomalies(await ApiClient.anomalies(storeId)),
    ),

  zones: (storeId = DEFAULT_STORE_ID, date?: string) =>
    safeFetch(
      async () => mapHeatmapToZones(await ApiClient.heatmap(storeId, date)),
    ),

  aiSummary: (storeId = DEFAULT_STORE_ID) =>
    safeFetch<BackendAiStoreSummaryResponse>(
      async () => await ApiClient.aiSummary(storeId),
    ),

  /**
   * GET /stores/{storeId}/event-stream
   * Returns aggregated raw-event counts for Entrance, Zone, Billing, Re-ID.
   * Polled every 5 s by EventIntelligenceSection.
   */
  eventStream: (storeId = DEFAULT_STORE_ID, date?: string) =>
    safeFetch<BackendEventStreamResponse>(() =>
      ApiClient.eventStream(storeId, date),
    ),

  copilot: (storeId: string, question: string, date?: string) =>
    ApiClient.copilotQuery({ store_id: storeId, question, date }),

  /**
   * Fetch AI insight for a specific anomaly.
   * Cached 15 min on the backend — safe to call on every anomaly expand.
   * Returns null on network error; components should fall back to rule-based text.
   */
  insight: (storeId: string, anomalyId: string) =>
    safeFetch<AnomalyInsightResponse>(() =>
      ApiClient.insightForAnomaly(storeId, anomalyId),
    ),
};
