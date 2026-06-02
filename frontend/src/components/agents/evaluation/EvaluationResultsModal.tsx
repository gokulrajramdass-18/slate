"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { evaluationApi, type EvaluationRun, type EvaluationResult } from "@/lib/api/evaluations";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

interface EvaluationResultsModalProps {
  run: EvaluationRun;
  onClose: () => void;
}

export function EvaluationResultsModal({ run, onClose }: EvaluationResultsModalProps) {
  const [expandedResults, setExpandedResults] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<"all" | "passed" | "failed">("all");

  const { data: results = [], isLoading } = useQuery({
    queryKey: ["evaluation-results", run.id, filter],
    queryFn: () =>
      evaluationApi.getResults(
        run.id,
        filter === "passed",
        filter === "failed"
      ),
  });

  const toggleExpand = (resultId: string) => {
    const newExpanded = new Set(expandedResults);
    if (newExpanded.has(resultId)) {
      newExpanded.delete(resultId);
    } else {
      newExpanded.add(resultId);
    }
    setExpandedResults(newExpanded);
  };

  const passRate = run.total_cases > 0 ? (run.passed_cases / run.total_cases) * 100 : 0;

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>{run.run_name || run.dataset_name}</DialogTitle>
          <DialogDescription>
            Evaluation results for {run.agent_name}
          </DialogDescription>
        </DialogHeader>

        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4 py-4">
          <div className="p-4 bg-muted rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Total Cases</div>
            <div className="text-2xl font-bold">{run.total_cases}</div>
          </div>

          <div className="p-4 bg-green-50 dark:bg-green-950 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Passed</div>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {run.passed_cases}
            </div>
          </div>

          <div className="p-4 bg-red-50 dark:bg-red-950 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Failed</div>
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {run.failed_cases}
            </div>
          </div>

          <div className="p-4 bg-blue-50 dark:bg-blue-950 rounded-lg">
            <div className="text-sm text-muted-foreground mb-1">Pass Rate</div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {passRate.toFixed(1)}%
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="text-sm">
            <span className="text-muted-foreground">Avg Score: </span>
            <span className="font-medium">
              {run.avg_score ? (run.avg_score * 10).toFixed(2) : "N/A"}/10
            </span>
          </div>
          <div className="text-sm">
            <span className="text-muted-foreground">Avg Latency: </span>
            <span className="font-medium">
              {run.avg_latency_ms ? run.avg_latency_ms.toFixed(0) : "N/A"}ms
            </span>
          </div>
        </div>

        {/* Filters */}
        <Tabs value={filter} onValueChange={(v) => setFilter(v as any)} className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="all">All ({run.total_cases})</TabsTrigger>
            <TabsTrigger value="passed">Passed ({run.passed_cases})</TabsTrigger>
            <TabsTrigger value="failed">Failed ({run.failed_cases})</TabsTrigger>
          </TabsList>

          <TabsContent value={filter} className="mt-4">
            <ScrollArea className="h-[400px]">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : results.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No results to display
                </div>
              ) : (
                <div className="space-y-2">
                  {results.map((result) => {
                    const isExpanded = expandedResults.has(result.id);

                    return (
                      <div
                        key={result.id}
                        className="border rounded-lg overflow-hidden"
                      >
                        {/* Result Header */}
                        <div
                          className="p-4 cursor-pointer hover:bg-accent transition-colors"
                          onClick={() => toggleExpand(result.id)}
                        >
                          <div className="flex items-start gap-3">
                            {result.passed ? (
                              <CheckCircle className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                            ) : (
                              <XCircle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
                            )}

                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium truncate">
                                  {result.input_prompt.substring(0, 100)}
                                  {result.input_prompt.length > 100 && "..."}
                                </span>
                                {result.category && (
                                  <Badge variant="secondary" className="text-xs">
                                    {result.category}
                                  </Badge>
                                )}
                              </div>

                              <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                {result.overall_score !== null && result.overall_score !== undefined && (
                                  <span>
                                    Score: {(result.overall_score * 10).toFixed(1)}/10
                                  </span>
                                )}
                                <span>
                                  <Clock className="h-3 w-3 inline mr-1" />
                                  {result.execution_time_ms.toFixed(0)}ms
                                </span>
                              </div>
                            </div>

                            <div>
                              {isExpanded ? (
                                <ChevronDown className="h-5 w-5 text-muted-foreground" />
                              ) : (
                                <ChevronRight className="h-5 w-5 text-muted-foreground" />
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Expanded Details */}
                        {isExpanded && (
                          <div className="px-4 pb-4 space-y-4 border-t bg-muted/30">
                            <div>
                              <h4 className="font-medium text-sm mb-2 mt-3">Input</h4>
                              <div className="p-3 bg-background rounded text-sm">
                                {result.input_prompt}
                              </div>
                            </div>

                            {result.expected_output && (
                              <div>
                                <h4 className="font-medium text-sm mb-2">Expected Output</h4>
                                <div className="p-3 bg-background rounded text-sm">
                                  {result.expected_output}
                                </div>
                              </div>
                            )}

                            <div>
                              <h4 className="font-medium text-sm mb-2">Agent Output</h4>
                              <div className="p-3 bg-background rounded text-sm">
                                {result.agent_output || (
                                  <span className="text-muted-foreground">No output</span>
                                )}
                              </div>
                            </div>

                            {result.criteria_scores && Object.keys(result.criteria_scores).length > 0 && (
                              <div>
                                <h4 className="font-medium text-sm mb-2">Criteria Scores</h4>
                                <div className="grid grid-cols-2 gap-2">
                                  {Object.entries(result.criteria_scores).map(([criterion, score]) => (
                                    <div
                                      key={criterion}
                                      className="flex justify-between p-2 bg-background rounded text-sm"
                                    >
                                      <span className="capitalize">{criterion}:</span>
                                      <span className="font-medium">
                                        {(score * 10).toFixed(1)}/10
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Tool-call assertions: only render when the test
                                case had expectations OR the agent actually used
                                tools. */}
                            {(result.expected_tool_calls?.length || result.actual_tool_calls?.length) ? (
                              <div>
                                <h4 className="font-medium text-sm mb-2 flex items-center gap-2">
                                  Tool calls
                                  {result.tool_calls_passed === true && (
                                    <Badge className="bg-green-500/10 text-green-700 dark:text-green-400 text-xs">
                                      <CheckCircle className="w-3 h-3 mr-1" />
                                      Pass
                                    </Badge>
                                  )}
                                  {result.tool_calls_passed === false && (
                                    <Badge className="bg-red-500/10 text-red-700 dark:text-red-400 text-xs">
                                      <XCircle className="w-3 h-3 mr-1" />
                                      Fail
                                    </Badge>
                                  )}
                                </h4>
                                <div className="space-y-2">
                                  {result.expected_tool_calls?.map((expected, idx) => {
                                    const matched = result.actual_tool_calls?.find(
                                      (a) => a.tool_name === expected.tool_name
                                    );
                                    const ok = !!matched;
                                    return (
                                      <div
                                        key={`exp-${idx}`}
                                        className="flex items-start gap-2 p-2 bg-background rounded text-xs font-mono"
                                      >
                                        {ok ? (
                                          <CheckCircle className="w-3 h-3 mt-0.5 text-green-600 shrink-0" />
                                        ) : (
                                          <XCircle className="w-3 h-3 mt-0.5 text-red-600 shrink-0" />
                                        )}
                                        <div className="flex-1 min-w-0">
                                          <div>
                                            <span className="text-muted-foreground">expected: </span>
                                            {expected.tool_name}
                                            {expected.required === false && (
                                              <span className="text-muted-foreground ml-1">(optional)</span>
                                            )}
                                          </div>
                                          {expected.args_match && (
                                            <div className="text-muted-foreground truncate">
                                              args⊇ {JSON.stringify(expected.args_match)}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })}
                                  {result.actual_tool_calls
                                    ?.filter(
                                      (a) =>
                                        !result.expected_tool_calls?.some(
                                          (e) => e.tool_name === a.tool_name
                                        )
                                    )
                                    .map((actual, idx) => (
                                      <div
                                        key={`act-${idx}`}
                                        className="flex items-start gap-2 p-2 bg-background rounded text-xs font-mono opacity-70"
                                      >
                                        <span className="w-3 h-3 mt-0.5 shrink-0 text-muted-foreground">·</span>
                                        <div className="flex-1 min-w-0">
                                          <div>
                                            <span className="text-muted-foreground">also called: </span>
                                            {actual.tool_name}
                                          </div>
                                          {actual.result_snippet && (
                                            <div className="text-muted-foreground truncate">
                                              → {actual.result_snippet}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                </div>
                              </div>
                            ) : null}

                            {result.feedback && (
                              <div>
                                <h4 className="font-medium text-sm mb-2">Feedback</h4>
                                <div className="p-3 bg-background rounded text-sm">
                                  {result.feedback}
                                </div>
                              </div>
                            )}

                            {result.error_occurred && result.error_message && (
                              <div>
                                <h4 className="font-medium text-sm mb-2 text-red-600">Error</h4>
                                <div className="p-3 bg-red-50 dark:bg-red-950 rounded text-sm text-red-600">
                                  {result.error_message}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </TabsContent>
        </Tabs>

        <div className="flex justify-end pt-4 border-t">
          <Button onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
