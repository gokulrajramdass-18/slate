"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  Loader2,
  Clock,
  XCircle,
  AlertTriangle,
  ArrowRight,
  FileText,
  Calendar,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AgentTask, TaskStatus } from "@/lib/types";

interface TaskBoardProps {
  tasks: AgentTask[];
}

const statusColumns: { key: TaskStatus; label: string; color: string }[] = [
  { key: "pending", label: "Pending", color: "bg-gray-50 dark:bg-gray-900" },
  { key: "blocked", label: "Blocked", color: "bg-amber-50 dark:bg-amber-950" },
  { key: "in_progress", label: "In Progress", color: "bg-blue-50 dark:bg-blue-950" },
  { key: "completed", label: "Completed", color: "bg-green-50 dark:bg-green-950" },
  { key: "failed", label: "Failed", color: "bg-red-50 dark:bg-red-950" },
];

const statusIcons: Record<TaskStatus, React.ElementType> = {
  pending: Clock,
  in_progress: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
  blocked: AlertTriangle,
};

const statusBadgeVariants: Record<TaskStatus, "default" | "secondary" | "destructive" | "outline"> = {
  pending: "outline",
  in_progress: "secondary",
  completed: "default",
  failed: "destructive",
  blocked: "outline",
};

export function TaskBoard({ tasks }: TaskBoardProps) {
  const [selectedTask, setSelectedTask] = useState<AgentTask | null>(null);

  if (tasks.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <Clock className="h-12 w-12 mx-auto mb-3 text-gray-300 dark:text-gray-700" />
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">
            No tasks yet
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Execute a query to see task breakdown
          </p>
        </CardContent>
      </Card>
    );
  }

  // Group tasks by status
  const grouped = statusColumns.reduce<Record<TaskStatus, AgentTask[]>>(
    (acc, col) => {
      acc[col.key] = tasks.filter((t) => t.status === col.key);
      return acc;
    },
    {} as Record<TaskStatus, AgentTask[]>
  );

  // Only show columns that have tasks
  const activeColumns = statusColumns.filter((col) => grouped[col.key].length > 0);

  return (
    <div className="space-y-3">
      {/* Summary header */}
      <div className="flex items-center justify-between px-1">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Task Overview
        </h3>
        <div className="flex items-center gap-2">
          {statusColumns.map((col) => {
            const count = grouped[col.key].length;
            if (count === 0) return null;
            return (
              <Badge
                key={col.key}
                variant={statusBadgeVariants[col.key]}
                className="text-[10px] font-medium"
              >
                {count} {col.label.toLowerCase()}
              </Badge>
            );
          })}
        </div>
      </div>

      {/* Task columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {activeColumns.map((col) => (
          <div key={col.key} className="space-y-3">
            <div className="flex items-center gap-2 px-2">
              <h4 className="text-sm font-bold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                {col.label}
              </h4>
              <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
              <Badge variant="outline" className="text-xs h-5 font-semibold">
                {grouped[col.key].length}
              </Badge>
            </div>
            <div className={`space-y-3 p-4 rounded-lg ${col.color} min-h-[200px] border-2 border-gray-200 dark:border-gray-800`}>
              {grouped[col.key].map((task) => (
                <TaskCard key={task.id} task={task} onClick={() => setSelectedTask(task)} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Task Details Dialog */}
      <Dialog open={!!selectedTask} onOpenChange={(open) => !open && setSelectedTask(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Task Details
            </DialogTitle>
            <DialogDescription>
              Complete information about this task execution
            </DialogDescription>
          </DialogHeader>
          {selectedTask && <TaskDetails task={selectedTask} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TaskCard({ task, onClick }: { task: AgentTask; onClick: () => void }) {
  const StatusIcon = statusIcons[task.status];

  // Parse description if it's JSON
  const getCleanDescription = (desc: string | undefined): string | null => {
    if (!desc) return null;

    // If it starts with { or [, it's likely JSON
    if (desc.trim().startsWith("{") || desc.trim().startsWith("[")) {
      try {
        const parsed = JSON.parse(desc);
        // Extract meaningful fields
        if (parsed.expected_output) return parsed.expected_output;
        if (parsed.description) return parsed.description;
        if (parsed.step_name) return parsed.step_name;
        // If no meaningful field, return null to hide it
        return null;
      } catch {
        // If parsing fails, return original
        return desc;
      }
    }
    return desc;
  };

  const cleanDescription = getCleanDescription(task.description);

  return (
    <Card className="shadow-sm hover:shadow-md transition-shadow cursor-pointer border-2" onClick={onClick}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start gap-3">
          <StatusIcon
            className={`h-5 w-5 flex-shrink-0 mt-0.5 ${
              task.status === "in_progress"
                ? "text-blue-500 animate-spin"
                : task.status === "completed"
                ? "text-green-500"
                : task.status === "failed"
                ? "text-red-500"
                : task.status === "blocked"
                ? "text-amber-500"
                : "text-gray-400"
            }`}
          />
          <div className="flex-1 min-w-0">
            <p className="text-base font-semibold leading-tight text-gray-900 dark:text-gray-100 mb-2">
              {task.title}
            </p>
            {cleanDescription && (
              <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3 leading-relaxed">
                {cleanDescription}
              </p>
            )}
          </div>
        </div>

        {task.assigned_agent_name && (
          <div className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 px-3 py-2 rounded-md border">
            <ArrowRight className="h-4 w-4 text-blue-500" />
            <span className="font-medium">{task.assigned_agent_name}</span>
          </div>
        )}

        {task.depends_on && task.depends_on.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-900 px-3 py-2 rounded-md">
            <AlertTriangle className="h-4 w-4" />
            <span>Depends on {task.depends_on.length} task(s)</span>
          </div>
        )}

        {task.error && (
          <div className="text-sm text-red-700 dark:text-red-300 bg-red-100 dark:bg-red-900 p-3 rounded-md border border-red-300 dark:border-red-700">
            <p className="font-semibold mb-1">Error:</p>
            <p className="line-clamp-2">{task.error}</p>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t">
          <Badge variant={statusBadgeVariants[task.status]} className="text-xs font-medium px-2 py-1">
            {task.status.replace("_", " ")}
          </Badge>
          {task.completed_at && task.started_at && (
            <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
              {(
                (new Date(task.completed_at).getTime() -
                  new Date(task.started_at).getTime()) /
                1000
              ).toFixed(1)}
              s
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function TaskDetails({ task }: { task: AgentTask }) {
  const StatusIcon = statusIcons[task.status];

  // Try to parse JSON fields
  const parseJSON = (value: any): any => {
    if (typeof value === "string") {
      try {
        return JSON.parse(value);
      } catch {
        return value;
      }
    }
    return value;
  };

  const description = parseJSON(task.description);
  const result = parseJSON(task.result);
  const metadata = (task as any).metadata ? parseJSON((task as any).metadata) : null;

  const formatDuration = () => {
    if (!task.started_at || !task.completed_at) return null;
    const duration = (new Date(task.completed_at).getTime() - new Date(task.started_at).getTime()) / 1000;
    return `${duration.toFixed(2)}s`;
  };

  return (
    <ScrollArea className="max-h-[60vh]">
      <div className="space-y-6 pr-4">
        {/* Header */}
        <div className="flex items-start gap-3">
          <StatusIcon
            className={`h-6 w-6 flex-shrink-0 mt-1 ${
              task.status === "in_progress"
                ? "text-blue-500 animate-spin"
                : task.status === "completed"
                ? "text-green-500"
                : task.status === "failed"
                ? "text-red-500"
                : task.status === "blocked"
                ? "text-amber-500"
                : "text-gray-400"
            }`}
          />
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {task.title}
            </h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant={statusBadgeVariants[task.status]}>
                {task.status.replace("_", " ")}
              </Badge>
              {task.assigned_agent_name && (
                <Badge variant="outline" className="text-xs">
                  {task.assigned_agent_name}
                </Badge>
              )}
            </div>
          </div>
        </div>

        {/* Timestamps */}
        <div className="grid grid-cols-2 gap-4">
          {task.started_at && (
            <div className="space-y-1">
              <div className="flex items-center gap-1 text-xs font-medium text-gray-600 dark:text-gray-400">
                <Calendar className="h-3 w-3" />
                Started
              </div>
              <p className="text-sm text-gray-900 dark:text-gray-100">
                {new Date(task.started_at).toLocaleString()}
              </p>
            </div>
          )}
          {task.completed_at && (
            <div className="space-y-1">
              <div className="flex items-center gap-1 text-xs font-medium text-gray-600 dark:text-gray-400">
                <Calendar className="h-3 w-3" />
                Completed
              </div>
              <p className="text-sm text-gray-900 dark:text-gray-100">
                {new Date(task.completed_at).toLocaleString()}
              </p>
              {formatDuration() && (
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Duration: {formatDuration()}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Description/Input */}
        {description && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Task Input / Description
            </h4>
            <Card className="bg-gray-50 dark:bg-gray-900">
              <CardContent className="p-4">
                {typeof description === "object" ? (
                  <pre className="text-xs text-gray-800 dark:text-gray-200 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(description, null, 2)}
                  </pre>
                ) : (
                  <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                    {description}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Result/Output */}
        {result && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Task Output / Result
            </h4>
            <Card className="bg-green-50 dark:bg-green-950">
              <CardContent className="p-4">
                {typeof result === "object" ? (
                  <pre className="text-xs text-gray-800 dark:text-gray-200 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                ) : (
                  <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">
                    {result}
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Error */}
        {task.error && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-red-600 dark:text-red-400">
              Error
            </h4>
            <Card className="bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800">
              <CardContent className="p-4">
                <p className="text-sm text-red-800 dark:text-red-200 whitespace-pre-wrap">
                  {task.error}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Dependencies */}
        {task.depends_on && task.depends_on.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Dependencies
            </h4>
            <Card className="bg-amber-50 dark:bg-amber-950">
              <CardContent className="p-4">
                <p className="text-sm text-amber-800 dark:text-amber-200">
                  This task depends on {task.depends_on.length} other task(s):
                </p>
                <ul className="mt-2 space-y-1">
                  {task.depends_on.map((depId) => (
                    <li key={depId} className="text-xs text-amber-700 dark:text-amber-300 font-mono">
                      • {depId}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Metadata */}
        {metadata && Object.keys(metadata).length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              Additional Metadata
            </h4>
            <Card className="bg-gray-50 dark:bg-gray-900">
              <CardContent className="p-4">
                <pre className="text-xs text-gray-800 dark:text-gray-200 overflow-x-auto whitespace-pre-wrap">
                  {JSON.stringify(metadata, null, 2)}
                </pre>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </ScrollArea>
  );
}
