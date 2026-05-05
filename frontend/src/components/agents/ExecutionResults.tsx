"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api/agents";
import { queryKeys } from "@/lib/query-client";
import type { TeamExecution, WorkflowStep } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { EvaluationPanel } from "./EvaluationPanel";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
  PlayCircle,
  Eye,
  Calendar,
  Award,
} from "lucide-react";

interface ExecutionResultsProps {
  teamId: string;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    idle: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    pending: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    running: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
    error: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    cancelled: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  };

  const icons: Record<string, any> = {
    idle: Clock,
    pending: Clock,
    running: Loader2,
    completed: CheckCircle2,
    error: XCircle,
    cancelled: XCircle,
  };

  const Icon = icons[status] || Clock;
  const isRunning = status === "running";

  return (
    <Badge className={`${colors[status] || colors.idle} border-0`}>
      <Icon className={`w-3 h-3 mr-1 ${isRunning ? "animate-spin" : ""}`} />
      {status}
    </Badge>
  );
}

function formatDuration(ms?: number): string {
  if (!ms) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatDate(dateString?: string): string {
  if (!dateString) return "—";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function StepViewer({ step }: { step: WorkflowStep }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border bg-card">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium">
        {step.step_number}
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{step.title}</span>
          <StatusBadge status={step.status} />
        </div>
        {step.description && (
          <p className="text-xs text-muted-foreground">{step.description}</p>
        )}
        {step.agent_name && (
          <p className="text-xs text-muted-foreground">
            Agent: <span className="font-medium">{step.agent_name}</span>
          </p>
        )}
        {step.duration_ms && (
          <p className="text-xs text-muted-foreground">
            Duration: {formatDuration(step.duration_ms)}
          </p>
        )}
        {step.output && (
          <div className="mt-2">
            <details className="text-xs">
              <summary className="cursor-pointer text-primary hover:underline">
                View output
              </summary>
              <pre className="mt-2 p-2 bg-gray-50 dark:bg-gray-900 rounded text-xs overflow-x-auto">
                {typeof step.output === "string"
                  ? step.output
                  : JSON.stringify(step.output, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}

function ExecutionDetailDialog({
  execution,
  open,
  onClose,
}: {
  execution: TeamExecution;
  open: boolean;
  onClose: () => void;
}) {
  // Fetch evaluations for this execution
  const { data: evaluationsData } = useQuery({
    queryKey: ["execution-evaluations", execution.id],
    queryFn: () => agentsApi.getExecutionEvaluations(execution.id),
    enabled: open,
  });

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <PlayCircle className="w-5 h-5" />
            Execution Details
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Execution Info */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Query</h3>
              <div className="flex items-center gap-2">
                <StatusBadge status={execution.status} />
                {evaluationsData && evaluationsData.total > 0 && (
                  <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                    <Award className="mr-1 h-3 w-3" />
                    Evaluated
                  </Badge>
                )}
              </div>
            </div>
            <p className="text-sm text-muted-foreground bg-gray-50 dark:bg-gray-900 p-3 rounded">
              {execution.query}
            </p>
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <span className="text-muted-foreground">Started:</span>{" "}
                <span className="font-medium">
                  {new Date(execution.started_at).toLocaleString()}
                </span>
              </div>
              {execution.completed_at && (
                <div>
                  <span className="text-muted-foreground">Completed:</span>{" "}
                  <span className="font-medium">
                    {new Date(execution.completed_at).toLocaleString()}
                  </span>
                </div>
              )}
              {execution.total_duration_ms && (
                <div>
                  <span className="text-muted-foreground">Duration:</span>{" "}
                  <span className="font-medium">
                    {formatDuration(execution.total_duration_ms)}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Judge Evaluations */}
          {evaluationsData && evaluationsData.total > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Judge Evaluations</h3>
              <EvaluationPanel evaluations={evaluationsData.evaluations} />
            </div>
          )}

          {/* Steps */}
          {execution.steps && execution.steps.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">
                Execution Steps ({execution.steps.length})
              </h3>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {execution.steps.map((step) => (
                  <StepViewer key={step.id} step={step} />
                ))}
              </div>
            </div>
          )}

          {/* Result */}
          {execution.result && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Result</h3>
              <pre className="text-sm bg-gray-50 dark:bg-gray-900 p-4 rounded overflow-x-auto max-h-64">
                {typeof execution.result === "string"
                  ? execution.result
                  : JSON.stringify(execution.result, null, 2)}
              </pre>
            </div>
          )}

          {/* Messages */}
          {execution.messages && execution.messages.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">
                Agent Messages ({execution.messages.length})
              </h3>
              <ScrollArea className="h-64 border rounded-lg p-3">
                <div className="space-y-2">
                  {execution.messages.map((msg: any) => (
                    <div
                      key={msg.id}
                      className="p-2 bg-gray-50 dark:bg-gray-900 rounded text-xs"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium">{msg.role || "system"}:</span>
                        <span className="text-muted-foreground">
                          {formatDate(msg.created)}
                        </span>
                      </div>
                      <p className="text-muted-foreground">{msg.content}</p>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function ExecutionCard({ execution }: { execution: TeamExecution }) {
  const [showDetails, setShowDetails] = useState(false);

  const successfulSteps = execution.steps?.filter(
    (s) => s.status === "completed"
  ).length || 0;
  const totalSteps = execution.steps?.length || 0;

  // Check if execution has evaluations
  const hasEvaluations = (execution as any).has_evaluations || false;

  return (
    <>
      <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => setShowDetails(true)}>
        <CardContent className="p-4">
          <div className="space-y-3">
            {/* Header */}
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-medium line-clamp-2 mb-1">
                  {execution.query}
                </h4>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Calendar className="w-3 h-3" />
                  {formatDate(execution.started_at)}
                  {execution.total_duration_ms && (
                    <>
                      <span>•</span>
                      <Clock className="w-3 h-3" />
                      {formatDuration(execution.total_duration_ms)}
                    </>
                  )}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <StatusBadge status={execution.status} />
                {hasEvaluations && (
                  <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 text-xs">
                    <Award className="mr-1 h-3 w-3" />
                    Evaluated
                  </Badge>
                )}
              </div>
            </div>

            {/* Progress */}
            {totalSteps > 0 && (
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Progress</span>
                  <span className="font-medium">
                    {successfulSteps}/{totalSteps} steps
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-800 rounded-full h-1.5">
                  <div
                    className="bg-primary h-1.5 rounded-full transition-all"
                    style={{
                      width: `${(successfulSteps / totalSteps) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {/* View Details Button */}
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-between"
              onClick={(e) => {
                e.stopPropagation();
                setShowDetails(true);
              }}
            >
              <span className="text-xs">View Details</span>
              <ChevronRight className="w-3 h-3" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <ExecutionDetailDialog
        execution={execution}
        open={showDetails}
        onClose={() => setShowDetails(false)}
      />
    </>
  );
}

export function ExecutionResults({ teamId }: ExecutionResultsProps) {
  const { data: executionsData, isLoading } = useQuery({
    queryKey: [...queryKeys.agentTeams, teamId, "executions"],
    queryFn: async () => {
      const response = await agentsApi.listExecutions(teamId);
      // Backend returns {executions: [...], total: N}
      return response;
    },
    refetchInterval: 5000, // Poll every 5 seconds for updates
  });

  // Handle both array and object responses
  const executions = Array.isArray(executionsData)
    ? executionsData
    : (executionsData as any)?.executions || [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (executions.length === 0) {
    return (
      <Card>
        <CardContent className="py-16 text-center space-y-4">
          <PlayCircle className="w-12 h-12 mx-auto text-muted-foreground" />
          <div className="space-y-1">
            <p className="font-medium text-lg">No execution history</p>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Run a query in the Execute tab to see execution results here.
              Past executions will be displayed with their steps, messages, and outcomes.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Execution History ({executions.length})
        </h3>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {executions.map((execution: TeamExecution) => (
          <ExecutionCard key={execution.id} execution={execution} />
        ))}
      </div>
    </div>
  );
}
