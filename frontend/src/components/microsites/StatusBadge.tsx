"use client";

import { Badge } from "@/components/ui/badge";
import type { MicrositeStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: MicrositeStatus;
  className?: string;
}

const statusConfig = {
  draft: { label: "Draft", variant: "secondary" as const },
  published: { label: "Published", variant: "default" as const },
  blocked: { label: "Blocked", variant: "destructive" as const },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <Badge variant={config.variant} className={className}>
      {config.label}
    </Badge>
  );
}
