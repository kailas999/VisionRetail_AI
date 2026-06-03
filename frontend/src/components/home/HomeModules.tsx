import { Link } from "@tanstack/react-router";
import { ArrowRight, Sparkles } from "lucide-react";
import { ScrollReveal } from "@/hooks/use-scroll-reveal";
import { BENTO_ITEMS, CAPABILITY_CARDS, DEMO_STORE, MODULE_LINKS, STEPS } from "./data";
import { cn } from "@/lib/utils";

export function HomeBento() {
  return (
    <section id="features" className="py-20 sm:py-28 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto">
        <ScrollReveal className="text-center mb-14">
          <span className="landing-section-tag">Features</span>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mt-4">
            Built for modern{" "}
            <span className="landing-headline-accent">retail teams</span>
          </h2>
          <p className="text-muted-foreground mt-4 max-w-2xl mx-auto text-base sm:text-lg">
            Five modules wired to the same FastAPI backend — live dashboard, funnel intelligence,
            zone heatmaps, z-score anomalies, and GPT-5.2 copilot.
          </p>
        </ScrollReveal>

        <div className="grid md:grid-cols-3 gap-4 auto-rows-[minmax(140px,auto)]">
          {BENTO_ITEMS.map((item, i) => (
            <ScrollReveal key={item.title} delay={i * 70} className={item.span}>
              <Link
                to={item.to}
                className={cn(
                  "landing-bento-card group rounded-2xl p-6 sm:p-7 relative overflow-hidden block h-full",
                  item.accent,
                )}
              >
                <div className="landing-bento-shine" />
                <item.icon className="h-6 w-6 mb-4 opacity-90 group-hover:scale-110 transition-transform duration-300" />
                <h3 className="text-lg sm:text-xl font-bold tracking-tight">{item.title}</h3>
                <p className="text-sm text-muted-foreground mt-2 leading-relaxed max-w-sm">{item.desc}</p>
                <span className="inline-flex items-center gap-1 text-sm font-semibold text-primary mt-4 opacity-0 group-hover:opacity-100 translate-y-2 group-hover:translate-y-0 transition-all duration-300">
                  Explore <ArrowRight className="h-3.5 w-3.5" />
                </span>
              </Link>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function HomePlatform() {
  return (
    <section id="platform" className="py-20 sm:py-28 px-4 sm:px-6 landing-section-alt">
      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-center">
          <ScrollReveal>
            <span className="landing-section-tag">Platform</span>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-4 leading-tight">
              Three views.<br />
              <span className="landing-headline-accent">One event stream.</span>
            </h2>
            <p className="text-muted-foreground mt-5 text-base leading-relaxed">
              Every page reads from the same PostgreSQL store — {DEMO_STORE.id} ({DEMO_STORE.name}).
              Dashboard for ops, funnel for drop-offs, heatmap for the floor. Same design system, same live data.
            </p>
            <div className="mt-8 space-y-3">
              {MODULE_LINKS.map((row) => (
                <Link
                  key={row.to}
                  to={row.to}
                  className="flex items-center gap-4 p-4 rounded-xl border border-border/60 bg-card/50 hover:border-primary/30 hover:bg-card hover:shadow-glow transition-all group"
                >
                  <div className={cn("h-10 w-10 rounded-lg bg-muted/80 grid place-items-center shrink-0", row.c)}>
                    <row.icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <span className="font-semibold block">{row.label}</span>
                    <span className="text-xs text-muted-foreground mt-0.5 block">{row.desc}</span>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all shrink-0" />
                </Link>
              ))}
            </div>
          </ScrollReveal>

          <div className="grid grid-cols-2 gap-3">
            {CAPABILITY_CARDS.map((c, i) => (
              <ScrollReveal key={c.title} delay={i * 80}>
                <div className={cn("rounded-2xl border border-border/50 p-5 bg-gradient-to-br backdrop-blur-sm h-full", c.color)}>
                  <c.icon className="h-5 w-5 text-foreground/80 mb-3" />
                  <div className="font-bold">{c.title}</div>
                  <div className="text-xs text-muted-foreground mt-1">{c.sub}</div>
                </div>
              </ScrollReveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export function HomeSteps() {
  return (
    <section id="how" className="py-20 sm:py-28 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto">
        <ScrollReveal className="text-center mb-16">
          <span className="landing-section-tag">How it works</span>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight mt-4">
            From CCTV clip to <span className="landing-headline-accent">store decision</span>
          </h2>
          <p className="text-muted-foreground mt-4 max-w-2xl mx-auto text-sm sm:text-base">
            YOLOv8m → ByteTrack → OSNet Re-ID → semantic events → PostgreSQL → React dashboard.
          </p>
        </ScrollReveal>
        <div className="grid md:grid-cols-3 gap-8 relative">
          <div className="hidden md:block absolute top-14 left-[18%] right-[18%] h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
          {STEPS.map((s, i) => (
            <ScrollReveal key={s.n} delay={i * 120}>
              <div className="text-center relative landing-step-card rounded-2xl p-8 border border-border/50 bg-card/40">
                <div className="landing-step-num mx-auto mb-5">{s.n}</div>
                <s.icon className="h-5 w-5 text-primary mx-auto mb-3" />
                <h3 className="text-xl font-bold">{s.title}</h3>
                <p className="text-sm text-muted-foreground mt-3 leading-relaxed">{s.desc}</p>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function HomeCta() {
  return (
    <section className="px-4 sm:px-6 pb-20">
      <ScrollReveal className="max-w-5xl mx-auto">
        <div className="landing-cta rounded-3xl p-10 sm:p-16 text-center relative overflow-hidden">
          <div className="landing-cta-glow" />
          <div className="relative z-10">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-primary-foreground">
              Your cameras already see everything.<br />VisionRetail makes it actionable.
            </h2>
            <p className="text-primary-foreground/75 mt-4 max-w-xl mx-auto text-base sm:text-lg">
              Open the live dashboard for {DEMO_STORE.id} ({DEMO_STORE.timezone}), explore funnel
              drop-offs, or inspect {DEMO_STORE.zones} zone heatmaps — powered by {DEMO_STORE.aiModel}.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/dashboard" className="landing-btn-white">
                Open Live Dashboard
              </Link>
              <Link to="/heatmap" className="landing-btn-outline-white">
                Explore Heatmap
              </Link>
            </div>
          </div>
        </div>
      </ScrollReveal>
    </section>
  );
}

export function HomeFooter() {
  return (
    <footer className="border-t border-border/30 py-10 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-3">
          <div className="landing-logo h-9 w-9 rounded-lg grid place-items-center">
            <Sparkles className="h-4 w-4 text-primary-foreground" />
          </div>
          <div>
            <div className="font-bold text-sm">VisionRetail AI</div>
            <div className="text-xs text-muted-foreground">CCTV → Events → Intelligence</div>
          </div>
        </div>
        <div className="flex flex-wrap justify-center gap-6 text-sm text-muted-foreground">
          <Link to="/dashboard" className="hover:text-primary transition-colors">Dashboard</Link>
          <Link to="/funnel" className="hover:text-primary transition-colors">Funnel</Link>
          <Link to="/heatmap" className="hover:text-primary transition-colors">Heatmap</Link>
          <a href="#faq" className="hover:text-primary transition-colors">FAQ</a>
        </div>
        <p className="text-xs text-muted-foreground">© 2026 VisionRetail AI</p>
      </div>
    </footer>
  );
}
