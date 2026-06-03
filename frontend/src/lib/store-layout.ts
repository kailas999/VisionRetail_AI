// Real-world store layout: grid positions + rich per-zone analytics.
// Coordinates use a CSS grid (col-start / row-start / spans) so the heatmap
// renders an actual floor plan rather than a uniform grid of cards.

export type ZoneId =
  | "ENTRANCE"
  | "SKINCARE"
  | "MAKEUP"
  | "FRAGRANCE"
  | "HAIRCARE"
  | "WELLNESS"
  | "GIFTING"
  | "BILLING";

export interface ZoneLayout {
  zone_id: ZoneId;
  name: string;
  col: number; // 1-indexed
  row: number;
  colSpan: number;
  rowSpan: number;
}

export interface ZoneAnalyticsRich {
  zone_id: ZoneId;
  name: string;
  avg_dwell: number; // seconds
  visitors: number;
  conversion_rate: number; // 0-100
  trend: number; // % vs previous period (+/-)
  score: number; // 0-100 composite
  peak_hour: string;
  anomalies: number;
  zone_enter_count?: number;
  zone_exit_count?: number;
}

export const STORE_LAYOUT: ZoneLayout[] = [
  // 4 cols × 5 rows. Entrance bottom, billing top, retail floor in the middle.
  { zone_id: "ENTRANCE", name: "Entrance", col: 1, row: 5, colSpan: 4, rowSpan: 1 },
  { zone_id: "SKINCARE", name: "Skincare", col: 1, row: 3, colSpan: 2, rowSpan: 2 },
  { zone_id: "MAKEUP", name: "Makeup", col: 3, row: 3, colSpan: 2, rowSpan: 2 },
  { zone_id: "FRAGRANCE", name: "Fragrance", col: 1, row: 2, colSpan: 1, rowSpan: 1 },
  { zone_id: "HAIRCARE", name: "Haircare", col: 2, row: 2, colSpan: 1, rowSpan: 1 },
  { zone_id: "WELLNESS", name: "Wellness", col: 3, row: 2, colSpan: 1, rowSpan: 1 },
  { zone_id: "GIFTING", name: "Gifting", col: 4, row: 2, colSpan: 1, rowSpan: 1 },
  { zone_id: "BILLING", name: "Billing", col: 1, row: 1, colSpan: 4, rowSpan: 1 },
];

export const ZONE_ANALYTICS: ZoneAnalyticsRich[] = [
  { zone_id: "ENTRANCE", name: "Entrance", avg_dwell: 42, visitors: 1420, conversion_rate: 100, trend: 8.4, score: 95, peak_hour: "18:00", anomalies: 0 },
  { zone_id: "SKINCARE", name: "Skincare", avg_dwell: 412, visitors: 386, conversion_rate: 28, trend: 12.1, score: 89, peak_hour: "17:00", anomalies: 0 },
  { zone_id: "MAKEUP", name: "Makeup", avg_dwell: 521, visitors: 498, conversion_rate: 31, trend: 14.6, score: 94, peak_hour: "19:00", anomalies: 0 },
  { zone_id: "FRAGRANCE", name: "Fragrance", avg_dwell: 287, visitors: 244, conversion_rate: 18, trend: -32.0, score: 48, peak_hour: "16:00", anomalies: 1 },
  { zone_id: "HAIRCARE", name: "Haircare", avg_dwell: 198, visitors: 172, conversion_rate: 14, trend: -4.2, score: 56, peak_hour: "15:00", anomalies: 0 },
  { zone_id: "WELLNESS", name: "Wellness", avg_dwell: 154, visitors: 118, conversion_rate: 9, trend: -24.0, score: 32, peak_hour: "14:00", anomalies: 1 },
  { zone_id: "GIFTING", name: "Gifting", avg_dwell: 233, visitors: 209, conversion_rate: 11, trend: -6.0, score: 44, peak_hour: "18:00", anomalies: 0 },
  { zone_id: "BILLING", name: "Billing", avg_dwell: 96, visitors: 486, conversion_rate: 96, trend: 12.0, score: 78, peak_hour: "19:00", anomalies: 1 },
];

export const STORES = [
  { id: "STORE_BLR_002", name: "Bengaluru · Indiranagar" },
];

export type DateRange = "today" | "7d" | "30d" | "90d";
export const DATE_RANGES: { id: DateRange; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
  { id: "90d", label: "Last 90 days" },
];

export type PerformanceFilter = "all" | "high" | "medium" | "low";
export const PERF_FILTERS: { id: PerformanceFilter; label: string }[] = [
  { id: "all", label: "All zones" },
  { id: "high", label: "High performing" },
  { id: "medium", label: "Medium" },
  { id: "low", label: "Underperforming" },
];

export function scoreTier(score: number): "high" | "medium" | "low" | "idle" {
  if (score === 0) return "idle";
  if (score >= 75) return "high";
  if (score >= 50) return "medium";
  return "low";
}
