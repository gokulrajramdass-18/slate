"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { ChevronDown, ChevronRight, CheckCircle, XCircle, Clock, SkipForward } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { actionsApi, type ActionExecutionDetail } from "@/lib/api/actions";

interface ExecutionHistoryProps {
  actionId: string;
}

export function ActionExecutionHistory({ actionId }: ExecutionHistoryProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const { data: executions, isLoading } = useQuery({
    queryKey: ["action-executions", actionId, statusFilter],
    queryFn: () =>
      actionsApi.getExecutions(actionId, { limit: 50, status_filter: statusFilter }),
  });

  const { data: stats } = useQuery({
    queryKey: ["action-stats", actionId],
    queryFn: () => actionsApi.getStats(actionId),
  });

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />;
      case "skipped":
        return <SkipForward className="h-4 w-4 text-gray-500" />;
      case "pending":
      case "running":
        return <Clock className="h-4 w-4 text-blue-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "success":
        return "bg-green-100 text-green-800";
      case "failed":
        return "bg-red-100 text-red-800";
      case "skipped":
        return "bg-gray-100 text-gray-800";
      case "pending":
      case "running":
        return "bg-blue-100 text-blue-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Total Executions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_executions}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.success_rate}%</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Avg Time</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats.average_execution_time_ms
                  ? `${Math.round(stats.average_execution_time_ms)}ms`
                  : "N/A"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Last Status</CardTitle>
            </CardHeader>
            <CardContent>
              <Badge className={getStatusColor(stats.last_execution_status || "")}>
                {stats.last_execution_status || "None"}
              </Badge>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2">
        <Button
          variant={statusFilter === undefined ? "default" : "outline"}
          size="sm"
          onClick={() => setStatusFilter(undefined)}
        >
          All
        </Button>
        <Button
          variant={statusFilter === "success" ? "default" : "outline"}
          size="sm"
          onClick={() => setStatusFilter("success")}
        >
          Success
        </Button>
        <Button
          variant={statusFilter === "failed" ? "default" : "outline"}
          size="sm"
          onClick={() => setStatusFilter("failed")}
        >
          Failed
        </Button>
        <Button
          variant={statusFilter === "skipped" ? "default" : "outline"}
          size="sm"
          onClick={() => setStatusFilter("skipped")}
        >
          Skipped
        </Button>
      </div>

      {/* Executions Table */}
      {executions && executions.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12"></TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Trigger</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Condition</TableHead>
              <TableHead>Retries</TableHead>
              <TableHead>Executed At</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {executions.map((execution) => (
              <React.Fragment key={execution.id}>
                <TableRow className="cursor-pointer hover:bg-muted/50">
                  <TableCell onClick={() => toggleRow(execution.id)}>
                    {expandedRows.has(execution.id) ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {getStatusIcon(execution.status)}
                      <Badge className={getStatusColor(execution.status)}>
                        {execution.status}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm">{execution.trigger_event}</TableCell>
                  <TableCell>
                    {execution.execution_time_ms
                      ? `${execution.execution_time_ms}ms`
                      : "-"}
                  </TableCell>
                  <TableCell>
                    {execution.condition_met === null ? (
                      <span className="text-muted-foreground">None</span>
                    ) : execution.condition_met ? (
                      <Badge variant="outline" className="bg-green-50">
                        Met
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="bg-red-50">
                        Not Met
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{execution.retry_count}</TableCell>
                  <TableCell className="text-sm">
                    {format(new Date(execution.created_at), "MMM d, yyyy HH:mm:ss")}
                  </TableCell>
                </TableRow>
                {expandedRows.has(execution.id) && (
                  <TableRow>
                    <TableCell colSpan={7} className="bg-muted/30">
                      <Collapsible open={true}>
                        <CollapsibleContent>
                          <div className="space-y-4 py-4">
                            {/* Input Data */}
                            {execution.input_data && (
                              <div>
                                <h4 className="font-semibold mb-2">Input Data:</h4>
                                <pre className="bg-background p-3 rounded-md text-xs overflow-x-auto">
                                  {JSON.stringify(execution.input_data, null, 2)}
                                </pre>
                              </div>
                            )}

                            {/* Output Data */}
                            {execution.output_data && (
                              <div>
                                <h4 className="font-semibold mb-2">Output Data:</h4>
                                <pre className="bg-background p-3 rounded-md text-xs overflow-x-auto">
                                  {JSON.stringify(execution.output_data, null, 2)}
                                </pre>
                              </div>
                            )}

                            {/* Error Message */}
                            {execution.error_message && (
                              <div>
                                <h4 className="font-semibold mb-2 text-red-600">
                                  Error:
                                </h4>
                                <pre className="bg-red-50 p-3 rounded-md text-xs overflow-x-auto text-red-900">
                                  {execution.error_message}
                                </pre>
                              </div>
                            )}

                            {/* Condition Details */}
                            {execution.condition_details && (
                              <div>
                                <h4 className="font-semibold mb-2">Condition Details:</h4>
                                <pre className="bg-background p-3 rounded-md text-xs overflow-x-auto">
                                  {JSON.stringify(execution.condition_details, null, 2)}
                                </pre>
                              </div>
                            )}

                            {/* Metadata */}
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="font-semibold">Execution ID:</span>{" "}
                                <span className="font-mono text-xs">
                                  {execution.id}
                                </span>
                              </div>
                              {execution.orchestration_id && (
                                <div>
                                  <span className="font-semibold">
                                    Orchestration ID:
                                  </span>{" "}
                                  <span className="font-mono text-xs">
                                    {execution.orchestration_id}
                                  </span>
                                </div>
                              )}
                              {execution.chat_session_id && (
                                <div>
                                  <span className="font-semibold">Chat Session ID:</span>{" "}
                                  <span className="font-mono text-xs">
                                    {execution.chat_session_id}
                                  </span>
                                </div>
                              )}
                              {execution.completed_at && (
                                <div>
                                  <span className="font-semibold">Completed At:</span>{" "}
                                  {format(
                                    new Date(execution.completed_at),
                                    "MMM d, yyyy HH:mm:ss"
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        </CollapsibleContent>
                      </Collapsible>
                    </TableCell>
                  </TableRow>
                )}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="text-center py-12 text-muted-foreground">
          No executions found
          {statusFilter && ` with status "${statusFilter}"`}
        </div>
      )}
    </div>
  );
}
