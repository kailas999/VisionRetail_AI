import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HourlyPoint } from "@/lib/store-api";
import { useTheme } from "@/hooks/use-theme";
import { getChartTheme } from "@/lib/chart-theme";

interface Props {
  data: HourlyPoint[];
}

export function VisitorsChart({ data }: Props) {
  const { resolvedTheme } = useTheme();
  const chart = getChartTheme(resolvedTheme === "dark");

  return (
    <div className="surface-elevated rounded-2xl p-6 h-full">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">Visitors vs Conversions</h3>
          <p className="text-xs text-muted-foreground mt-1">Hourly breakdown · today</p>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-primary shadow-glow" />
            Visitors
          </span>
          <span className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-teal shadow-glow-teal" />
            Conversions
          </span>
        </div>
      </div>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 12, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="visitorsFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chart.primary} stopOpacity={chart.primaryFill} />
                <stop offset="100%" stopColor={chart.primary} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="convFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={chart.teal} stopOpacity={chart.tealFill} />
                <stop offset="100%" stopColor={chart.teal} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={chart.grid} vertical={false} />
            <XAxis dataKey="hour" stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
            <YAxis stroke={chart.axis} fontSize={11} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={chart.tooltip}
              labelStyle={{ color: chart.label, fontWeight: 600 }}
            />
            <Area type="monotone" dataKey="visitors" stroke={chart.primary} strokeWidth={2.5} fill="url(#visitorsFill)" />
            <Area type="monotone" dataKey="conversions" stroke={chart.teal} strokeWidth={2.5} fill="url(#convFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
