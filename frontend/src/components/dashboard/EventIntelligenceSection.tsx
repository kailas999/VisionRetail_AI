import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/store-api";
import { Users, Clock, ShoppingBag, Eye, Activity, Map, ArrowRight } from "lucide-react";

export function EventIntelligenceSection({ storeId }: { storeId: string }) {
  const { data: stream, isLoading } = useQuery({
    queryKey: ["event-stream", storeId],
    queryFn: () => api.eventStream(storeId),
    refetchInterval: 5000,
  });

  if (isLoading || !stream) {
    return <div className="animate-pulse h-64 bg-muted/20 rounded-xl border border-border/50"></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          Retail Event Intelligence
        </h2>
        <div className="flex items-center gap-2">
          <span className="pulse-dot"></span>
          <span className="text-xs text-muted-foreground font-mono uppercase">Live Event Stream</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Card 1: Entrance */}
        <div className="surface p-5 rounded-xl border border-border/50 shadow-sm flex flex-col gap-4 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-blue-500 to-blue-400"></div>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm text-foreground/90 uppercase tracking-wider">Entrance Intelligence</h3>
            <Users className="h-4 w-4 text-blue-500" />
          </div>
          <div className="grid grid-cols-2 gap-y-4">
            <div>
              <div className="text-xs text-muted-foreground">ENTRY Events</div>
              <div className="text-xl font-mono font-bold">{stream.entrance.entry_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">EXIT Events</div>
              <div className="text-xl font-mono font-bold">{stream.entrance.exit_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">REENTRY Events</div>
              <div className="text-xl font-mono font-bold">{stream.entrance.reentry_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Occupancy</div>
              <div className="text-xl font-mono font-bold text-blue-400">{stream.entrance.current_occupancy}</div>
            </div>
          </div>
        </div>

        {/* Card 2: Zone */}
        <div className="surface p-5 rounded-xl border border-border/50 shadow-sm flex flex-col gap-4 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-500 to-purple-400"></div>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm text-foreground/90 uppercase tracking-wider">Zone Intelligence</h3>
            <Map className="h-4 w-4 text-purple-500" />
          </div>
          <div className="grid grid-cols-2 gap-y-4">
            <div>
              <div className="text-xs text-muted-foreground">ZONE_ENTER</div>
              <div className="text-xl font-mono font-bold">{stream.zone.zone_enter_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">ZONE_EXIT</div>
              <div className="text-xl font-mono font-bold">{stream.zone.zone_exit_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">ZONE_DWELL</div>
              <div className="text-xl font-mono font-bold">{stream.zone.zone_dwell_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Avg Dwell</div>
              <div className="text-xl font-mono font-bold text-purple-400">{Math.round(stream.zone.avg_dwell_seconds)}s</div>
            </div>
          </div>
        </div>

        {/* Card 3: Billing */}
        <div className="surface p-5 rounded-xl border border-border/50 shadow-sm flex flex-col gap-4 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-500 to-emerald-400"></div>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm text-foreground/90 uppercase tracking-wider">Billing Intelligence</h3>
            <ShoppingBag className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="grid grid-cols-2 gap-y-4">
            <div>
              <div className="text-xs text-muted-foreground">QUEUE_JOIN</div>
              <div className="text-xl font-mono font-bold">{stream.billing.queue_join_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">QUEUE_ABANDON</div>
              <div className="text-xl font-mono font-bold">{stream.billing.queue_abandon_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">PURCHASE</div>
              <div className="text-xl font-mono font-bold text-emerald-400">{stream.billing.purchase_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Abandon Rate</div>
              <div className="text-xl font-mono font-bold text-orange-400">{stream.billing.queue_abandon_rate}%</div>
            </div>
          </div>
        </div>

        {/* Card 4: Re-ID */}
        <div className="surface p-5 rounded-xl border border-border/50 shadow-sm flex flex-col gap-4 relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-amber-500 to-amber-400"></div>
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-sm text-foreground/90 uppercase tracking-wider">Re-ID Intelligence</h3>
            <Eye className="h-4 w-4 text-amber-500" />
          </div>
          <div className="grid grid-cols-2 gap-y-4">
            <div>
              <div className="text-xs text-muted-foreground">Matches</div>
              <div className="text-xl font-mono font-bold">{stream.reid.cross_camera_matches}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Match Rate</div>
              <div className="text-xl font-mono font-bold text-amber-400">{stream.reid.match_rate}%</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Fragmented</div>
              <div className="text-xl font-mono font-bold text-red-400">{stream.reid.fragmented_visitors}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Avg Confidence</div>
              <div className="text-xl font-mono font-bold">{stream.reid.avg_confidence}%</div>
            </div>
          </div>
        </div>
      </div>

      {/* Card 5: Event Stream Health */}
      <div className="surface p-5 rounded-xl border border-border/50 shadow-sm">
        <h3 className="font-semibold text-sm text-foreground/90 uppercase tracking-wider mb-4 border-b border-border/50 pb-2 flex items-center gap-2">
          <Clock className="h-4 w-4 text-primary" />
          Retail Event Stream
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="flex flex-col">
            <span className="text-[10px] text-muted-foreground font-mono">CAM_01</span>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">ENTRY</span>
              <span className="font-mono text-sm">{stream.entrance.entry_count}</span>
            </div>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">EXIT</span>
              <span className="font-mono text-sm">{stream.entrance.exit_count}</span>
            </div>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">REENTRY</span>
              <span className="font-mono text-sm">{stream.entrance.reentry_count}</span>
            </div>
          </div>
          
          <div className="flex flex-col">
            <span className="text-[10px] text-muted-foreground font-mono">CAM_02</span>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">ZONE_ENTER</span>
              <span className="font-mono text-sm">{stream.zone.zone_enter_count}</span>
            </div>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">ZONE_EXIT</span>
              <span className="font-mono text-sm">{stream.zone.zone_exit_count}</span>
            </div>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">ZONE_DWELL</span>
              <span className="font-mono text-sm">{stream.zone.zone_dwell_count}</span>
            </div>
          </div>

          <div className="flex flex-col">
            <span className="text-[10px] text-muted-foreground font-mono">CAM_03</span>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">QUEUE_JOIN</span>
              <span className="font-mono text-sm">{stream.billing.queue_join_count}</span>
            </div>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold">QUEUE_ABANDON</span>
              <span className="font-mono text-sm">{stream.billing.queue_abandon_count}</span>
            </div>
            <div className="flex justify-between items-center bg-muted/30 p-2 rounded mt-1">
              <span className="text-xs font-semibold text-emerald-400">PURCHASE</span>
              <span className="font-mono text-sm text-emerald-400">{stream.billing.purchase_count}</span>
            </div>
          </div>
          
          {/* Pipeline flow visualizer */}
          <div className="col-span-2 hidden lg:flex items-center justify-center bg-muted/10 rounded border border-dashed border-border/50 p-4">
             <div className="flex items-center gap-2 text-muted-foreground">
                <div className="text-center">
                  <div className="text-xs font-mono mb-1">DETECTION</div>
                  <div className="h-8 w-8 rounded bg-blue-500/20 border border-blue-500/50 flex items-center justify-center text-blue-400"><Eye className="h-4 w-4"/></div>
                </div>
                <ArrowRight className="h-4 w-4" />
                <div className="text-center">
                  <div className="text-xs font-mono mb-1">EVENTS</div>
                  <div className="h-8 w-8 rounded bg-purple-500/20 border border-purple-500/50 flex items-center justify-center text-purple-400"><Activity className="h-4 w-4"/></div>
                </div>
                <ArrowRight className="h-4 w-4" />
                <div className="text-center">
                  <div className="text-xs font-mono mb-1">METRICS</div>
                  <div className="h-8 w-8 rounded bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center text-emerald-400"><Map className="h-4 w-4"/></div>
                </div>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}
