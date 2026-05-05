"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  CheckCircle2,
  Loader2,
  Clock,
  XCircle,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import type { TaskStatus } from "@/lib/types";

// Extended WorkflowStep type that matches backend response
interface WorkflowStep {
  id?: string;
  team_id?: string;
  step_number: number;
  title?: string;
  action?: string; // Backend uses 'action' instead of 'title'
  description?: string;
  agent_id?: string;
  agent_name?: string;
  status: TaskStatus | string; // Allow any status string for flexibility
  result?: string; // Backend uses 'result' instead of 'output'
  output?: string;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
}

interface WorkflowProgressProps {
  steps: WorkflowStep[];
  isActive?: boolean;
}

export function WorkflowProgress({ steps, isActive }: WorkflowProgressProps) {
  const [selectedStep, setSelectedStep] = useState<WorkflowStep | null>(null);

  if (steps.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-gray-500">
        {isActive ? (
          <div className="flex items-center justify-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Planning workflow...
          </div>
        ) : (
          "No workflow steps yet"
        )}
      </div>
    );
  }

  const completedSteps = steps.filter((s) => s.status === "completed").length;
  const totalSteps = steps.length;
  const progressPercent = totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;

  const statusIcons: Record<TaskStatus, React.ElementType> = {
    pending: Clock,
    in_progress: Loader2,
    completed: CheckCircle2,
    failed: XCircle,
    blocked: AlertTriangle,
  };

  const statusColors: Record<TaskStatus, string> = {
    pending: "text-gray-400",
    in_progress: "text-blue-500",
    completed: "text-green-500",
    failed: "text-red-500",
    blocked: "text-amber-500",
  };

  const lineColors: Record<TaskStatus, string> = {
    pending: "bg-gray-200 dark:bg-gray-700",
    in_progress: "bg-blue-300 dark:bg-blue-700",
    completed: "bg-green-300 dark:bg-green-700",
    failed: "bg-red-300 dark:bg-red-700",
    blocked: "bg-amber-300 dark:bg-amber-700",
  };

  return (
    <>
      <div className="space-y-4">
        {/* Progress bar */}
        <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
          Progress: {completedSteps}/{totalSteps} steps
        </span>
        {isActive && (
          <Badge variant="outline" className="text-[10px]">
            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
            Running
          </Badge>
        )}
      </div>
      <Progress value={progressPercent} className="h-2" />

      {/* Timeline */}
      <div className="space-y-0">{steps.map((step, index) => {
            const stepStatus = (step.status || "pending") as TaskStatus;
            const StatusIcon = statusIcons[stepStatus] || Clock;
            const statusColor = statusColors[stepStatus] || "text-gray-400";
            const lineColor = lineColors[stepStatus] || "bg-gray-200 dark:bg-gray-700";
            const isLast = index === steps.length - 1;

            return (
              <div
                key={step.id || `step-${step.step_number}-${index}`}
                className="flex gap-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900 rounded-lg p-2 -mx-2 transition-colors"
                onClick={() => setSelectedStep(step)}
              >
                {/* Timeline column */}
                <div className="flex flex-col items-center">
                  <div
                    className={`p-1 rounded-full border-2 ${
                      stepStatus === "completed"
                        ? "border-green-500 bg-green-50 dark:bg-green-950"
                        : stepStatus === "in_progress"
                        ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
                        : stepStatus === "failed"
                        ? "border-red-500 bg-red-50 dark:bg-red-950"
                        : "border-gray-300 dark:border-gray-600"
                    }`}
                  >
                    <StatusIcon
                      className={`h-4 w-4 ${statusColor} ${
                        stepStatus === "in_progress" ? "animate-spin" : ""
                      }`}
                    />
                  </div>
                  {!isLast && (
                    <div
                      className={`w-0.5 flex-1 min-h-[24px] ${lineColor}`}
                    />
                  )}
                </div>

                {/* Step content */}
                <div className="flex-1 pb-4 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-gray-400">
                      Step {step.step_number}
                    </span>
                    {/* Show description if title is just "task" or missing */}
                    <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {(step.title && step.title.toLowerCase() !== 'task')
                        ? step.title
                        : (step.action && step.action.toLowerCase() !== 'task')
                          ? step.action
                          : step.description
                            ? step.description.substring(0, 60) + (step.description.length > 60 ? '...' : '')
                            : `Step ${step.step_number}`}
                    </span>
                    {step.agent_name && (
                      <Badge variant="outline" className="text-[10px]">
                        👤 {step.agent_name}
                      </Badge>
                    )}
                    {step.duration_ms !== undefined && (
                      <span className="text-[10px] text-gray-400">
                        ⏱️ {step.duration_ms}ms
                      </span>
                    )}
                    <ChevronRight className="h-3 w-3 text-gray-400 ml-auto" />
                  </div>

                  {/* Only show description separately if it wasn't used as title */}
                  {step.description &&
                   (step.title && step.title.toLowerCase() !== 'task') &&
                   (step.action && step.action.toLowerCase() !== 'task') && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-1">
                      {step.description}
                    </p>
                  )}

                  {(step.output || step.result) && step.status === "completed" && (
                    <p className="text-xs text-green-600 dark:text-green-400 mt-1 line-clamp-1">
                      ✓ {typeof (step.output || step.result) === 'string'
                        ? (step.output || step.result)?.substring(0, 100)
                        : 'Output available'}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Step Details Dialog */}
      <Dialog open={!!selectedStep} onOpenChange={(open) => !open && setSelectedStep(null)}>
        <DialogContent className="max-w-3xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>Step Details</DialogTitle>
            <DialogDescription>
              Complete information about this workflow step
            </DialogDescription>
          </DialogHeader>
          {selectedStep && (
            <ScrollArea className="max-h-[60vh] pr-4">
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">
                    Step {selectedStep.step_number}: {selectedStep.title || selectedStep.action || 'Workflow Step'}
                  </h3>
                  <Badge variant={
                    selectedStep.status === 'completed' ? 'default' :
                    selectedStep.status === 'in_progress' ? 'secondary' :
                    selectedStep.status === 'failed' ? 'destructive' : 'outline'
                  }>
                    {selectedStep.status}
                  </Badge>
                </div>

                {/* Agent and Timing */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  {selectedStep.agent_name && (
                    <div>
                      <span className="text-gray-500">Agent:</span>
                      <p className="font-medium">{selectedStep.agent_name}</p>
                    </div>
                  )}
                  {selectedStep.duration_ms !== undefined && (
                    <div>
                      <span className="text-gray-500">Duration:</span>
                      <p className="font-medium">{selectedStep.duration_ms}ms</p>
                    </div>
                  )}
                  {selectedStep.started_at && (
                    <div>
                      <span className="text-gray-500">Started:</span>
                      <p className="font-medium text-xs">{new Date(selectedStep.started_at).toLocaleString()}</p>
                    </div>
                  )}
                  {selectedStep.completed_at && (
                    <div>
                      <span className="text-gray-500">Completed:</span>
                      <p className="font-medium text-xs">{new Date(selectedStep.completed_at).toLocaleString()}</p>
                    </div>
                  )}
                </div>

                {/* Description */}
                {selectedStep.description && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2">Description</h4>
                    <p className="text-sm text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-900 p-3 rounded">
                      {selectedStep.description}
                    </p>
                  </div>
                )}

                {/* Output/Result */}
                {(selectedStep.output || selectedStep.result) && (
                  <div>
                    <h4 className="text-sm font-semibold mb-2">Output</h4>
                    <pre className="text-xs bg-green-50 dark:bg-green-950 p-3 rounded overflow-x-auto whitespace-pre-wrap border border-green-200 dark:border-green-800">
                      {selectedStep.output || selectedStep.result}
                    </pre>
                  </div>
                )}
              </div>
            </ScrollArea>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
