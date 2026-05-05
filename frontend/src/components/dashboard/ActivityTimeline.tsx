import {
  CheckCircle,
  XCircle,
  Clock,
  Users,
  Workflow,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface ActivityEvent {
  id: string;
  type: "workflow" | "agent" | "approval" | "schedule" | "error";
  title: string;
  description?: string;
  timestamp: string;
  status?: "success" | "failed" | "pending";
}

interface ActivityTimelineProps {
  events: ActivityEvent[];
  maxItems?: number;
}

const eventIcons = {
  workflow: Workflow,
  agent: Users,
  approval: AlertCircle,
  schedule: Calendar,
  error: XCircle,
};

const eventColors = {
  workflow: "text-blue-600 bg-blue-100 dark:bg-blue-900",
  agent: "text-purple-600 bg-purple-100 dark:bg-purple-900",
  approval: "text-orange-600 bg-orange-100 dark:bg-orange-900",
  schedule: "text-green-600 bg-green-100 dark:bg-green-900",
  error: "text-red-600 bg-red-100 dark:bg-red-900",
};

const statusIcons = {
  success: CheckCircle,
  failed: XCircle,
  pending: Clock,
};

export function ActivityTimeline({ events, maxItems = 10 }: ActivityTimelineProps) {
  const displayEvents = events.slice(0, maxItems);

  if (displayEvents.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No recent activity
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {displayEvents.map((event, index) => {
        const EventIcon = eventIcons[event.type] || Workflow;
        const StatusIcon = event.status ? statusIcons[event.status] : null;

        return (
          <div key={event.id} className="flex gap-4 group">
            {/* Timeline connector */}
            <div className="flex flex-col items-center">
              <div
                className={`p-2 rounded-lg ${eventColors[event.type]} transition-transform group-hover:scale-110`}
              >
                <EventIcon className="w-4 h-4" />
              </div>
              {index < displayEvents.length - 1 && (
                <div className="w-0.5 h-full bg-gray-200 dark:bg-gray-700 mt-2" />
              )}
            </div>

            {/* Event content */}
            <div className="flex-1 pb-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium">{event.title}</p>
                    {StatusIcon && (
                      <StatusIcon
                        className={`w-4 h-4 ${
                          event.status === "success"
                            ? "text-green-600"
                            : event.status === "failed"
                            ? "text-red-600"
                            : "text-yellow-600"
                        }`}
                      />
                    )}
                  </div>
                  {event.description && (
                    <p className="text-xs text-muted-foreground mt-1">
                      {event.description}
                    </p>
                  )}
                </div>
                <p className="text-xs text-muted-foreground whitespace-nowrap">
                  {formatDistanceToNow(new Date(event.timestamp), {
                    addSuffix: true,
                  })}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
