import { Link } from "@tanstack/react-router";
import { ArrowRight, Check, X } from "lucide-react";
import { ScrollReveal } from "@/hooks/use-scroll-reveal";
import { COMPARE, FAQ_ITEMS, IMPACT_STATS, MARQUEE_ITEMS, USE_CASES } from "./data";
import { cn } from "@/lib/utils";
import { useState } from "react";

export function HomeMarquee() {
  return (
    <div className="landing-marquee-wrap border-y border-border/40 py-4 bg-card/30 backdrop-blur-sm">
      <div className="landing-marquee">
        {[...MARQUEE_ITEMS, ...MARQUEE_ITEMS].map((t, i) => (
          <span key={i} className="landing-marquee-item">
            <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

export function HomeImpact() {
  return (
    <section id="impact" className="py-16 sm:py-20 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto">
        <ScrollReveal className="text-center mb-12">
          <span className="landing-section-tag">Impact</span>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mt-4">
            Built on <span className="landing-headline-accent">real retail data</span>
          </h2>
          <p className="text-muted-foreground mt-3 max-w-xl mx-auto text-sm sm:text-base">
            From CCTV events to operator-ready KPIs — tuned for the demo store and your live pipeline.
          </p>
        </ScrollReveal>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {IMPACT_STATS.map((s, i) => (
            <ScrollReveal key={s.label} delay={i * 80}>
              <div className="landing-impact-card text-center p-6 sm:p-8 rounded-2xl">
                <div className="text-3xl sm:text-4xl font-bold font-[var(--font-display)] landing-headline-accent tabular-nums">
                  {s.value}
                </div>
                <div className="font-semibold mt-2">{s.label}</div>
                <div className="text-xs text-muted-foreground mt-1">{s.sub}</div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function HomeCompare() {
  return (
    <section className="py-16 sm:py-24 px-4 sm:px-6 landing-section-alt">
      <div className="max-w-5xl mx-auto">
        <ScrollReveal className="text-center mb-12">
          <span className="landing-section-tag">Transformation</span>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mt-4">
            From spreadsheets to <span className="landing-headline-accent">live signals</span>
          </h2>
        </ScrollReveal>

        <div className="grid md:grid-cols-2 gap-5">
          <ScrollReveal delay={0}>
            <div className="landing-compare-card landing-compare-before rounded-2xl p-6 sm:p-8 h-full">
              <h3 className="font-bold text-lg text-muted-foreground">{COMPARE.before.title}</h3>
              <ul className="mt-6 space-y-3">
                {COMPARE.before.items.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <span className="h-5 w-5 rounded-full bg-critical/10 grid place-items-center shrink-0 mt-0.5">
                      <X className="h-3 w-3 text-critical" />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </ScrollReveal>

          <ScrollReveal delay={100}>
            <div className="landing-compare-card landing-compare-after rounded-2xl p-6 sm:p-8 h-full">
              <h3 className="font-bold text-lg">{COMPARE.after.title}</h3>
              <ul className="mt-6 space-y-3">
                {COMPARE.after.items.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm">
                    <span className="h-5 w-5 rounded-full bg-success/15 grid place-items-center shrink-0 mt-0.5">
                      <Check className="h-3 w-3 text-success" />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
              <Link to="/dashboard" className="landing-btn-primary mt-8 w-full sm:w-auto">
                Start now <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </ScrollReveal>
        </div>
      </div>
    </section>
  );
}

export function HomeUseCases() {
  return (
    <section className="py-16 sm:py-24 px-4 sm:px-6">
      <div className="max-w-7xl mx-auto">
        <ScrollReveal className="text-center mb-12">
          <span className="landing-section-tag">Use cases</span>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mt-4">
            What you can <span className="landing-headline-accent">uncover</span>
          </h2>
          <p className="text-muted-foreground mt-3 max-w-2xl mx-auto text-sm sm:text-base">
            Three core workflows — funnel drop-offs, floor heatmaps, and AI copilot — mapped to real pages in this app.
          </p>
        </ScrollReveal>

        <div className="grid md:grid-cols-3 gap-5">
          {USE_CASES.map((t, i) => (
            <ScrollReveal key={t.role} delay={i * 100}>
              <div className="landing-testimonial rounded-2xl p-6 sm:p-7 h-full flex flex-col">
                <p className="text-sm leading-relaxed flex-1">&ldquo;{t.quote}&rdquo;</p>
                <div className="mt-6 pt-5 border-t border-border/50">
                  <div className="text-xs font-bold text-primary">{t.metric}</div>
                  <div className="text-sm font-semibold mt-1">{t.role}</div>
                  <div className="text-xs text-muted-foreground">{t.org}</div>
                </div>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}

export function HomeFaq() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section id="faq" className="py-16 sm:py-24 px-4 sm:px-6 landing-section-alt">
      <div className="max-w-3xl mx-auto">
        <ScrollReveal className="text-center mb-12">
          <span className="landing-section-tag">FAQ</span>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight mt-4">
            Questions? <span className="landing-headline-accent">Answered.</span>
          </h2>
        </ScrollReveal>

        <div className="space-y-3">
          {FAQ_ITEMS.map((item, i) => (
            <ScrollReveal key={item.q} delay={i * 60}>
              <div className="landing-faq-item rounded-xl border border-border/60 overflow-hidden bg-card/50">
                <button
                  type="button"
                  onClick={() => setOpen(open === i ? null : i)}
                  className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left text-sm font-semibold hover:bg-muted/30 transition-colors"
                >
                  {item.q}
                  <span className={cn("text-primary text-lg transition-transform", open === i && "rotate-45")}>+</span>
                </button>
                {open === i && (
                  <div className="px-5 pb-4 text-sm text-muted-foreground leading-relaxed border-t border-border/40 pt-3">
                    {item.a}
                  </div>
                )}
              </div>
            </ScrollReveal>
          ))}
        </div>
      </div>
    </section>
  );
}
