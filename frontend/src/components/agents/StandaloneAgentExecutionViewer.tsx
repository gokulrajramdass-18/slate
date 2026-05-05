/**
 * Standalone Agent Execution Viewer
 *
 * Handles execution of standalone agents with streaming progress
 */

"use client";

import { useState, useEffect } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-client";
import * as standaloneAgentsApi from "@/lib/api/standalone-agents";
import type { StandaloneAgent, StandaloneAgentExecutionStep } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, X, CheckCircle2, AlertCircle, Clock } from "lucide-react";
import { toast } from "sonner";

interface StandaloneAgentExecutionViewerProps {
  agent: StandaloneAgent;
  onClose: () => void;
}

export function StandaloneAgentExecutionViewer({
  agent,
  onClose,
}: StandaloneAgentExecutionViewerProps) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [steps, setSteps] = useState<StandaloneAgentExecutionStep[]>([]);
  const [result, setResult] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const handleExecute = async () => {
    if (!query.trim()) {
      toast.error("Please enter a query");
      return;
    }

    setIsExecuting(true);
    setExecutionId(null);
    setSteps([]);
    setResult("");
    setError(null);

    try {
      await standaloneAgentsApi.executeStandaloneAgentStream(
        agent.id,
        {
          query: query.trim(),
          stream: true,
          max_steps: 10,
        },
        (event) => {
          switch (event.type) {
            case "metadata":
              setExecutionId(event.data.execution_id);
              break;

            case "agent_step":
              setSteps((prev) => {
                const existing = prev.find((s) => s.step_number === event.data.step_number);
                if (existing) {
                  return prev.map((s) =>
                    s.step_number === event.data.step_number
                      ? { ...s, ...event.data }
                      : s
                  );
                }
                return [...prev, event.data];
              });
              break;

            case "chunk":
              setResult((prev) => prev + (event.data.content || ""));
              break;

            case "done":
              setIsExecuting(false);
              queryClient.invalidateQueries({
                queryKey: queryKeys.standaloneAgentExecutions(agent.id),
              });
              toast.success("Execution completed");

              // Auto-close after 3 seconds
              setTimeout(() => {
                onClose();
              }, 3000);
              break;

            case "error":
              setError(event.data.error || "Execution failed");
              setIsExecuting(false);
              toast.error(event.data.error || "Execution failed");
              break;
          }
        }
      );
    } catch (err: any) {
      setError(err.message || "Failed to start execution");
      setIsExecuting(false);
      toast.error(err.message || "Failed to start execution");
    }
  };

  const handleCancel = () => {
    setIsExecuting(false);
    onClose();
  };

  return (
    <div className="space-y-4">
      {/* Query Input */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Execute Query</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your query for the agent..."
              rows={4}
              disabled={isExecuting}
            />
          </div>

          <div className="flex gap-2">
            <Button
              onClick={handleExecute}
              disabled={isExecuting || !query.trim()}
              className="flex-1"
            >
              {isExecuting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Executing...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Execute
                </>
              )}
            </Button>
            <Button variant="outline" onClick={handleCancel}>
              <X className="w-4 h-4 mr-2" />
              Close
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Execution Steps */}
      {steps.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Execution Steps</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {steps.map((step) => (
                <div
                  key={step.step_number}
                  className="flex items-start gap-3 p-3 rounded-lg border bg-muted/30"
                >
                  <div className="flex-shrink-0 mt-1">
                    {step.status === "completed" ? (
                      <CheckCircle2 className="w-5 h-5 text-green-600" />
                    ) : step.status === "failed" ? (
                      <AlertCircle className="w-5 h-5 text-red-600" />
                    ) : step.status === "running" ? (
                      <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
                    ) : (
                      <Clock className="w-5 h-5 text-gray-400" />
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">
                        Step {step.step_number}
                      </span>
                      <Badge
                        variant={
                          step.status === "completed"
                            ? "default"
                            : step.status === "failed"
                            ? "destructive"
                            : "secondary"
                        }
                        className="text-xs"
                      >
                        {step.status}
                      </Badge>
                      {step.tool_name && (
                        <Badge variant="outline" className="text-xs">
                          {step.tool_name}
                        </Badge>
                      )}
                    </div>

                    <p className="text-sm text-muted-foreground">
                      {step.action}
                    </p>

                    {step.result && (
                      <div className="mt-2 p-2 bg-background rounded text-xs font-mono whitespace-pre-wrap">
                        {step.result}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Result */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Result</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <div className="whitespace-pre-wrap">{result}</div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Card className="border-red-200 dark:border-red-900">
          <CardHeader>
            <CardTitle className="text-lg text-red-600 dark:text-red-400">
              Execution Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Info */}
      {!isExecuting && !executionId && (
        <Card className="border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0">
                <svg
                  className="w-5 h-5 text-blue-600 dark:text-blue-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <div className="text-sm text-blue-900 dark:text-blue-200 space-y-2">
                <p className="font-medium">Agent Configuration:</p>
                <ul className="list-disc list-inside space-y-1 text-blue-800 dark:text-blue-300">
                  <li>Role: {agent.role}</li>
                  <li>Tools: {agent.tool_ids?.length || 0} configured</li>
                  <li>Data Sources: {agent.data_source_ids?.length || 0} available</li>
                  {agent.model_name && <li>Model: {agent.model_name}</li>}
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
