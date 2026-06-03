import { createFileRoute } from "@tanstack/react-router";
import { HomePage } from "@/components/home/HomePage";
import { appConfig } from "@/lib/app-config";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: `VisionRetail AI · ${appConfig.storeId}` },
      {
        name: "description",
        content:
          `${appConfig.storeName} (${appConfig.storeId}) — ${appConfig.yoloModel}, OSNet Re-ID, funnels, heatmaps, anomalies, and ${appConfig.aiModel} copilot. Timezone: ${appConfig.timezone}.`,
      },
      { property: "og:title", content: `VisionRetail AI · ${appConfig.storeName}` },
      {
        property: "og:description",
        content:
          `Live retail intelligence for ${appConfig.storeId} — CCTV events to dashboard on :${appConfig.apiPort}.`,
      },
    ],
  }),
  component: HomePage,
});
