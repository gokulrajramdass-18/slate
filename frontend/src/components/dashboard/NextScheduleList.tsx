import { Clock, Zap } from "lucide-react";
import { formatDistanceToNow } from "date-fns";

interface NextRun {
  id: string;
  workflow_name: string;
  next_run_at: string;
  schedule_type: string;
}

interface NextScheduleListProps {
  schedules: NextRun[];
  emptyMessage?: string;
}

export function NextScheduleList({
  schedules,
  emptyMessage = "No upcoming scheduled runs",
}: NextScheduleListProps) {
  if (schedules.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        {emptyMessage}
      </div>
    );
  }

  const getScheduleIcon = (type: string) => {
    switch (type) {
      case "cron":
        return <Clock className="w-4 h-4 text-blue-500" />;
      case "event":
        return <Zap className="w-4 h-4 text-purple-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const isImminent = (nextRun: string) => {
    const diff = new Date(nextRun).getTime() - Date.now();
    return diff < 3600000; // Less than 1 hour
  };

  return (
    <div className="space-y-2">
      {schedules.map((schedule) => {
        const imminent = isImminent(schedule.next_run_at);

        return (
          <div
            key={schedule.id}
            className={`flex items-center justify-between p-3 rounded-lg transition-all ${
              imminent
                ? "bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800"
                : "bg-gray-50 dark:bg-gray-800"
            }`}
          >
            <div className="flex items-center gap-3 flex-1">
              {getScheduleIcon(schedule.schedule_type)}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  {schedule.workflow_name}
                </p>
                <p className={`text-xs ${imminent ? "text-orange-600 dark:text-orange-400 font-medium" : "text-muted-foreground"}`}>
                  {formatDistanceToNow(new Date(schedule.next_run_at), {
                    addSuffix: true,
                  })}
                </p>
              </div>
            </div>
            {imminent && (
              <span className="text-xs font-medium text-orange-600 dark:text-orange-400">
                Soon
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
