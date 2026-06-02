"use client";

import { useState, useCallback, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Users,
  Play,
  Loader2,
  Send,
  AlertCircle,
  ArrowLeft,
  Save,
  Library,
  Trash2,
  Search,
  ChevronLeft,
  ChevronRight,
  Calendar,
  Clock,
  CheckCircle2,
  Award,
  HelpCircle,
  Bot,
  Wrench,
} from "lucide-react";
import { AgentCard } from "./AgentCard";
import { TaskBoard } from "./TaskBoard";
import { MessageTimeline } from "./MessageTimeline";
import { WorkflowProgress } from "./WorkflowProgress";
import { EvaluationPanel } from "./EvaluationPanel";
import { useAgentTeam, useTeamExecutions } from "@/lib/hooks/use-api";
import { agentsApi } from "@/lib/api";
import type { AwaitingInputEvent } from "@/lib/api/agents";
import { userQueryPromptsApi } from "@/lib/api/user-query-prompts";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-client";
import { useRouter, useSearchParams } from "@/lib/routing/navigation";
import { toast } from "sonner";
import { useEffect } from "react";
import type {
  AgentTeam,
  TeamExecution,
  AgentTask,
  AgentMessage,
  WorkflowStep,
} from "@/lib/types";
import { ORCHESTRATION_PATTERNS } from "@/lib/types";

interface AgentTeamViewerProps {
  teamId: string;
}

export function AgentTeamViewer({ teamId }: AgentTeamViewerProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const initialTab = searchParams.get("tab") || "execute";
  const historyOnly = searchParams.get("history_only") === "true";
  const executionId = searchParams.get("execution");

  // State declarations - MUST come before any hooks that use them
  const [query, setQuery] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentExecution, setCurrentExecution] = useState<Partial<TeamExecution> | null>(null);
  const [liveSteps, setLiveSteps] = useState<WorkflowStep[]>([]);
  const [liveTasks, setLiveTasks] = useState<AgentTask[]>([]);
  const [liveMessages, setLiveMessages] = useState<AgentMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>(initialTab);

  // Pending clarification (popup state). Set when an agent has paused with
  // a question; cleared on submit or cancel.
  const [clarification, setClarification] = useState<AwaitingInputEvent | null>(null);
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [clarificationSubmitting, setClarificationSubmitting] = useState(false);

  // History → click-to-view dialog. Holds the full execution row so the
  // dialog can render Output / Agent Steps / Messages tabs without
  // navigating away.
  const [historyDetail, setHistoryDetail] = useState<TeamExecution | null>(null);

  // Data fetching hooks - can now safely reference state variables
  const { data: team, isLoading: teamLoading } = useAgentTeam(teamId);
  const { data: executions = [] } = useTeamExecutions(teamId);

  // Fetch evaluations for current execution
  const { data: evaluationsData } = useQuery({
    queryKey: ["execution-evaluations", currentExecution?.id],
    queryFn: () =>
      currentExecution?.id ? agentsApi.getExecutionEvaluations(currentExecution.id) : null,
    enabled: !!currentExecution?.id,
  });

  // Prompt management
  const [showSavePromptDialog, setShowSavePromptDialog] = useState(false);
  const [showLoadPromptDialog, setShowLoadPromptDialog] = useState(false);
  const [promptName, setPromptName] = useState("");
  const [promptDescription, setPromptDescription] = useState("");
  const [promptCategory, setPromptCategory] = useState("");

  // History filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"date_desc" | "date_asc">("date_desc");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Load specific execution if executionId is in URL
  useEffect(() => {
    if (executionId && executions.length > 0) {
      const execution = executions.find((exec: any) => exec.id === executionId);
      if (execution) {
        setCurrentExecution(execution);
        setLiveSteps(execution.steps || []);
        setLiveTasks(execution.tasks || []);
        setLiveMessages(execution.messages || []);
        setQuery(execution.query || "");
        // Make sure we're on the execute tab to show the execution
        setActiveTab("execute");
      }
    }
  }, [executionId, executions]);

  // Filter and sort executions
  const filteredExecutions = executions.filter((exec: any) => {
    const matchesSearch = exec.query?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || exec.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const sortedExecutions = [...filteredExecutions].sort((a: any, b: any) => {
    const dateA = new Date(a.started_at).getTime();
    const dateB = new Date(b.started_at).getTime();
    return sortBy === "date_desc" ? dateB - dateA : dateA - dateB;
  });

  const totalPages = Math.ceil(sortedExecutions.length / itemsPerPage);
  const paginatedExecutions = sortedExecutions.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Fetch saved prompts
  const { data: savedPrompts = [] } = useQuery({
    queryKey: queryKeys.userQueryPromptsByTeam(teamId),
    queryFn: () => userQueryPromptsApi.list({ team_id: teamId }),
  });

  // Save prompt mutation
  const savePromptMutation = useMutation({
    mutationFn: userQueryPromptsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.userQueryPromptsByTeam(teamId) });
      toast.success("Prompt saved");
      setShowSavePromptDialog(false);
      setPromptName("");
      setPromptDescription("");
      setPromptCategory("");
    },
    onError: () => {
      toast.error("Failed to save prompt");
    },
  });

  // Delete prompt mutation
  const deletePromptMutation = useMutation({
    mutationFn: userQueryPromptsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.userQueryPromptsByTeam(teamId) });
      toast.success("Prompt deleted");
    },
    onError: () => {
      toast.error("Failed to delete prompt");
    },
  });

  // Auto-refresh when there are running executions
  useEffect(() => {
    const hasRunningExecutions = executions.some((exec: any) =>
      exec.status === "running" || exec.status === "executing" || exec.status === "planning"
    );

    // Auto-refresh only if there are running executions
    // Note: We don't need to check isExecuting here because the live SSE updates
    // will handle the current execution, and auto-refresh is for OTHER running executions
    if (hasRunningExecutions) {
      const interval = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: queryKeys.teamExecutions(teamId) });
      }, 3000); // Refresh every 3 seconds

      return () => clearInterval(interval);
    }
  }, [executions, teamId, queryClient]);

  const handleExecute = useCallback(async () => {
    if (!query.trim() || isExecuting) return;

    setIsExecuting(true);
    setError(null);
    setLiveSteps([]);
    setLiveTasks([]);
    setLiveMessages([]);
    setCurrentExecution({ status: "planning", query });

    // Switch to Execute tab to show live progress
    setActiveTab("execute");

    // Set up timeout for long-running executions (5 minutes)
    const timeoutId = setTimeout(() => {
      if (isExecuting) {
        setError("Execution timed out after 5 minutes. The team may still be working in the background.");
        setIsExecuting(false);
        setCurrentExecution((prev) => prev ? { ...prev, status: "error" } : prev);
        toast.error("Execution timed out", {
          description: "The execution took too long. Please check the History tab for results.",
        });
      }
    }, 5 * 60 * 1000); // 5 minutes

    try {
      await agentsApi.executeTeam(
        teamId,
        { query },
        // onStep
        (step: WorkflowStep) => {
          console.log("[AgentTeamViewer] onStep called with:", step);
          setLiveSteps((prev) => {
            const existing = prev.findIndex((s) => s.id === step.id);
            if (existing >= 0) {
              const updated = [...prev];
              updated[existing] = step;
              console.log("[AgentTeamViewer] Updated existing step:", updated);
              return updated;
            }
            console.log("[AgentTeamViewer] Added new step, total:", prev.length + 1);
            return [...prev, step];
          });
          setCurrentExecution((prev) => prev ? { ...prev, status: "executing" } : prev);
        },
        // onMessage
        (message: AgentMessage) => {
          console.log("[AgentTeamViewer] onMessage called with:", message);
          setLiveMessages((prev) => {
            console.log("[AgentTeamViewer] Added message, total:", prev.length + 1);
            return [...prev, message];
          });
        },
        // onTaskUpdate
        (task: AgentTask) => {
          console.log("[AgentTeamViewer] onTaskUpdate called with:", task);
          setLiveTasks((prev) => {
            const existing = prev.findIndex((t) => t.id === task.id);
            if (existing >= 0) {
              const updated = [...prev];
              updated[existing] = task;
              console.log("[AgentTeamViewer] Updated existing task:", updated);
              return updated;
            }
            console.log("[AgentTeamViewer] Added new task, total:", prev.length + 1);
            return [...prev, task];
          });
        },
        // onComplete
        (result: TeamExecution) => {
          clearTimeout(timeoutId);
          setCurrentExecution(result);
          setIsExecuting(false);
          toast.success("Execution completed", {
            description: "Your team has finished working on the query.",
          });
          // Refresh execution list
          queryClient.invalidateQueries({ queryKey: queryKeys.teamExecutions(teamId) });
        },
        // onError
        (err: string) => {
          clearTimeout(timeoutId);
          setError(err);
          setIsExecuting(false);
          setCurrentExecution((prev) => prev ? { ...prev, status: "error" } : prev);
          toast.error("Execution failed", {
            description: err || "An error occurred during execution.",
          });
        },
        // onAwaitingInput
        (info: AwaitingInputEvent) => {
          clearTimeout(timeoutId);
          setIsExecuting(false);
          setClarification(info);
          setClarificationAnswer("");
          setCurrentExecution((prev) =>
            prev ? { ...prev, id: info.execution_id, status: "awaiting_input" as any } : prev,
          );
          toast.info(`${info.sender_name || "Agent"} needs your input`, {
            description: "A clarifying question is waiting.",
          });
        }
      );
    } catch (err: any) {
      clearTimeout(timeoutId);
      const errorMessage = err.message || "Execution failed";
      setError(errorMessage);
      setIsExecuting(false);
      setCurrentExecution((prev) => prev ? { ...prev, status: "error" } : prev);
      toast.error("Execution failed", {
        description: errorMessage,
      });
    }
  }, [teamId, query, isExecuting, queryClient]);

  // Ref-based re-entry guard. State (clarificationSubmitting) flips
  // *after* React commits; a fast double-event (⌘+Enter + click, or two
  // Enter keystrokes) lands on the same render and would otherwise fire
  // two POSTs to the same clarification id — backend then 409s the
  // second one with "cannot answer twice". A ref reads/writes
  // synchronously so the second call sees the in-flight flag immediately.
  const submittingClarificationIdRef = useRef<string | null>(null);

  // Submit the user's answer and re-attach to the resume SSE stream. Reuses
  // the same setters as executeTeam so the live timeline keeps growing.
  const submitClarification = useCallback(async () => {
    if (!clarification) return;
    // Re-entry guard: if a POST is already in flight for this exact
    // clarification, drop the duplicate silently.
    if (submittingClarificationIdRef.current === clarification.clarification_id) {
      return;
    }
    const text = clarificationAnswer.trim();
    if (!text) {
      toast.error("Please enter an answer");
      return;
    }
    submittingClarificationIdRef.current = clarification.clarification_id;
    const inflightId = clarification.clarification_id;
    setClarificationSubmitting(true);
    setIsExecuting(true);
    setCurrentExecution((prev) =>
      prev ? { ...prev, status: "executing" as any } : prev,
    );
    try {
      await agentsApi.answerClarification(
        teamId,
        clarification.execution_id,
        clarification.clarification_id,
        text,
        {
          onMessage: (m) => setLiveMessages((prev) => [...prev, m]),
          onTaskUpdate: (t) =>
            setLiveTasks((prev) => {
              const i = prev.findIndex((x) => x.id === t.id);
              if (i >= 0) {
                const copy = [...prev];
                copy[i] = t;
                return copy;
              }
              return [...prev, t];
            }),
          onAwaitingInput: (info) => {
            // Another question — keep the loop going.
            setIsExecuting(false);
            setClarification(info);
            setClarificationAnswer("");
            toast.info(`${info.sender_name || "Agent"} needs more input`);
          },
          onComplete: (result) => {
            setCurrentExecution(result);
            setIsExecuting(false);
            setClarification(null);
            toast.success("Execution completed");
            queryClient.invalidateQueries({ queryKey: queryKeys.teamExecutions(teamId) });
          },
          onError: (err) => {
            setError(err);
            setIsExecuting(false);
            toast.error("Resume failed", { description: err });
          },
        },
      );
    } finally {
      // Only clear the guard if we still own it — defensive against the
      // unlikely case where another path already cleared it.
      if (submittingClarificationIdRef.current === inflightId) {
        submittingClarificationIdRef.current = null;
      }
      setClarificationSubmitting(false);
    }
  }, [clarification, clarificationAnswer, teamId, queryClient]);

  const cancelClarification = useCallback(() => {
    setClarification(null);
    setClarificationAnswer("");
    setIsExecuting(false);
    setCurrentExecution((prev) => prev ? { ...prev, status: "error" as any } : prev);
    toast.info("Execution cancelled");
  }, []);

  if (teamLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!team) {
    return (
      <div className="flex items-center justify-center p-8 text-gray-500">
        Team not found
      </div>
    );
  }

  const teamStatusColors: Record<string, string> = {
    idle: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    planning: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    executing: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    running: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 animate-pulse",
    reviewing: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
    completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    error: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
    failed: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  };

  const displayStatus = currentExecution?.status || team.status;

  // If history_only mode, show simplified view
  if (historyOnly) {
    return (
      <div className="h-full overflow-auto p-6">
        <div className="space-y-6 max-w-7xl mx-auto px-4 md:px-6 lg:px-8">
        {/* Back Button and Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push("/agents")}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Agents
          </Button>
        </div>

        {/* Team Header */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900">
                  <Users className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <CardTitle>{team.name} - Execution History</CardTitle>
                  {team.description && (
                    <CardDescription>{team.description}</CardDescription>
                  )}
                </div>
              </div>
            </div>
          </CardHeader>
        </Card>

        {/* History Card */}
        <Card>
          <CardHeader>
            <CardTitle>Execution History</CardTitle>
            <CardDescription>
              {sortedExecutions.length} {sortedExecutions.length === 1 ? "execution" : "executions"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Filters */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search executions..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="flex-1"
                />
              </div>
              <Select value={statusFilter} onValueChange={(v) => {
                setStatusFilter(v);
                setCurrentPage(1);
              }}>
                <SelectTrigger>
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-gray-900">
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="running">Running</SelectItem>
                  <SelectItem value="executing">Executing</SelectItem>
                  <SelectItem value="planning">Planning</SelectItem>
                  <SelectItem value="error">Error</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-gray-900">
                  <SelectItem value="date_desc">Newest First</SelectItem>
                  <SelectItem value="date_asc">Oldest First</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Execution List */}
            {sortedExecutions.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <p>No executions found</p>
              </div>
            ) : (
              <>
                <ScrollArea className="h-[500px]">
                  <div className="space-y-3">
                    {paginatedExecutions.map((execution: any) => (
                      <div
                        key={execution.id}
                        className="p-4 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                        onClick={() => {
                          setHistoryDetail(execution as TeamExecution);
                        }}
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              {execution.status === "running" && (
                                <Loader2 className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" />
                              )}
                              <p className="font-medium text-sm truncate">{execution.query}</p>
                            </div>
                            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                {new Date(execution.started_at).toLocaleDateString()}
                              </span>
                              <span className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {new Date(execution.started_at).toLocaleTimeString()}
                              </span>
                              {execution.status === "running" && (
                                <span className="text-blue-600 dark:text-blue-400 font-medium animate-pulse">
                                  • Executing...
                                </span>
                              )}
                              {execution.result && execution.status === "completed" && (
                                <span className="text-green-600 dark:text-green-400">
                                  • Click to view result
                                </span>
                              )}
                            </div>
                          </div>
                          <Badge className={teamStatusColors[execution.status] || teamStatusColors.idle}>
                            {execution.status}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between pt-4 border-t">
                    <p className="text-xs text-muted-foreground">
                      Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, sortedExecutions.length)} of {sortedExecutions.length}
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </Button>
                      <span className="text-sm">
                        Page {currentPage} of {totalPages}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                      >
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back Button and Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/agents")}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Agents
        </Button>
      </div>

      {/* Team Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900">
                <Users className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <CardTitle>{team.name}</CardTitle>
                {team.description && (
                  <CardDescription>{team.description}</CardDescription>
                )}
                {team.orchestration_pattern && (
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant="secondary" className="text-[10px] font-medium">
                      {ORCHESTRATION_PATTERNS.find(
                        (p) => p.key === team.orchestration_pattern
                      )?.label || team.orchestration_pattern}
                    </Badge>
                    <span className="text-[11px] text-muted-foreground">
                      {ORCHESTRATION_PATTERNS.find(
                        (p) => p.key === team.orchestration_pattern
                      )?.tagline}
                    </span>
                  </div>
                )}
              </div>
            </div>
            <Badge className={teamStatusColors[displayStatus] || teamStatusColors.idle}>
              {isExecuting && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
              {displayStatus}
            </Badge>
          </div>
        </CardHeader>
      </Card>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="execute">Execute</TabsTrigger>
          <TabsTrigger value="prompts">Prompts</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        {/* Execute Tab */}
        <TabsContent value="execute" className="space-y-4">
          {/* Viewing Past Execution Banner */}
          {executionId && currentExecution && !isExecuting && (
            <Card className="bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800">
              <CardContent className="pt-4">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
                    <div>
                      <p className="font-medium text-blue-900 dark:text-blue-100">
                        Viewing Past Execution
                      </p>
                      <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                        You're viewing results from a previous execution. The query input below shows the original query.
                      </p>
                      {currentExecution.started_at && (
                        <p className="text-xs text-blue-600 dark:text-blue-400 mt-1 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Executed on {new Date(currentExecution.started_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      // Clear execution and go back to fresh state
                      router.push(`/agents/teams/${teamId}/execute?tab=execute`);
                      setCurrentExecution(null);
                      setLiveSteps([]);
                      setLiveTasks([]);
                      setLiveMessages([]);
                      setQuery("");
                      setError(null);
                    }}
                    className="shrink-0"
                  >
                    New Execution
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardContent className="pt-6 space-y-4">
              {/* Query Input */}
              <div className="space-y-2">
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter a query for the team to work on..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !isExecuting && query.trim() && !executionId) {
                        handleExecute();
                      }
                    }}
                    disabled={isExecuting || !!executionId}
                    className="flex-1"
                  />
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setShowLoadPromptDialog(true)}
                    disabled={isExecuting || !!executionId}
                    title="Load saved prompt"
                  >
                    <Library className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setShowSavePromptDialog(true)}
                    disabled={isExecuting || !query.trim() || !!executionId}
                    title="Save current query"
                  >
                    <Save className="h-4 w-4" />
                  </Button>
                  <Button
                    onClick={handleExecute}
                    disabled={isExecuting || !query.trim() || !!executionId}
                    className="min-w-[120px]"
                  >
                    {isExecuting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="ml-2">Running...</span>
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        <span className="ml-2">Execute</span>
                      </>
                    )}
                  </Button>
                </div>
                {savedPrompts.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {savedPrompts.length} saved {savedPrompts.length === 1 ? "prompt" : "prompts"} available
                  </p>
                )}
              </div>

              {error && (
                <Card className="border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950">
                  <CardContent className="pt-6">
                    <div className="space-y-3">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1 space-y-2">
                          <h3 className="font-semibold text-red-900 dark:text-red-100">
                            Execution Failed
                          </h3>
                          <p className="text-sm text-red-800 dark:text-red-200">
                            {error}
                          </p>
                          {error.includes("timeout") && (
                            <p className="text-xs text-red-700 dark:text-red-300">
                              The execution took longer than expected. Check the History tab to see if it completed.
                            </p>
                          )}
                          {error.includes("No language model") && (
                            <p className="text-xs text-red-700 dark:text-red-300">
                              Please configure a language model in Settings → API Keys before executing.
                            </p>
                          )}
                          {error.includes("Failed to fetch") && (
                            <p className="text-xs text-red-700 dark:text-red-300">
                              Network error. Please check your connection and ensure the backend is running.
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setError(null);
                            handleExecute();
                          }}
                          className="bg-white dark:bg-gray-900"
                        >
                          <Play className="h-3 w-3 mr-1" />
                          Retry
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setError(null);
                            setCurrentExecution(null);
                            setLiveSteps([]);
                            setLiveTasks([]);
                            setLiveMessages([]);
                          }}
                        >
                          Dismiss
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>

          {/* Team Members */}
          {team.agents.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Team Members ({team.agents.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {team.agents.map((agent) => {
                    const agentTask = liveTasks.find(
                      (t) => t.assigned_agent_id === agent.id && t.status === "in_progress"
                    );
                    return (
                      <AgentCard
                        key={agent.id}
                        agent={agent}
                        isActive={agent.status === "working"}
                        currentTask={agentTask?.title}
                      />
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Current Execution - Compact View */}
          {(liveTasks.length > 0 || liveMessages.length > 0 || currentExecution?.result) && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Execution Details</CardTitle>
                  <div className="flex items-center gap-2">
                    {liveTasks.length > 0 && (
                      <Badge variant="outline" className="text-[10px]">
                        {liveTasks.filter(t => t.status === 'completed').length}/{liveTasks.length} tasks
                      </Badge>
                    )}
                    {liveMessages.length > 0 && (
                      <Badge variant="outline" className="text-[10px]">
                        {liveMessages.length} messages
                      </Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue={
                  currentExecution?.result
                    ? "result"
                    : liveTasks.length > 0 ? "tasks" : "messages"
                } className="w-full">
                  <TabsList className="grid w-full" style={{ gridTemplateColumns: `repeat(${[liveTasks.length > 0, liveMessages.length > 0, currentExecution?.result, evaluationsData && evaluationsData.total > 0].filter(Boolean).length}, 1fr)` }}>
                    {liveTasks.length > 0 && <TabsTrigger value="tasks">Tasks</TabsTrigger>}
                    {liveMessages.length > 0 && <TabsTrigger value="messages">Messages</TabsTrigger>}
                    {currentExecution?.result && <TabsTrigger value="result">Result</TabsTrigger>}
                    {evaluationsData && evaluationsData.total > 0 && (
                      <TabsTrigger value="evaluation">
                        <Award className="mr-2 h-4 w-4" />
                        Evaluation
                        <Badge className="ml-2 bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                          {evaluationsData.total}
                        </Badge>
                      </TabsTrigger>
                    )}
                  </TabsList>
                  {liveTasks.length > 0 && (
                    <TabsContent value="tasks" className="mt-4">
                      <TaskBoard tasks={liveTasks} />
                    </TabsContent>
                  )}
                  {liveMessages.length > 0 && (
                    <TabsContent value="messages" className="mt-4">
                      <MessageTimeline messages={liveMessages} />
                    </TabsContent>
                  )}
                  {currentExecution?.result && (
                    <TabsContent value="result" className="mt-4">
                      {/* Show evaluation summary at top if available */}
                      {evaluationsData && evaluationsData.evaluations.length > 0 && (
                        <div className="mb-4 p-3 rounded-lg bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <Award className="h-4 w-4 text-yellow-600" />
                              <span className="text-sm font-medium">Judge Evaluation</span>
                            </div>
                            {(() => {
                              const finalEval = evaluationsData.evaluations.find(
                                (e) => e.scope === "final_result"
                              );
                              if (finalEval) {
                                return (
                                  <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
                                    Score: {finalEval.overall_score.toFixed(1)}/10
                                  </Badge>
                                );
                              }
                              return null;
                            })()}
                          </div>
                        </div>
                      )}

                      <ScrollArea className="h-[600px]">
                        <div className="prose prose-sm dark:prose-invert max-w-none">
                          <ReactMarkdown
                            components={{
                              h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-6 mb-4 text-primary" {...props} />,
                              h2: ({node, ...props}) => <h2 className="text-xl font-semibold mt-5 mb-3 text-primary" {...props} />,
                              h3: ({node, ...props}) => <h3 className="text-lg font-semibold mt-4 mb-2" {...props} />,
                              h4: ({node, ...props}) => <h4 className="text-base font-semibold mt-3 mb-2" {...props} />,
                              p: ({node, ...props}) => <p className="mb-3 leading-relaxed" {...props} />,
                              ul: ({node, ...props}) => <ul className="list-disc list-inside mb-3 space-y-1" {...props} />,
                              ol: ({node, ...props}) => <ol className="list-decimal list-inside mb-3 space-y-1" {...props} />,
                              li: ({node, ...props}) => <li className="ml-4" {...props} />,
                              blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-primary/50 pl-4 italic my-4 bg-muted/30 py-2" {...props} />,
                              code: ({node, inline, ...props}: any) =>
                                inline ? (
                                  <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono" {...props} />
                                ) : (
                                  <code className="block bg-muted p-4 rounded-lg my-3 overflow-x-auto font-mono text-sm" {...props} />
                                ),
                              table: ({node, ...props}) => (
                                <div className="overflow-x-auto my-4">
                                  <table className="min-w-full border-collapse border border-border" {...props} />
                                </div>
                              ),
                              th: ({node, ...props}) => <th className="border border-border bg-muted px-4 py-2 text-left font-semibold" {...props} />,
                              td: ({node, ...props}) => <td className="border border-border px-4 py-2" {...props} />,
                              hr: ({node, ...props}) => <hr className="my-6 border-t-2 border-border" {...props} />,
                              a: ({node, ...props}) => <a className="text-primary hover:underline" {...props} />,
                            }}
                          >
                            {currentExecution.result}
                          </ReactMarkdown>
                        </div>
                      </ScrollArea>
                    </TabsContent>
                  )}
                  {evaluationsData && evaluationsData.total > 0 && (
                    <TabsContent value="evaluation" className="mt-4">
                      <EvaluationPanel evaluations={evaluationsData.evaluations} />
                    </TabsContent>
                  )}
                </Tabs>
              </CardContent>
            </Card>
          )}

          {/* Current Execution - Result */}
          {currentExecution?.result && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />
                  Execution Result
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[600px]">
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown
                      components={{
                        h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-6 mb-4 text-primary" {...props} />,
                        h2: ({node, ...props}) => <h2 className="text-xl font-semibold mt-5 mb-3 text-primary" {...props} />,
                        h3: ({node, ...props}) => <h3 className="text-lg font-semibold mt-4 mb-2" {...props} />,
                        h4: ({node, ...props}) => <h4 className="text-base font-semibold mt-3 mb-2" {...props} />,
                        p: ({node, ...props}) => <p className="mb-3 leading-relaxed" {...props} />,
                        ul: ({node, ...props}) => <ul className="list-disc list-inside mb-3 space-y-1" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal list-inside mb-3 space-y-1" {...props} />,
                        li: ({node, ...props}) => <li className="ml-4" {...props} />,
                        blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-primary/50 pl-4 italic my-4 bg-muted/30 py-2" {...props} />,
                        code: ({node, inline, ...props}: any) =>
                          inline ? (
                            <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono" {...props} />
                          ) : (
                            <code className="block bg-muted p-4 rounded-lg my-3 overflow-x-auto font-mono text-sm" {...props} />
                          ),
                        table: ({node, ...props}) => (
                          <div className="overflow-x-auto my-4">
                            <table className="min-w-full border-collapse border border-border" {...props} />
                          </div>
                        ),
                        th: ({node, ...props}) => <th className="border border-border bg-muted px-4 py-2 text-left font-semibold" {...props} />,
                        td: ({node, ...props}) => <td className="border border-border px-4 py-2" {...props} />,
                        hr: ({node, ...props}) => <hr className="my-6 border-t-2 border-border" {...props} />,
                        a: ({node, ...props}) => <a className="text-primary hover:underline" {...props} />,
                      }}
                    >
                      {currentExecution.result}
                    </ReactMarkdown>
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Prompts Tab */}
        <TabsContent value="prompts">
          <Card>
            <CardHeader>
              <CardTitle>Saved Prompts</CardTitle>
              <CardDescription>
                Manage saved query prompts for this team
              </CardDescription>
            </CardHeader>
            <CardContent>
              {savedPrompts.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No saved prompts yet</p>
                  <p className="text-xs mt-1">Save prompts from the Execute tab to reuse them later</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {savedPrompts.map((prompt) => (
                    <div
                      key={prompt.id}
                      className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                      onClick={() => {
                        setQuery(prompt.query_text);
                        setActiveTab("execute");
                        toast.success("Prompt loaded");
                      }}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <p className="font-medium text-sm">{prompt.name}</p>
                          {prompt.description && (
                            <p className="text-xs text-muted-foreground mt-1">{prompt.description}</p>
                          )}
                          <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{prompt.query_text}</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm("Delete this prompt?")) {
                              deletePromptMutation.mutate(prompt.id);
                            }
                          }}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                      {prompt.category && (
                        <Badge variant="outline" className="mt-2 text-xs">{prompt.category}</Badge>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Execution History</CardTitle>
              <CardDescription>
                {sortedExecutions.length} {sortedExecutions.length === 1 ? "execution" : "executions"}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Filters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="Search executions..."
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="flex-1"
                  />
                </div>
                <Select value={statusFilter} onValueChange={(v) => {
                  setStatusFilter(v);
                  setCurrentPage(1);
                }}>
                  <SelectTrigger>
                    <SelectValue placeholder="Filter by status" />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-900">
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                    <SelectItem value="executing">Executing</SelectItem>
                    <SelectItem value="planning">Planning</SelectItem>
                    <SelectItem value="error">Error</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-900">
                    <SelectItem value="date_desc">Newest First</SelectItem>
                    <SelectItem value="date_asc">Oldest First</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Execution List */}
              {sortedExecutions.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <p>No executions found</p>
                </div>
              ) : (
                <>
                  <ScrollArea className="h-[500px]">
                    <div className="space-y-3">
                      {paginatedExecutions.map((execution: any) => (
                        <div
                          key={execution.id}
                          className="p-4 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                          onClick={() => {
                            // Open the focused details dialog (Output /
                            // Agent Steps / Messages tabs) instead of
                            // hijacking the Execute tab.
                            setHistoryDetail(execution as TeamExecution);
                          }}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                {execution.status === "running" && (
                                  <Loader2 className="w-4 h-4 text-blue-600 dark:text-blue-400 animate-spin" />
                                )}
                                <p className="font-medium text-sm truncate">{execution.query}</p>
                              </div>
                              <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                                <span className="flex items-center gap-1">
                                  <Calendar className="w-3 h-3" />
                                  {new Date(execution.started_at).toLocaleDateString()}
                                </span>
                                <span className="flex items-center gap-1">
                                  <Clock className="w-3 h-3" />
                                  {new Date(execution.started_at).toLocaleTimeString()}
                                </span>
                                {execution.status === "running" && (
                                  <span className="text-blue-600 dark:text-blue-400 font-medium animate-pulse">
                                    • Executing...
                                  </span>
                                )}
                                {execution.result && execution.status === "completed" && (
                                  <span className="text-green-600 dark:text-green-400">
                                    • Click to view result
                                  </span>
                                )}
                              </div>
                            </div>
                            <Badge className={teamStatusColors[execution.status] || teamStatusColors.idle}>
                              {execution.status}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between pt-4 border-t">
                      <p className="text-xs text-muted-foreground">
                        Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, sortedExecutions.length)} of {sortedExecutions.length}
                      </p>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                          disabled={currentPage === 1}
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </Button>
                        <span className="text-sm">
                          Page {currentPage} of {totalPages}
                        </span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                          disabled={currentPage === totalPages}
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Save Prompt Dialog */}
      <Dialog open={showSavePromptDialog} onOpenChange={setShowSavePromptDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Prompt</DialogTitle>
            <DialogDescription>
              Save this query for reuse later
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="prompt-name">Name</Label>
              <Input
                id="prompt-name"
                value={promptName}
                onChange={(e) => setPromptName(e.target.value)}
                placeholder="My research query"
              />
            </div>
            <div>
              <Label htmlFor="prompt-description">Description (optional)</Label>
              <Textarea
                id="prompt-description"
                value={promptDescription}
                onChange={(e) => setPromptDescription(e.target.value)}
                placeholder="What is this prompt for?"
                rows={2}
              />
            </div>
            <div>
              <Label htmlFor="prompt-category">Category (optional)</Label>
              <Input
                id="prompt-category"
                value={promptCategory}
                onChange={(e) => setPromptCategory(e.target.value)}
                placeholder="e.g., Research, Analysis"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSavePromptDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (!promptName.trim()) {
                  toast.error("Please enter a name");
                  return;
                }
                savePromptMutation.mutate({
                  team_id: teamId,
                  name: promptName,
                  description: promptDescription || undefined,
                  category: promptCategory || undefined,
                  query_text: query,
                });
              }}
              disabled={savePromptMutation.isPending}
            >
              {savePromptMutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Load Prompt Dialog */}
      <Dialog open={showLoadPromptDialog} onOpenChange={setShowLoadPromptDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Load Prompt</DialogTitle>
            <DialogDescription>
              Select a saved prompt to load
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[400px]">
            <div className="space-y-2">
              {savedPrompts.length === 0 ? (
                <p className="text-center py-8 text-muted-foreground">No saved prompts</p>
              ) : (
                savedPrompts.map((prompt) => (
                  <div
                    key={prompt.id}
                    className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                    onClick={() => {
                      setQuery(prompt.query_text);
                      setShowLoadPromptDialog(false);
                      toast.success("Prompt loaded");
                    }}
                  >
                    <p className="font-medium text-sm">{prompt.name}</p>
                    {prompt.description && (
                      <p className="text-xs text-muted-foreground mt-1">{prompt.description}</p>
                    )}
                    <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{prompt.query_text}</p>
                    {prompt.category && (
                      <Badge variant="outline" className="mt-2 text-xs">{prompt.category}</Badge>
                    )}
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLoadPromptDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Clarification popup — surfaces an agent's mid-run question and
          captures the user's reply, then resumes execution with that reply
          spliced into the questioner's next prompt. */}
      <Dialog
        open={!!clarification}
        onOpenChange={(open) => { if (!open) cancelClarification(); }}
      >
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <HelpCircle className="h-5 w-5 text-blue-500" />
              {clarification?.sender_name || "An agent"} needs your input
            </DialogTitle>
            <DialogDescription>
              Execution is paused. Provide an answer below and the team will
              continue from where it left off.
            </DialogDescription>
          </DialogHeader>
          {clarification && (
            <div className="space-y-3">
              <div className="rounded-md border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Badge variant="outline" className="text-[10px]">
                    {clarification.sender_role || "agent"}
                  </Badge>
                  <span className="text-xs font-medium">
                    {clarification.sender_name}
                  </span>
                </div>
                <p className="text-sm whitespace-pre-wrap leading-relaxed">
                  {clarification.question}
                </p>
              </div>
              <div>
                <label className="text-xs font-medium">Your answer</label>
                <textarea
                  className="mt-1 w-full min-h-[110px] rounded-md border border-gray-200 dark:border-gray-700 bg-background p-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  value={clarificationAnswer}
                  onChange={(e) => setClarificationAnswer(e.target.value)}
                  placeholder="Type your reply…"
                  autoFocus
                  onKeyDown={(e) => {
                    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                      e.preventDefault();
                      submitClarification();
                    }
                  }}
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  Tip: ⌘/Ctrl + Enter to submit.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={cancelClarification}
              disabled={clarificationSubmitting}
            >
              Cancel run
            </Button>
            <Button
              onClick={submitClarification}
              disabled={clarificationSubmitting || !clarificationAnswer.trim()}
            >
              {clarificationSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Resuming…
                </>
              ) : (
                "Submit & continue"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Execution details dialog (opened from the History tab). Three
          tabs: Output (final answer markdown), Agent Steps (per-agent
          step + tool-call timeline grouped by sender), Messages (full
          inter-agent message log via the existing MessageTimeline). */}
      <Dialog
        open={!!historyDetail}
        onOpenChange={(open) => { if (!open) setHistoryDetail(null); }}
      >
        <DialogContent className="max-w-5xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 pr-6">
              <Users className="h-5 w-5 text-blue-500" />
              <span className="truncate">
                {historyDetail?.query || "Execution"}
              </span>
            </DialogTitle>
            <DialogDescription className="flex items-center gap-2 text-xs">
              {historyDetail && (
                <>
                  <Badge className={teamStatusColors[historyDetail.status] || teamStatusColors.idle}>
                    {historyDetail.status}
                  </Badge>
                  {historyDetail.started_at && (
                    <span className="text-muted-foreground">
                      Started {new Date(historyDetail.started_at).toLocaleString()}
                    </span>
                  )}
                  {historyDetail.completed_at && (
                    <span className="text-muted-foreground">
                      • Finished {new Date(historyDetail.completed_at).toLocaleString()}
                    </span>
                  )}
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          {historyDetail && (
            <Tabs defaultValue="output" className="flex-1 min-h-0 flex flex-col">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="output">Output</TabsTrigger>
                <TabsTrigger value="agent_steps">
                  Agent Steps
                  {(() => {
                    const stepKinds = new Set(["task_assign", "task_result", "tool_call", "tool_result", "control"]);
                    const n = (historyDetail.messages || []).filter(
                      (m: any) => stepKinds.has(m.message_type)
                    ).length;
                    return n > 0 ? <Badge variant="outline" className="ml-2 text-[10px]">{n}</Badge> : null;
                  })()}
                </TabsTrigger>
                <TabsTrigger value="messages">
                  Messages
                  {historyDetail.messages?.length ? (
                    <Badge variant="outline" className="ml-2 text-[10px]">{historyDetail.messages.length}</Badge>
                  ) : null}
                </TabsTrigger>
              </TabsList>

              {/* Output tab */}
              <TabsContent value="output" className="flex-1 min-h-0 mt-3">
                <ScrollArea className="h-[60vh] pr-4">
                  {historyDetail.result ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                      <ReactMarkdown
                        components={{
                          h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-6 mb-4 text-primary" {...props} />,
                          h2: ({node, ...props}) => <h2 className="text-xl font-semibold mt-5 mb-3 text-primary" {...props} />,
                          h3: ({node, ...props}) => <h3 className="text-lg font-semibold mt-4 mb-2" {...props} />,
                          h4: ({node, ...props}) => <h4 className="text-base font-semibold mt-3 mb-2" {...props} />,
                          p: ({node, ...props}) => <p className="mb-3 leading-relaxed" {...props} />,
                          ul: ({node, ...props}) => <ul className="list-disc list-outside ml-5 mb-3 space-y-1" {...props} />,
                          ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-5 mb-3 space-y-1" {...props} />,
                          li: ({node, ...props}) => <li className="leading-relaxed" {...props} />,
                          code: ({node, className, children, ...props}: any) => {
                            const inline = !(className || "").includes("language-");
                            return inline
                              ? <code className="px-1 py-0.5 bg-gray-200 dark:bg-gray-800 rounded text-xs font-mono" {...props}>{children}</code>
                              : <code className={className} {...props}>{children}</code>;
                          },
                          pre: ({node, ...props}) => <pre className="bg-gray-100 dark:bg-gray-950 p-3 rounded text-xs overflow-x-auto" {...props} />,
                          blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-primary/50 pl-4 italic my-4 bg-muted/30 py-2" {...props} />,
                        }}
                      >
                        {historyDetail.result}
                      </ReactMarkdown>
                    </div>
                  ) : historyDetail.status === "failed" ? (
                    <div className="text-sm text-destructive">
                      Execution failed.
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      No final output captured for this execution.
                    </div>
                  )}
                </ScrollArea>
              </TabsContent>

              {/* Agent Steps tab — group execution events by acting agent */}
              <TabsContent value="agent_steps" className="flex-1 min-h-0 mt-3">
                <ScrollArea className="h-[60vh] pr-4">
                  <AgentStepsView execution={historyDetail} />
                </ScrollArea>
              </TabsContent>

              {/* Messages tab — full inter-agent timeline */}
              <TabsContent value="messages" className="flex-1 min-h-0 mt-3">
                <ScrollArea className="h-[60vh] pr-4">
                  <MessageTimeline messages={historyDetail.messages || []} />
                </ScrollArea>
              </TabsContent>
            </Tabs>
          )}
          <DialogFooter className="border-t pt-3">
            <Button variant="outline" onClick={() => setHistoryDetail(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AgentStepsView
//
// Used by the History details dialog. Groups the execution's `messages`
// stream by acting agent (sender name + role), and within each group
// surfaces the meaningful steps the agent took: control events (data
// sources loaded, tools/skills loaded, query execution started/completed),
// tool calls (with input arguments), and tool results (with output).
// task_assign rows are shown as the agent's prompt; task_result rows are
// shown as the agent's final output for that turn.
// ---------------------------------------------------------------------------

function AgentStepsView({ execution }: { execution: TeamExecution }) {
  const stepKinds = new Set([
    "task_assign",
    "task_result",
    "tool_call",
    "tool_result",
    "control",
  ]);
  const stepMessages = (execution.messages || []).filter((m: any) =>
    stepKinds.has(m.message_type),
  );

  if (stepMessages.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No agent steps were recorded for this execution.
      </div>
    );
  }

  // Group consecutive steps by acting agent. The "acting agent" for
  // task_assign is the recipient (whoever was assigned), for everything
  // else it's the sender. This keeps the prompt + the resulting work
  // inside the same agent's card.
  type Group = {
    agentId: string;
    agentName: string;
    role?: string;
    items: any[];
  };
  const groups: Group[] = [];
  for (const m of stepMessages as any[]) {
    const isAssign = m.message_type === "task_assign";
    const actingId = isAssign ? m.to_agent_id : m.from_agent_id;
    const actingName = isAssign ? m.to_agent_name : m.from_agent_name;
    const meta = (() => {
      const v = m.metadata;
      if (!v) return {};
      if (typeof v === "string") {
        try { return JSON.parse(v) || {}; } catch { return {}; }
      }
      return v;
    })();
    const role = meta.role;
    const last = groups[groups.length - 1];
    if (last && last.agentId === actingId) {
      last.items.push({ ...m, _parsedMeta: meta });
    } else {
      groups.push({
        agentId: actingId || "system",
        agentName: actingName || "System",
        role,
        items: [{ ...m, _parsedMeta: meta }],
      });
    }
  }

  return (
    <div className="space-y-4">
      {groups.map((g, gi) => (
        <Card key={`${g.agentId}-${gi}`} className="overflow-hidden">
          <CardHeader className="pb-2 bg-muted/30">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-blue-600 dark:text-blue-400" />
              <span className="font-semibold text-sm">{g.agentName}</span>
              {g.role && (
                <Badge variant="outline" className="text-[10px]">
                  {g.role}
                </Badge>
              )}
              <Badge variant="outline" className="ml-auto text-[10px]">
                {g.items.length} step{g.items.length === 1 ? "" : "s"}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-3 space-y-2">
            {g.items.map((it: any, i: number) => (
              <AgentStepRow key={it.id || i} step={it} />
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function AgentStepRow({ step }: { step: any }) {
  const kind: string = step.message_type;
  const meta = step._parsedMeta || {};
  const ts = step.timestamp || step.created;

  if (kind === "task_assign") {
    return (
      <div className="rounded border border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/30 p-3">
        <div className="flex items-center gap-2 mb-1">
          <Send className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />
          <span className="text-xs font-semibold text-purple-700 dark:text-purple-300">Prompt</span>
          {ts && <span className="text-[10px] text-muted-foreground ml-auto">{new Date(ts).toLocaleTimeString()}</span>}
        </div>
        <pre className="text-xs whitespace-pre-wrap leading-relaxed font-sans text-gray-800 dark:text-gray-200 line-clamp-6">
          {step.content}
        </pre>
      </div>
    );
  }

  if (kind === "task_result") {
    return (
      <div className="rounded border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/30 p-3">
        <div className="flex items-center gap-2 mb-1">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
          <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">Response</span>
          {meta.is_clarification && (
            <Badge variant="outline" className="text-[10px] text-amber-700 border-amber-300 bg-amber-50 dark:bg-amber-950 dark:text-amber-200 dark:border-amber-800">
              Clarification
            </Badge>
          )}
          {ts && <span className="text-[10px] text-muted-foreground ml-auto">{new Date(ts).toLocaleTimeString()}</span>}
        </div>
        <div className="text-xs whitespace-pre-wrap leading-relaxed text-gray-800 dark:text-gray-200 max-h-48 overflow-y-auto">
          {step.content}
        </div>
      </div>
    );
  }

  if (kind === "tool_call") {
    const args = meta.tool_input;
    return (
      <div className="rounded border border-purple-300 dark:border-purple-700 bg-purple-100/40 dark:bg-purple-950/40 p-3">
        <div className="flex items-center gap-2 mb-1">
          <Wrench className="h-3.5 w-3.5 text-purple-700 dark:text-purple-300" />
          <span className="text-xs font-semibold text-purple-700 dark:text-purple-300">Tool call</span>
          <code className="text-xs font-mono px-1.5 py-0.5 rounded bg-white/60 dark:bg-gray-900/60">
            {meta.tool_name || "unknown"}
          </code>
          {ts && <span className="text-[10px] text-muted-foreground ml-auto">{new Date(ts).toLocaleTimeString()}</span>}
        </div>
        {args && (
          <pre className="text-[11px] bg-white dark:bg-gray-900 p-2 rounded border overflow-x-auto">
            {typeof args === "string" ? args : JSON.stringify(args, null, 2)}
          </pre>
        )}
      </div>
    );
  }

  if (kind === "tool_result") {
    const out = meta.tool_output;
    return (
      <div className="rounded border border-emerald-300 dark:border-emerald-700 bg-emerald-100/40 dark:bg-emerald-950/40 p-3">
        <div className="flex items-center gap-2 mb-1">
          <Wrench className="h-3.5 w-3.5 text-emerald-700 dark:text-emerald-300" />
          <span className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">Tool result</span>
          <code className="text-xs font-mono px-1.5 py-0.5 rounded bg-white/60 dark:bg-gray-900/60">
            {meta.tool_name || "unknown"}
          </code>
          {ts && <span className="text-[10px] text-muted-foreground ml-auto">{new Date(ts).toLocaleTimeString()}</span>}
        </div>
        {out !== undefined && out !== null && (
          <pre className="text-[11px] bg-white dark:bg-gray-900 p-2 rounded border overflow-x-auto max-h-32">
            {typeof out === "string" ? out : JSON.stringify(out, null, 2)}
          </pre>
        )}
      </div>
    );
  }

  // control + anything else
  return (
    <div className="rounded border border-gray-200 dark:border-gray-700 bg-gray-50/60 dark:bg-gray-900/40 p-2">
      <div className="flex items-center gap-2">
        <AlertCircle className="h-3.5 w-3.5 text-gray-500" />
        <span className="text-xs text-gray-700 dark:text-gray-300 flex-1 whitespace-pre-wrap">
          {step.content}
        </span>
        {ts && <span className="text-[10px] text-muted-foreground">{new Date(ts).toLocaleTimeString()}</span>}
      </div>
    </div>
  );
}
