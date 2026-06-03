import { Link } from "@tanstack/react-router";
import { Bot, ChevronDown, Play, Sparkles, TrendingUp, Users, Map, Zap } from "lucide-react";
import { ScrollReveal } from "@/hooks/use-scroll-reveal";
import { cn } from "@/lib/utils";
import { appConfig, timezoneShort } from "@/lib/app-config";
import { DEMO_STORE } from "./data";

interface Props {
  isLive: boolean;
  storeId: string;
  storeName?: string;
  visitors?: number;
  conversion?: string;
  reidRate?: string;
  anomalyCount?: number;
}

export function HomeHero({
  isLive,
  storeId,
  storeName = DEMO_STORE.name,
  visitors,
  conversion,
  reidRate,
  anomalyCount,
}: Props) {
  return (
    <section className="landing-hero relative min-h-[100svh] flex flex-col justify-center pt-28 pb-20 px-4 sm:px-6">
      <div className="landing-spotlight" />
      <div className="landing-mesh" />
      <div className="landing-ring landing-ring-1" />
      <div className="landing-ring landing-ring-2" />
      <div className="landing-aurora" />

      <div className="relative max-w-7xl mx-auto w-full">
        <ScrollReveal className="text-center max-w-5xl mx-auto">
          <div className="landing-pill mx-auto mb-8">
            <span className={cn("landing-pill-dot", isLive && "landing-pill-dot-live")} />
            <span>
              {isLive
                ? `Live · ${storeId} · ${timezoneShort()}`
                : `${appConfig.environment} · ${storeId}`}
            </span>
            {isLive && <span className="text-success font-semibold">API online</span>}
          </div>

          <h1 className="landing-hero-title">
            <span className="landing-hero-title-lead">Turn cameras into</span>
            <span className="landing-hero-title-main">revenue intelligence</span>
          </h1>

          <p className="mt-6 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
            {appConfig.yoloModel.replace(/\.pt$/i, "")} + OSNet Re-ID on three cameras, ingested to
            PostgreSQL on :{appConfig.apiPort} — then surfaced as live KPIs, funnels, heatmaps,
            anomalies, and {appConfig.aiModel} copilot for {storeName}.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/dashboard" className="landing-btn-primary landing-btn-lg w-full sm:w-auto">
              <Play className="h-4 w-4 fill-current" />
              Launch Dashboard
            </Link>
            <a href="#features" className="landing-btn-ghost landing-btn-lg w-full sm:w-auto">
              See what&apos;s inside <ChevronDown className="h-4 w-4" />
            </a>
          </div>

          <div className="mt-8 flex items-center justify-center gap-3 flex-wrap">
            <div className="landing-trust-avatars">
              {["CV", "Re-ID", "AI"].map((t, i) => (
                <span key={t} style={{ zIndex: 3 - i }}>{t}</span>
              ))}
            </div>
            <p className="text-sm text-muted-foreground text-center sm:text-left">
              Configured store ·{" "}
              <span className="text-foreground font-semibold">{storeName}</span>
              {" · "}
              <span className="font-mono text-xs">{storeId}</span>
              {" · "}
              <span className="text-xs">{appConfig.timezone}</span>
            </p>
          </div>
        </ScrollReveal>

        <ScrollReveal className="mt-12 sm:mt-16 relative max-w-5xl mx-auto" delay={150}>
          <DashboardMockup
            visitors={visitors}
            conversion={conversion}
            storeId={storeId}
            storeName={storeName}
            isLive={isLive}
            reidRate={reidRate}
            anomalyCount={anomalyCount}
          />
        </ScrollReveal>
      </div>

      <a href="#impact" className="landing-scroll-hint" aria-label="Scroll down">
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground font-semibold">Explore</span>
        <ChevronDown className="h-4 w-4 text-primary animate-bounce mt-1" />
      </a>
    </section>
  );
}

function DashboardMockup({
  visitors,
  conversion,
  storeId,
  storeName,
  isLive,
  reidRate,
  anomalyCount,
}: {
  visitors?: number;
  conversion?: string;
  storeId: string;
  storeName: string;
  isLive: boolean;
  reidRate?: string;
  anomalyCount?: number;
}) {
  const bars = [35, 55, 42, 70, 48, 85, 62, 90, 58, 78, 65, 92];

  return (
    <div className="landing-mockup relative">
      <div className="landing-mockup-glow" />
      <div className="landing-mockup-frame rounded-2xl sm:rounded-3xl overflow-hidden border border-border/60 shadow-2xl">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border/50 bg-muted/30">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-critical/60" />
            <span className="h-2.5 w-2.5 rounded-full bg-warn/60" />
            <span className="h-2.5 w-2.5 rounded-full bg-success/60" />
          </div>
          <span className="text-[10px] text-muted-foreground font-mono flex-1 text-center">
            visionretail.ai/dashboard
          </span>
          {isLive && (
            <span className="badge-live text-[8px] py-0.5">
              <span className="pulse-dot" /> Live
            </span>
          )}
        </div>

        <div className="p-4 sm:p-6 bg-card/95 backdrop-blur-xl">
          <div className="flex items-center justify-between mb-5">
            <div>
              <div className="text-xs text-muted-foreground">Store Overview</div>
              <div className="font-bold text-sm mt-0.5">{storeName}</div>
              <div className="text-[10px] text-muted-foreground font-mono mt-0.5">{storeId}</div>
            </div>
            <div className="h-8 w-8 rounded-lg bg-gradient-primary grid place-items-center shadow-glow">
              <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mb-4">
            {[
              { icon: Users, label: "Visitors", val: visitors ?? "—", c: "border-primary/20 bg-primary/5" },
              { icon: TrendingUp, label: "Conv.", val: conversion ? `${conversion}%` : "—", c: "border-teal/20 bg-teal/5" },
              { icon: Map, label: "Zones", val: String(DEMO_STORE.zones), c: "border-info/20 bg-info/5" },
              { icon: Zap, label: "Alerts", val: anomalyCount ?? "—", c: "border-warn/20 bg-warn/5" },
            ].map((k) => (
              <div key={k.label} className={cn("rounded-xl border p-2.5 sm:p-3", k.c)}>
                <k.icon className="h-3.5 w-3.5 text-muted-foreground mb-1.5" />
                <div className="text-[9px] text-muted-foreground uppercase">{k.label}</div>
                <div className="text-sm sm:text-base font-bold font-mono tabular-nums">{k.val}</div>
              </div>
            ))}
          </div>

          <div className="rounded-xl border border-border/40 bg-muted/20 p-3 sm:p-4">
            <div className="flex justify-between text-[10px] text-muted-foreground mb-3">
              <span>Visitors vs Conversions</span>
              <span className="flex gap-3">
                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-primary" /> Visitors</span>
                <span className="flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-teal" /> Conv.</span>
              </span>
            </div>
            <div className="flex items-end gap-1 h-20 sm:h-24">
              {bars.map((h, i) => (
                <div key={i} className="flex-1 flex flex-col gap-0.5 justify-end h-full">
                  <div className="rounded-sm bg-gradient-to-t from-primary to-primary/40 landing-bar-animate" style={{ height: `${h}%`, animationDelay: `${i * 60}ms` }} />
                  <div className="rounded-sm bg-gradient-to-t from-teal to-teal/30 landing-bar-animate" style={{ height: `${h * 0.45}%`, animationDelay: `${i * 60 + 30}ms` }} />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="landing-float-card landing-float-1 hidden sm:block">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-success/15 grid place-items-center">
            <TrendingUp className="h-4 w-4 text-success" />
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground">Re-ID match rate</div>
            <div className="text-sm font-bold text-success tabular-nums">
              {reidRate ? `${reidRate}%` : "—"}
            </div>
          </div>
        </div>
      </div>
      <div className="landing-float-card landing-float-2 hidden sm:block">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-primary/15 grid place-items-center">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground">Anomaly insight</div>
            <div className="text-xs font-semibold max-w-[140px] leading-tight">
              {anomalyCount ? `${anomalyCount} active alert${anomalyCount === 1 ? "" : "s"}` : "Monitoring baseline"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
