/** Public app settings — sourced from root `.env` VITE_* vars (see vite envDir). */

function env(key: string, fallback: string): string {
  const value = import.meta.env[key];
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

function envNum(key: string, fallback: number): number {
  const parsed = Number(env(key, String(fallback)));
  return Number.isFinite(parsed) ? parsed : fallback;
}

export const appConfig = {
  apiBaseUrl: env("VITE_API_BASE_URL", "http://localhost:8000"),
  storeId: env("VITE_DEFAULT_STORE_ID", "STORE_BLR_002"),
  timezone: env("VITE_DEFAULT_TIMEZONE", "Asia/Kolkata"),
  storeName: env("VITE_STORE_NAME", "Purplle Bangalore South"),
  zoneCount: envNum("VITE_STORE_ZONE_COUNT", 6),
  aiModel: env("VITE_OPENAI_MODEL", "gpt-5.2"),
  yoloModel: env("VITE_YOLO_MODEL", "yolov8m.pt"),
  yoloConfidence: envNum("VITE_YOLO_CONFIDENCE", 0.35),
  yoloIou: envNum("VITE_YOLO_IOU", 0.45),
  reidThreshold: envNum("VITE_REID_THRESHOLD", 0.65),
  reidReentryWindowMinutes: envNum("VITE_REID_REENTRY_WINDOW_MINUTES", 30),
  staffConfidenceThreshold: envNum("VITE_STAFF_CONFIDENCE_THRESHOLD", 0.75),
  apiPort: env("VITE_API_PORT", "8000"),
  environment: env("VITE_ENVIRONMENT", "production"),
} as const;

export function yoloModelLabel(model = appConfig.yoloModel): string {
  const base = model.replace(/\.pt$/i, "");
  if (/^yolov8/i.test(base)) {
    return base.replace(/^yolo/i, "YOLO");
  }
  return base;
}

export function formatThreshold(value: number): string {
  return value.toFixed(2).replace(/\.?0+$/, "") || "0";
}

export function timezoneShort(tz = appConfig.timezone): string {
  try {
    return (
      new Intl.DateTimeFormat("en-IN", { timeZone: tz, timeZoneName: "short" })
        .formatToParts(new Date())
        .find((p) => p.type === "timeZoneName")?.value ?? tz
    );
  } catch {
    return tz;
  }
}
