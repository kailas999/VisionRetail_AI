import {
  Bot,
  Camera,
  GitBranch,
  LayoutDashboard,
  Map,
  Shield,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { appConfig, formatThreshold, timezoneShort, yoloModelLabel } from "@/lib/app-config";

const { aiModel, storeId, storeName, zoneCount, timezone } = appConfig;
const yolo = yoloModelLabel();
const reid = formatThreshold(appConfig.reidThreshold);
const yoloConf = formatThreshold(appConfig.yoloConfidence);
const staffConf = formatThreshold(appConfig.staffConfidenceThreshold);

/** Scrolling ticker — mirrors `.env` pipeline + stack settings */
export const MARQUEE_ITEMS = [
  `${yolo} · conf ${yoloConf}`,
  "ByteTrack Tracking",
  `OSNet Re-ID · ≥${reid}`,
  `FastAPI :${appConfig.apiPort}`,
  "Conversion Funnel",
  "Zone Heatmaps",
  "Z-Score Anomalies",
  `${aiModel} Copilot`,
];

/** Numbers from `.env` + app architecture */
export const IMPACT_STATS = [
  { value: timezoneShort(), label: "Store timezone", sub: timezone },
  { value: String(zoneCount), label: "Mapped zones", sub: storeName },
  { value: reid, label: "Re-ID threshold", sub: `${appConfig.reidReentryWindowMinutes}m re-entry window` },
  { value: "4", label: "Funnel stages", sub: "Entry → Engage → Billing → Purchase" },
];

export const BENTO_ITEMS: {
  span: string;
  icon: LucideIcon;
  title: string;
  desc: string;
  accent: string;
  to: string;
}[] = [
  {
    span: "md:col-span-2 md:row-span-2",
    icon: LayoutDashboard,
    title: "Live Command Center",
    desc:
      `Monitor ${storeId} in ${timezoneShort()} — visitors, conversion, dwell, queue depth, hourly charts, funnel, heatmap preview, anomalies, ${aiModel} summary, and Ask Copilot on one screen.`,
    accent: "landing-bento-primary",
    to: "/dashboard",
  },
  {
    span: "",
    icon: GitBranch,
    title: "Conversion Funnel",
    desc:
      "Four validated stages: Entry → Zone Engagement → Billing Reached → Converted. Hierarchy is enforced in SQL so counts never break.",
    accent: "landing-bento-teal",
    to: "/funnel",
  },
  {
    span: "",
    icon: Map,
    title: "Zone Heatmaps",
    desc:
      `Dwell and visitor intensity across ${zoneCount} zones on the ${storeName} floor plan — Skincare, Makeup, Haircare, Billing, and entry/exit.`,
    accent: "landing-bento-info",
    to: "/heatmap",
  },
  {
    span: "md:col-span-2",
    icon: Bot,
    title: "AI Store Copilot",
    desc:
      `Ask in plain English. ${aiModel} answers via RAG over live metrics, funnel, and anomalies — never raw video. Rule-based fallback when the model is unavailable.`,
    accent: "landing-bento-violet",
    to: "/dashboard",
  },
  {
    span: "",
    icon: Zap,
    title: "Anomaly Detection",
    desc:
      "Z-score alerts vs a 7-day same-hour baseline: QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE, and TRAFFIC_DROP.",
    accent: "landing-bento-warn",
    to: "/dashboard",
  },
];

export const STEPS = [
  {
    n: "01",
    title: "Detect & track",
    desc:
      `${yolo} (conf ${yoloConf}, IoU ${formatThreshold(appConfig.yoloIou)}) on three cameras. ByteTrack follows each visitor across entry, floor, and billing views.`,
    icon: Camera,
  },
  {
    n: "02",
    title: "Unify & ingest",
    desc:
      `OSNet Re-ID (threshold ${reid}) merges cross-camera identities. Staff flagged above ${staffConf} confidence are excluded. Events batch to PostgreSQL on port ${appConfig.apiPort}.`,
    icon: GitBranch,
  },
  {
    n: "03",
    title: "Analyze & act",
    desc:
      `Metrics, funnels, heatmaps, and z-score anomalies on the dashboard. ${aiModel} summarizes risks and powers Ask Copilot for ${storeId}.`,
    icon: Bot,
  },
];

export const COMPARE = {
  before: {
    title: "Manual retail ops",
    items: [
      "Hand counts at the door",
      "No link between aisle dwell and checkout",
      "Queue issues found after customers leave",
      "CCTV reviewed manually, hours later",
      "Each camera treated as a separate feed",
    ],
  },
  after: {
    title: "VisionRetail AI",
    items: [
      `Automated counts for ${storeId} with staff excluded (≥${staffConf})`,
      `${zoneCount} zone heatmaps tied to the conversion funnel`,
      "Proactive alerts: QUEUE_SPIKE, DEAD_ZONE, and more",
      `${aiModel} insights grounded in PostgreSQL metrics`,
      `OSNet Re-ID (≥${reid}) across CAM_01, CAM_02, and CAM_03`,
    ],
  },
};

export const USE_CASES = [
  {
    quote:
      `The funnel page shows where shoppers drop between zone engagement and billing for ${storeId} — stage counts pulled live from your ingested event stream.`,
    role: "Conversion analysis",
    org: "Funnel Intelligence · /funnel",
    metric: "4-stage validated pipeline",
  },
  {
    quote:
      `Heatmaps rank ${storeName}'s ${zoneCount} zones by dwell and visitors — polygon overlays from store_layout.json, timezone ${timezone}.`,
    role: "Floor optimization",
    org: "Zone Heatmap · /heatmap",
    metric: `${zoneCount} mapped retail zones`,
  },
  {
    quote:
      `Ask Copilot with ${aiModel}: “Why did conversion drop today?” — it retrieves metrics, funnel data, and open anomalies before answering with cited evidence.`,
    role: "AI-assisted ops",
    org: "Ask Copilot · Dashboard",
    metric: `${aiModel} · RAG over live data`,
  },
];

export const FAQ_ITEMS = [
  {
    q: "What does VisionRetail AI actually do?",
    a: `It turns CCTV into structured retail events for store ${storeId} (${storeName}, ${timezone}) — entry, zone dwell, billing queue, and purchase — then aggregates them into dashboards, funnels, heatmaps, anomalies, and ${aiModel} summaries grounded in PostgreSQL.`,
  },
  {
    q: "Which pipeline settings are active?",
    a: `From your environment: ${yolo} with confidence ${yoloConf}, Re-ID threshold ${reid}, re-entry window ${appConfig.reidReentryWindowMinutes} minutes, staff exclusion above ${staffConf}. Three camera roles: CAM_01 (entry/exit), CAM_02 (floor zones), CAM_03 (billing).`,
  },
  {
    q: "How is the conversion funnel calculated?",
    a: "The backend runs a boolean multiplication CTE so Purchase ≤ Billing ≤ Engagement ≤ Entry always holds. Conversion rate = distinct purchasers ÷ distinct entrants, capped at 100%. The funnel page flags any hierarchy violation.",
  },
  {
    q: "How fast does data update?",
    a: `The homepage polls health every 10s and metrics every 15s against API port ${appConfig.apiPort}. The dashboard refreshes metrics every 15s, funnel every 20s, anomalies every 10s, and health every 8s. Stale-feed warnings appear if the last event is older than 10 minutes.`,
  },
  {
    q: "Can I try it without connecting real cameras?",
    a: `Yes. With ${appConfig.environment} config, run docker compose up, seed demo data (seed_data.py), and open the dashboard for ${storeId}. The CV pipeline (pipeline/run.sh) can ingest video clips into POST /events/ingest on :${appConfig.apiPort}.`,
  },
  {
    q: "What anomalies does the system detect?",
    a: `Four types with z-score vs a 7-day same-hour baseline: QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE, and TRAFFIC_DROP. Each can receive a ${aiModel} root-cause insight with rule-based fallback when the model is offline.`,
  },
];

export const MODULE_LINKS = [
  {
    icon: LayoutDashboard,
    label: "Live Dashboard",
    desc: `KPIs for ${storeId} · charts · funnel · heatmap · anomalies · ${aiModel}`,
    to: "/dashboard",
    c: "text-primary",
  },
  {
    icon: GitBranch,
    label: "Funnel Intelligence",
    desc: "Stage analysis, drop-off rates, and revenue-impact estimates",
    to: "/funnel",
    c: "text-teal",
  },
  {
    icon: Map,
    label: "Zone Heatmap",
    desc: `${zoneCount} zones · dwell intensity · ${storeName}`,
    to: "/heatmap",
    c: "text-info",
  },
];

export const CAPABILITY_CARDS = [
  {
    icon: Camera,
    title: yolo,
    sub: `conf ${yoloConf} · ByteTrack · OSNet`,
    color: "from-info/30 to-info/5",
  },
  {
    icon: Shield,
    title: "Validated funnel",
    sub: "4 stages · SQL-enforced",
    color: "from-success/30 to-success/5",
  },
  {
    icon: Bot,
    title: aiModel,
    sub: "Copilot · insights · summary",
    color: "from-primary/30 to-primary/5",
  },
  {
    icon: Map,
    title: `${zoneCount} zones`,
    sub: `${timezoneShort()} · dwell heatmap`,
    color: "from-teal/30 to-teal/5",
  },
];

export const DEMO_STORE = {
  id: storeId,
  name: storeName,
  zones: zoneCount,
  timezone,
  aiModel,
  yoloModel: appConfig.yoloModel,
  reidThreshold: appConfig.reidThreshold,
  cameras: ["CAM_01 Entry", "CAM_02 Floor", "CAM_03 Billing"],
};
