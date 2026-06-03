import { ChevronDown, Filter as FilterIcon, Store, CalendarRange } from "lucide-react";
import { STORES, DATE_RANGES, PERF_FILTERS, ZONE_ANALYTICS, type DateRange, type PerformanceFilter } from "@/lib/store-layout";

interface Props {
  storeId: string;
  dateRange: DateRange;
  perf: PerformanceFilter;
  zoneFilter: string; // "all" or zone_id
  onChange: (next: { storeId?: string; dateRange?: DateRange; perf?: PerformanceFilter; zoneFilter?: string }) => void;
}

export function FiltersBar({ storeId, dateRange, perf, zoneFilter, onChange }: Props) {
  return (
    <div className="surface-elevated rounded-2xl p-3 flex flex-wrap items-center gap-2">
      <Select
        icon={<Store className="h-3.5 w-3.5" />}
        label="Store"
        value={storeId}
        onChange={(v) => onChange({ storeId: v })}
        options={STORES.map((s) => ({ value: s.id, label: s.name }))}
      />
      <Select
        icon={<CalendarRange className="h-3.5 w-3.5" />}
        label="Range"
        value={dateRange}
        onChange={(v) => onChange({ dateRange: v as DateRange })}
        options={DATE_RANGES.map((d) => ({ value: d.id, label: d.label }))}
      />
      <Select
        icon={<FilterIcon className="h-3.5 w-3.5" />}
        label="Zone"
        value={zoneFilter}
        onChange={(v) => onChange({ zoneFilter: v })}
        options={[{ value: "all", label: "All zones" }, ...ZONE_ANALYTICS.map((z) => ({ value: z.zone_id, label: z.name }))]}
      />
      <Select
        icon={<FilterIcon className="h-3.5 w-3.5" />}
        label="Performance"
        value={perf}
        onChange={(v) => onChange({ perf: v as PerformanceFilter })}
        options={PERF_FILTERS.map((p) => ({ value: p.id, label: p.label }))}
      />
    </div>
  );
}

interface SelectProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}

function Select({ icon, label, value, options, onChange }: SelectProps) {
  return (
    <label className="relative inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-muted/40 hover:border-primary/40 transition-colors cursor-pointer min-w-[160px]">
      <span className="text-muted-foreground">{icon}</span>
      <span className="flex flex-col leading-tight">
        <span className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</span>
        <span className="text-xs font-semibold truncate max-w-[180px]">
          {options.find((o) => o.value === value)?.label ?? value}
        </span>
      </span>
      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground ml-auto" />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="absolute inset-0 opacity-0 cursor-pointer"
        aria-label={label}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </label>
  );
}
