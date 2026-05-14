"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  ExternalLink,
  Calendar,
  User,
  Settings,
  FileText,
  Trash2,
} from "lucide-react";
import { templatesApi } from "@/lib/api/templates";
import { format } from "date-fns";
import { useState } from "react";
import { Link } from 'react-router-dom';
import { toast } from "sonner";

interface TemplateExecutionHistoryProps {
  templateId: string;
}

const statusConfig = {
  completed: {
    icon: CheckCircle2,
    color: "text-green-500",
    bgColor: "bg-green-50 dark:bg-green-950",
    borderColor: "border-green-200 dark:border-green-800",
    label: "Completed",
    badgeVariant: "default" as const,
  },
  failed: {
    icon: XCircle,
    color: "text-red-500",
    bgColor: "bg-red-50 dark:bg-red-950",
    borderColor: "border-red-200 dark:border-red-800",
    label: "Failed",
    badgeVariant: "destructive" as const,
  },
  running: {
    icon: Loader2,
    color: "text-blue-500",
    bgColor: "bg-blue-50 dark:bg-blue-950",
    borderColor: "border-blue-200 dark:border-blue-800",
    label: "Running",
    badgeVariant: "secondary" as const,
  },
  pending: {
    icon: Clock,
    color: "text-amber-500",
    bgColor: "bg-amber-50 dark:bg-amber-950",
    borderColor: "border-amber-200 dark:border-amber-800",
    label: "Pending",
    badgeVariant: "outline" as const,
  },
};

export function TemplateExecutionHistory({ templateId }: TemplateExecutionHistoryProps) {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [executionToDelete, setExecutionToDelete] = useState<string | null>(null);

  const { data: executions, isLoading } = useQuery({
    queryKey: ["templates", templateId, "executions"],
    queryFn: () => templatesApi.getExecutions(templateId),
  });

  const deleteMutation = useMutation({
    mutationFn: (executionId: string) => templatesApi.deleteExecution(templateId, executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates", templateId, "executions"] });
      toast.success("Execution deleted successfully");
      setDeleteDialogOpen(false);
      setExecutionToDelete(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to delete execution");
    },
  });

  const handleDeleteClick = (executionId: string) => {
    setExecutionToDelete(executionId);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (executionToDelete) {
      deleteMutation.mutate(executionToDelete);
    }
  };

  // Filter executions
  const filteredExecutions = executions?.filter((execution) => {
    const matchesStatus = statusFilter === "all" || execution.status === statusFilter;
    const matchesSearch = searchQuery === "" ||
      execution.workspace_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      execution.orchestration_id?.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (!executions || executions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Execution History</CardTitle>
          <CardDescription>No executions yet for this template</CardDescription>
        </CardHeader>
        <CardContent className="text-center py-8">
          <p className="text-muted-foreground">
            This template hasn't been executed yet. Create a schedule or run it manually to see execution history.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Execution History</CardTitle>
            <CardDescription>
              {executions.length} total execution{executions.length !== 1 ? "s" : ""}
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Search..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-[200px]"
            />
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="All Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {filteredExecutions && filteredExecutions.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            No executions match your filters
          </div>
        ) : (
          <div className="space-y-4">
            {filteredExecutions?.map((execution, index) => {
              const status = statusConfig[execution.status as keyof typeof statusConfig] || statusConfig.pending;
              const StatusIcon = status.icon;

              return (
                <div
                  key={execution.orchestration_id || `execution-${index}`}
                  className={`border rounded-lg p-4 ${status.borderColor} ${status.bgColor} transition-all hover:shadow-md`}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3 flex-1">
                      <div className={`${status.color}`}>
                        <StatusIcon className={`h-5 w-5 ${execution.status === 'running' ? 'animate-spin' : ''}`} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium">{execution.workspace_name || "Unnamed Workspace"}</h3>
                          <code className="text-xs bg-muted px-2 py-0.5 rounded font-mono">
                            {execution.execution_id.substring(0, 8)}
                          </code>
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground flex-wrap">
                          <div className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            <span>
                              {execution.executed_at
                                ? (() => {
                                    try {
                                      const date = new Date(execution.executed_at);
                                      return isNaN(date.getTime()) ? "Invalid date" : format(date, "PPp");
                                    } catch {
                                      return "Invalid date";
                                    }
                                  })()
                                : "Not executed yet"
                              }
                            </span>
                          </div>
                          {(execution.duration_seconds || execution.duration_ms) && (
                            <div className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              <span>
                                {execution.duration_seconds
                                  ? `${execution.duration_seconds}s`
                                  : execution.duration_ms
                                    ? `${(execution.duration_ms / 1000).toFixed(1)}s`
                                    : 'N/A'}
                              </span>
                            </div>
                          )}
                          {execution.user_id && (
                            <div className="flex items-center gap-1">
                              <User className="h-3 w-3" />
                              <span className="truncate max-w-[150px]">{execution.user_id}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    <Badge variant={status.badgeVariant}>{status.label}</Badge>
                  </div>

                  {/* Parameters Display */}
                  {execution.parameters && Object.keys(execution.parameters).length > 0 && (
                    <div className="mb-3 p-3 bg-background/50 rounded border">
                      <div className="flex items-center gap-2 mb-2">
                        <Settings className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Parameters</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {Object.entries(execution.parameters).map(([key, value]) => (
                          <div key={key} className="flex items-center gap-2">
                            <span className="text-muted-foreground">{key}:</span>
                            <span className="font-mono text-xs bg-background px-2 py-0.5 rounded">
                              {String(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Execution Details */}
                  <div className="flex items-center justify-between gap-2">
                    {execution.schedule_id && (
                      <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        <span>Scheduled</span>
                      </div>
                    )}

                    <div className="flex gap-2 ml-auto">
                      {/* Direct link to result note */}
                      {execution.result_note_id && execution.workspace_id && (
                        <Link to={`/workspaces/${execution.workspace_id}?noteId=${execution.result_note_id}`}>
                          <Button variant="default" size="sm">
                            <FileText className="h-4 w-4 mr-2" />
                            View Results
                          </Button>
                        </Link>
                      )}
                      {execution.workspace_id && (
                        <Link to={`/workspaces/${execution.workspace_id}`}>
                          <Button variant="outline" size="sm">
                            <ExternalLink className="h-4 w-4 mr-2" />
                            View Workspace
                          </Button>
                        </Link>
                      )}
                      {/* Delete button - only show for completed or failed executions */}
                      {(execution.status === "completed" || execution.status === "failed") && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteClick(execution.execution_id)}
                          className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Error Message */}
                  {execution.status === "failed" && execution.error && (
                    <div className="mt-3 p-3 bg-destructive/10 border border-destructive/20 rounded text-sm">
                      <p className="font-medium text-destructive mb-1">Error:</p>
                      <p className="text-destructive/80">{execution.error}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Execution</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                <p>Are you sure you want to delete this execution? This will permanently remove:</p>
                <ul className="list-disc list-inside mt-2 space-y-1">
                  <li>The execution record</li>
                  <li>The execution folder in the workspace</li>
                  <li>All result notes and outputs</li>
                </ul>
                <p className="mt-2">This action cannot be undone.</p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
