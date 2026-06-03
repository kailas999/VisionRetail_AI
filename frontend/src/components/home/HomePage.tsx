import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, DEFAULT_STORE_ID } from "@/lib/store-api";
import { DEMO_STORE } from "./data";
import { HomeBento, HomeCta, HomeFooter, HomePlatform, HomeSteps } from "./HomeModules";
import { HomeCompare, HomeFaq, HomeImpact, HomeMarquee, HomeUseCases } from "./HomeSections";
import { HomeHero } from "./HomeHero";
import { HomeNav } from "./HomeNav";

export function HomePage() {
  const storeId = DEFAULT_STORE_ID;
  const health = useQuery({ queryKey: ["health"], queryFn: () => api.health(), refetchInterval: 10000 });
  const metrics = useQuery({ queryKey: ["metrics", storeId], queryFn: () => api.metrics(storeId), refetchInterval: 15000 });
  const anomalies = useQuery({ queryKey: ["anomalies", storeId], queryFn: () => api.anomalies(storeId), refetchInterval: 20000 });

  const isLive = health.data?.status === "ok";
  const m = metrics.data;
  const anomalyCount = anomalies.data?.anomalies.length;

  useEffect(() => {
    const onScroll = () => {
      const el = document.documentElement;
      const pct = el.scrollHeight > el.clientHeight
        ? el.scrollTop / (el.scrollHeight - el.clientHeight)
        : 0;
      el.style.setProperty("--scroll-progress", String(pct));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="landing-page min-h-screen flex flex-col overflow-x-hidden">
      <div className="landing-scroll-progress" aria-hidden />
      <HomeNav />
      <HomeHero
        isLive={isLive}
        storeId={storeId}
        storeName={DEMO_STORE.name}
        visitors={m?.unique_visitors}
        conversion={m ? (m.conversion_rate * 100).toFixed(1) : undefined}
        reidRate={m ? (m.cross_camera_match_rate * 100).toFixed(1) : undefined}
        anomalyCount={anomalyCount}
      />
      <HomeMarquee />
      <HomeImpact />
      <HomeBento />
      <HomeCompare />
      <HomePlatform />
      <HomeSteps />
      <HomeUseCases />
      <HomeFaq />
      <HomeCta />
      <HomeFooter />
    </div>
  );
}
