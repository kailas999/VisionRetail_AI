import { AlertCircle } from "lucide-react";

interface OfflineBannerProps {
  message?: string;
}

export function OfflineBanner({ message = "Backend offline — data shown is stale or unavailable" }: OfflineBannerProps) {
  return (
    <div className="bg-destructive/15 text-destructive border-l-4 border-destructive p-4 rounded-md flex items-start gap-3 my-4">
      <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
      <div>
        <h3 className="font-semibold text-sm">Connection Lost</h3>
        <p className="text-sm opacity-90 mt-1">{message}</p>
      </div>
    </div>
  );
}
