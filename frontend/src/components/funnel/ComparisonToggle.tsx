import { COMPARE_PERIODS, type ComparePeriod } from "@/lib/funnel-data";
import { cn } from "@/lib/utils";

interface Props {
  value: ComparePeriod;
  onChange: (v: ComparePeriod) => void;
}

export function ComparisonToggle({ value, onChange }: Props) {
  return (
    <div className="inline-flex items-center gap-1 p-1 rounded-xl border border-border/60 bg-muted/40">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground px-2 hidden sm:inline">Compare vs</span>
      {COMPARE_PERIODS.map((p) => {
        const active = value === p.id;
        return (
          <button
            key={p.id}
            type="button"
            onClick={() => onChange(p.id)}
            className={cn(
              "text-[11px] font-semibold px-2.5 py-1 rounded-lg transition-all duration-200",
              active
                ? "bg-gradient-primary text-primary-foreground shadow-glow"
                : "text-muted-foreground hover:text-foreground hover:bg-accent",
            )}
          >
            {p.label}
          </button>
        );
      })}
    </div>
  );
}
