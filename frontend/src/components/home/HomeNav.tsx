import { Link } from "@tanstack/react-router";
import { ArrowRight, Menu, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "#features", label: "Features" },
  { href: "#impact", label: "Impact" },
  { href: "#platform", label: "Platform" },
  { href: "#how", label: "How it works" },
  { href: "#faq", label: "FAQ" },
];

export function HomeNav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className="landing-nav fixed top-0 inset-x-0 z-50 px-4 sm:px-6 py-3 sm:py-4">
      <div
        className={cn(
          "max-w-7xl mx-auto flex items-center justify-between gap-4 rounded-2xl landing-nav-inner px-4 sm:px-5 py-2.5 transition-all duration-300",
          scrolled && "landing-nav-scrolled py-2",
        )}
      >
        <Link to="/" className="flex items-center gap-2.5 group shrink-0">
          <div className="landing-logo h-10 w-10 rounded-xl grid place-items-center">
            <Sparkles className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="hidden sm:block">
            <div className="text-sm font-bold tracking-tight leading-none">VisionRetail</div>
            <div className="text-[10px] text-muted-foreground font-medium mt-0.5">Retail Intelligence</div>
          </div>
        </Link>

        <nav className="hidden lg:flex items-center gap-0.5">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="px-3.5 py-2 text-sm font-medium text-muted-foreground hover:text-foreground rounded-lg hover:bg-foreground/5 transition-all"
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-2 shrink-0">
          <ThemeToggle />
          <Link to="/dashboard" className="landing-btn-primary hidden sm:inline-flex">
            Get Started <ArrowRight className="h-4 w-4" />
          </Link>
          <button
            type="button"
            className="lg:hidden h-9 w-9 rounded-lg border border-border/60 grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted/50"
            onClick={() => setMobileOpen((o) => !o)}
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="lg:hidden max-w-7xl mx-auto mt-2 px-4">
          <div className="landing-nav-inner rounded-2xl p-4 flex flex-col gap-1">
            {LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setMobileOpen(false)}
                className="px-4 py-3 text-sm font-medium rounded-xl hover:bg-foreground/5"
              >
                {l.label}
              </a>
            ))}
            <Link
              to="/dashboard"
              onClick={() => setMobileOpen(false)}
              className="landing-btn-primary mt-2 justify-center"
            >
              Launch Dashboard <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
