import { Link, useRouterState } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { GitBranch, Home, LayoutDashboard, Map, Sparkles } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Home", icon: Home, exact: true },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/funnel", label: "Funnel", icon: GitBranch, exact: false },
  { to: "/heatmap", label: "Heatmap", icon: Map, exact: false },
] as const;

interface AppShellProps {
  pageLabel: string;
  storeId?: string;
  status?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}

export function AppShell({ pageLabel, storeId, status, actions, children }: AppShellProps) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <div className="min-h-screen flex flex-col">
      <header className="surface-strong sticky top-0 z-30 border-b border-border/50">
        <div className="max-w-[1600px] mx-auto px-4 sm:px-6">
          <div className="py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <Link to="/" className="flex items-center gap-3 min-w-0 group">
                <div className="h-9 w-9 shrink-0 rounded-xl bg-gradient-primary grid place-items-center shadow-glow transition-transform duration-300 group-hover:scale-105">
                  <Sparkles className="h-4 w-4 text-primary-foreground" />
                </div>
                <div className="min-w-0 hidden sm:block">
                  <div className="text-sm font-bold tracking-tight leading-none">VisionRetail AI</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5 truncate">{pageLabel}</div>
                </div>
              </Link>
            </div>

            <nav className="flex items-center gap-0.5 sm:gap-1 p-1 rounded-xl bg-muted/40 border border-border/50">
              {NAV.map(({ to, label, icon: Icon, exact }) => {
                const active = exact ? pathname === to : pathname.startsWith(to);
                return (
                  <Link key={to} to={to} className={cn("nav-link", active && "nav-link-active")}>
                    <Icon className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">{label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="flex items-center gap-2 shrink-0">
              {storeId && (
                <div className="hidden lg:flex items-center text-xs text-muted-foreground px-3 py-1.5 rounded-lg bg-muted/50 border border-border/60 font-mono">
                  {storeId}
                </div>
              )}
              {status}
              {actions}
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 sm:px-6 py-6 page-enter">
        {children}
      </main>

      <footer className="border-t border-border/40 py-5 mt-auto">
        <p className="text-center text-[11px] text-muted-foreground">
          VisionRetail AI · Store Intelligence Platform
        </p>
      </footer>
    </div>
  );
}

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: string;
  trailing?: ReactNode;
}

export function PageHeader({ title, subtitle, trailing }: PageHeaderProps) {
  return (
    <div className="flex items-end justify-between flex-wrap gap-3 mb-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-muted-foreground mt-1.5 max-w-2xl">{subtitle}</p>}
      </div>
      {trailing}
    </div>
  );
}

interface LiveBadgeProps {
  live: boolean;
  label?: string;
}

export function LiveBadge({ live, label }: LiveBadgeProps) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold tracking-wider uppercase",
        live ? "border-success/40 bg-success/10 text-success" : "border-critical/40 bg-critical/10 text-critical",
      )}
    >
      <span className={live ? "pulse-dot" : "h-2 w-2 rounded-full bg-critical"} />
      {label ?? (live ? "Live" : "Offline")}
    </div>
  );
}
