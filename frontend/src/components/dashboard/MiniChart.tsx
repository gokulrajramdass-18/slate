import { Loader2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface MiniChartProps {
  title?: string;
  children: React.ReactNode;
  loading?: boolean;
  error?: string;
}

export function MiniChart({ title, children, loading, error }: MiniChartProps) {
  if (loading) {
    return (
      <div className="space-y-2">
        {title && <h3 className="text-sm font-medium">{title}</h3>}
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-2">
        {title && <h3 className="text-sm font-medium">{title}</h3>}
        <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {title && <h3 className="text-sm font-medium">{title}</h3>}
      <div className="h-48">{children}</div>
      {title && (
        <div className="text-xs text-muted-foreground text-center mt-2">
          {title}
        </div>
      )}
    </div>
  );
}
