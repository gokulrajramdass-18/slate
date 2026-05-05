/**
 * Standalone Agent Execution Page
 *
 * Shows current execution with streaming and execution history
 */

"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { queryKeys } from "@/lib/query-client";
import * as standaloneAgentsApi from "@/lib/api/standalone-agents";
import type { StandaloneAgent, StandaloneAgentExecutionStep } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Play,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Clock,
  Bot,
  History,
  FileText,
  Plus,
  Save,
  Trash2,
  Library,
  Search,
  ChevronLeft,
  ChevronRight,
  Calendar,
  XCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github-dark.css";

export default function StandaloneAgentExecutePage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const agentId = params.id as string;

  const [query, setQuery] = useState("");
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentExecutionId, setCurrentExecutionId] = useState<string | null>(null);
  const [steps, setSteps] = useState<StandaloneAgentExecutionStep[]>([]);
  const [result, setResult] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [stepsCollapsed, setStepsCollapsed] = useState(false);

  // History execution detail state
  const [expandedExecutionId, setExpandedExecutionId] = useState<string | null>(null);

  // Prompt management state
  const [showSavePromptDialog, setShowSavePromptDialog] = useState(false);
  const [showLoadPromptDialog, setShowLoadPromptDialog] = useState(false);
  const [promptName, setPromptName] = useState("");
  const [promptDescription, setPromptDescription] = useState("");
  const [selectedPromptId, setSelectedPromptId] = useState<string>("");

  // History filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"date_desc" | "date_asc">("date_desc");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Queries
  const { data: agent, isLoading: agentLoading } = useQuery({
    queryKey: queryKeys.standaloneAgent(agentId),
    queryFn: () => standaloneAgentsApi.getStandaloneAgent(agentId),
  });

  const { data: executionsData, refetch: refetchExecutions } = useQuery({
    queryKey: queryKeys.standaloneAgentExecutions(agentId),
    queryFn: () => standaloneAgentsApi.listStandaloneAgentExecutions(agentId),
  });

  // Cleanup abandoned executions on mount
  const cleanupMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch("http://localhost:5055/api/standalone-agents/executions/cleanup?timeout_minutes=10", {
        method: "POST",
      });
      if (!response.ok) throw new Error("Failed to cleanup");
      return response.json();
    },
    onSuccess: () => {
      refetchExecutions();
    },
  });

  // Run cleanup when component mounts to mark abandoned executions
  useEffect(() => {
    cleanupMutation.mutate();
  }, []);

  // Query prompts (user saved prompts)
  const { data: promptsData } = useQuery({
    queryKey: ["user-query-prompts"],
    queryFn: async () => {
      const response = await fetch("http://localhost:5055/api/user-query-prompts");
      if (!response.ok) throw new Error("Failed to fetch prompts");
      return response.json();
    },
  });

  // Mutations for prompt management
  const createPromptMutation = useMutation({
    mutationFn: async (data: { name: string; query_text: string; description?: string; category?: string }) => {
      const response = await fetch("http://localhost:5055/api/user-query-prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error("Failed to create prompt");
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-query-prompts"] });
      toast.success("Prompt saved successfully");
      setShowSavePromptDialog(false);
      setPromptName("");
      setPromptDescription("");
    },
    onError: () => {
      toast.error("Failed to save prompt");
    },
  });

  const deletePromptMutation = useMutation({
    mutationFn: async (promptId: string) => {
      const response = await fetch(`http://localhost:5055/api/user-query-prompts/${promptId}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Failed to delete prompt");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-query-prompts"] });
      toast.success("Prompt deleted successfully");
    },
    onError: () => {
      toast.error("Failed to delete prompt");
    },
  });

  const cancelExecutionMutation = useMutation({
    mutationFn: async (executionId: string) => {
      return standaloneAgentsApi.cancelStandaloneAgentExecution(executionId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.standaloneAgentExecutions(agentId),
      });
      toast.success("Execution cancelled successfully");
    },
    onError: () => {
      toast.error("Failed to cancel execution");
    },
  });

  const handleExecute = async () => {
    if (!query.trim()) {
      toast.error("Please enter a query");
      return;
    }

    setIsExecuting(true);
    setCurrentExecutionId(null);
    setSteps([]);
    setResult("");
    setError(null);

    try {
      await standaloneAgentsApi.executeStandaloneAgentStream(
        agentId,
        {
          query: query.trim(),
          stream: true,
          max_steps: 10,
        },
        (event) => {
          switch (event.type) {
            case "metadata":
              setCurrentExecutionId(event.data.execution_id);
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

            case "tool_call":
              // Add tool call as a step
              setSteps((prev) => [
                ...prev,
                {
                  step_number: prev.length + 1,
                  action: `Calling tool: ${event.data.tool}`,
                  status: "running",
                  tool_name: event.data.tool,
                  result: `Arguments: ${JSON.stringify(event.data.arguments, null, 2)}`,
                },
              ]);
              break;

            case "tool_result":
              // Update the last tool call step with result
              setSteps((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;
                if (lastIndex >= 0 && updated[lastIndex].tool_name === event.data.tool) {
                  updated[lastIndex] = {
                    ...updated[lastIndex],
                    status: "completed",
                    result: event.data.result,
                  };
                }
                return updated;
              });
              break;

            case "done":
              setIsExecuting(false);
              refetchExecutions();
              toast.success("Execution completed");
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

  const handleSavePrompt = () => {
    if (!promptName.trim() || !query.trim()) {
      toast.error("Please enter prompt name and query");
      return;
    }

    createPromptMutation.mutate({
      name: promptName,
      query_text: query,
      description: promptDescription,
      category: agent?.role || "general",
    });
  };

  const handleSelectPrompt = (promptId: string) => {
    const prompt = promptsData?.find((p: any) => p.id === promptId);
    if (prompt) {
      setQuery(prompt.query_text);
      setSelectedPromptId(promptId);
      setShowLoadPromptDialog(false);
      toast.success("Prompt loaded");
    }
  };

  const handleDeletePrompt = (promptId: string) => {
    if (confirm("Are you sure you want to delete this prompt?")) {
      deletePromptMutation.mutate(promptId);
      if (selectedPromptId === promptId) {
        setSelectedPromptId("");
      }
    }
  };

  const handleCancelExecution = (executionId: string) => {
    if (confirm("Are you sure you want to cancel this execution?")) {
      cancelExecutionMutation.mutate(executionId);
    }
  };

  const toggleExecutionExpanded = (executionId: string) => {
    setExpandedExecutionId(prev => prev === executionId ? null : executionId);
  };

  const getElapsedTime = (startedAt: string) => {
    const start = new Date(startedAt).getTime();
    const now = Date.now();
    const diff = now - start;
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  };

  const executions = executionsData?.executions || [];

  // Filter and sort executions
  const filteredExecutions = executions.filter((exec: any) => {
    const matchesSearch = exec.query?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || exec.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const sortedExecutions = [...filteredExecutions].sort((a: any, b: any) => {
    const dateA = new Date(a.created).getTime();
    const dateB = new Date(b.created).getTime();
    return sortBy === "date_desc" ? dateB - dateA : dateA - dateB;
  });

  const totalPages = Math.ceil(sortedExecutions.length / itemsPerPage);
  const paginatedExecutions = sortedExecutions.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  if (agentLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex flex-col items-center justify-center h-96 space-y-4">
        <AlertCircle className="w-12 h-12 text-destructive" />
        <p className="text-lg font-medium">Agent not found</p>
        <Button onClick={() => router.back()}>Go Back</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <Bot className="w-5 h-5 text-primary" />
              <h1 className="text-2xl font-semibold">{agent.name}</h1>
              <Badge variant="outline">Standalone Agent</Badge>
            </div>
            {agent.description && (
              <p className="text-sm text-muted-foreground mt-1">{agent.description}</p>
            )}
          </div>
        </div>
      </div>

      <Tabs defaultValue="execute" className="space-y-4">
        <TabsList>
          <TabsTrigger value="execute">
            <Play className="w-4 h-4 mr-2" />
            Execute
          </TabsTrigger>
          <TabsTrigger value="prompts">
            <FileText className="w-4 h-4 mr-2" />
            Prompts
          </TabsTrigger>
          <TabsTrigger value="history">
            <History className="w-4 h-4 mr-2" />
            History ({executions.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="execute" className="space-y-4">
          {/* Query Input */}
          <Card>
            <CardHeader>
              <CardTitle>Execute Query</CardTitle>
              <CardDescription>
                Run a query with this standalone agent
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter your query for the agent..."
                rows={4}
                disabled={isExecuting}
              />

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
                <Button
                  variant="outline"
                  onClick={() => setShowLoadPromptDialog(true)}
                  disabled={isExecuting}
                >
                  <Library className="w-4 h-4 mr-2" />
                  Load Prompt
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowSavePromptDialog(true)}
                  disabled={!query.trim() || isExecuting}
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save Prompt
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Execution Steps */}
          {steps.length > 0 && (
            <Card>
              <CardHeader className="cursor-pointer" onClick={() => setStepsCollapsed(!stepsCollapsed)}>
                <div className="flex items-center justify-between">
                  <CardTitle>Execution Steps</CardTitle>
                  <Button variant="ghost" size="sm">
                    {stepsCollapsed ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronUp className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </CardHeader>
              {!stepsCollapsed && (
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
              )}
            </Card>
          )}

          {/* Result */}
          {result && (
            <Card>
              <CardHeader>
                <CardTitle>Result</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="prose prose-sm max-w-none dark:prose-invert">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeHighlight]}
                    components={{
                      pre: ({ children, ...props }: any) => (
                        <pre
                          className="overflow-x-auto max-w-full bg-gray-900 text-gray-100 p-4 rounded-lg my-4"
                          {...props}
                        >
                          {children}
                        </pre>
                      ),
                      code: ({ inline, children, ...props }: any) =>
                        inline ? (
                          <code
                            className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm"
                            {...props}
                          >
                            {children}
                          </code>
                        ) : (
                          <code {...props}>{children}</code>
                        ),
                      a: ({ children, ...props }: any) => (
                        <a
                          className="text-blue-600 hover:text-blue-800 underline"
                          target="_blank"
                          rel="noopener noreferrer"
                          {...props}
                        >
                          {children}
                        </a>
                      ),
                      ul: ({ children, ...props }: any) => (
                        <ul className="list-disc pl-6 my-4 space-y-2" {...props}>
                          {children}
                        </ul>
                      ),
                      ol: ({ children, ...props }: any) => (
                        <ol className="list-decimal pl-6 my-4 space-y-2" {...props}>
                          {children}
                        </ol>
                      ),
                      blockquote: ({ children, ...props }: any) => (
                        <blockquote
                          className="border-l-4 border-gray-300 dark:border-gray-700 pl-4 italic my-4"
                          {...props}
                        >
                          {children}
                        </blockquote>
                      ),
                      h1: ({ children, ...props }: any) => (
                        <h1 className="text-2xl font-bold mt-6 mb-4" {...props}>
                          {children}
                        </h1>
                      ),
                      h2: ({ children, ...props }: any) => (
                        <h2 className="text-xl font-bold mt-5 mb-3" {...props}>
                          {children}
                        </h2>
                      ),
                      h3: ({ children, ...props }: any) => (
                        <h3 className="text-lg font-semibold mt-4 mb-2" {...props}>
                          {children}
                        </h3>
                      ),
                      table: ({ children, ...props }: any) => (
                        <div className="overflow-x-auto my-4">
                          <table
                            className="min-w-full divide-y divide-gray-200 dark:divide-gray-700"
                            {...props}
                          >
                            {children}
                          </table>
                        </div>
                      ),
                      th: ({ children, ...props }: any) => (
                        <th
                          className="px-4 py-2 bg-gray-100 dark:bg-gray-800 font-semibold text-left"
                          {...props}
                        >
                          {children}
                        </th>
                      ),
                      td: ({ children, ...props }: any) => (
                        <td className="px-4 py-2 border-t border-gray-200 dark:border-gray-700" {...props}>
                          {children}
                        </td>
                      ),
                    }}
                  >
                    {result}
                  </ReactMarkdown>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error */}
          {error && (
            <Card className="border-red-200 dark:border-red-900">
              <CardHeader>
                <CardTitle className="text-red-600 dark:text-red-400">
                  Execution Error
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </CardContent>
            </Card>
          )}

          {/* Agent Info */}
          {!isExecuting && !currentExecutionId && (
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
        </TabsContent>

        <TabsContent value="prompts" className="space-y-4">
          {/* Saved Prompts Selector */}
          <Card>
            <CardHeader>
              <CardTitle>Saved Prompts</CardTitle>
              <CardDescription>
                Select from your saved prompt library or save the current query
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Prompt Selector */}
              <div className="space-y-2">
                <Label>Select Prompt Template</Label>
                <Select value={selectedPromptId} onValueChange={handleSelectPrompt}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a saved prompt..." />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                    {promptsData && promptsData.length > 0 ? (
                      promptsData.map((prompt: any) => (
                        <SelectItem key={prompt.id} value={prompt.id}>
                          <div className="flex items-center gap-2">
                            <span>{prompt.name}</span>
                            {prompt.category && (
                              <Badge variant="outline" className="text-xs">
                                {prompt.category}
                              </Badge>
                            )}
                          </div>
                        </SelectItem>
                      ))
                    ) : (
                      <SelectItem value="none" disabled>
                        No saved prompts
                      </SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Selected Prompt Preview */}
              {selectedPromptId && promptsData?.find((p: any) => p.id === selectedPromptId) && (
                <div className="p-3 bg-muted rounded-lg space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium">
                      {promptsData.find((p: any) => p.id === selectedPromptId)?.name}
                    </Label>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeletePrompt(selectedPromptId)}
                    >
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                  {promptsData.find((p: any) => p.id === selectedPromptId)?.description && (
                    <p className="text-xs text-muted-foreground">
                      {promptsData.find((p: any) => p.id === selectedPromptId)?.description}
                    </p>
                  )}
                  <pre className="text-sm whitespace-pre-wrap">
                    {promptsData.find((p: any) => p.id === selectedPromptId)?.query_text}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Agent Configuration */}
          <Card>
            <CardHeader>
              <CardTitle>Agent Configuration</CardTitle>
              <CardDescription>
                System prompt and configuration for this standalone agent
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Role */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">Role</Label>
                <Badge variant="outline" className="text-sm">
                  {agent.role}
                </Badge>
              </div>

              {/* System Prompt */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">System Prompt</Label>
                <div className="p-3 bg-muted rounded-lg">
                  <pre className="text-sm whitespace-pre-wrap font-mono">
                    {agent.system_prompt || `You are a helpful ${agent.role} assistant.`}
                  </pre>
                </div>
              </div>

              {/* Model Override */}
              {agent.model_name && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium">Model Override</Label>
                  <Badge variant="secondary">{agent.model_name}</Badge>
                </div>
              )}

              {/* Tools Configuration */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">
                  Tools ({agent.tool_ids?.length || 0})
                </Label>
                {agent.tool_ids && agent.tool_ids.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {agent.tool_ids.map((toolId) => (
                      <Badge key={toolId} variant="outline" className="text-xs">
                        {toolId}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No tools configured</p>
                )}
              </div>

              {/* Data Sources Configuration */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">
                  Data Sources ({agent.data_source_ids?.length || 0})
                </Label>
                {agent.data_source_ids && agent.data_source_ids.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {agent.data_source_ids.map((sourceId) => (
                      <Badge key={sourceId} variant="outline" className="text-xs">
                        {sourceId}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No data sources configured</p>
                )}
              </div>

              {/* MCP Servers Configuration */}
              <div className="space-y-2">
                <Label className="text-sm font-medium">
                  MCP Servers ({agent.mcp_server_ids?.length || 0})
                </Label>
                {agent.mcp_server_ids && agent.mcp_server_ids.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {agent.mcp_server_ids.map((serverId) => (
                      <Badge key={serverId} variant="outline" className="text-xs">
                        {serverId}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No MCP servers configured</p>
                )}
              </div>

              {/* Additional Config */}
              {agent.config && Object.keys(agent.config).length > 0 && (
                <div className="space-y-2">
                  <Label className="text-sm font-medium">Additional Configuration</Label>
                  <div className="p-3 bg-muted rounded-lg">
                    <pre className="text-xs whitespace-pre-wrap font-mono">
                      {JSON.stringify(agent.config, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Example Prompts */}
          <Card>
            <CardHeader>
              <CardTitle>Example Prompts</CardTitle>
              <CardDescription>
                Sample queries you can try with this agent
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {agent.role === "analyst" && (
                  <>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">Analyze the data and provide insights</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Get comprehensive analysis of available data sources
                      </p>
                    </div>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">Create a SWOT analysis</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Generate strengths, weaknesses, opportunities, and threats
                      </p>
                    </div>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">What are the key trends?</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Identify patterns and trends in the data
                      </p>
                    </div>
                  </>
                )}

                {agent.role === "researcher" && (
                  <>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">Research and summarize the topic</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Get detailed research summary
                      </p>
                    </div>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">Find relevant information about...</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Search and extract specific information
                      </p>
                    </div>
                  </>
                )}

                {agent.role === "planner" && (
                  <>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">Create an action plan</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Generate step-by-step plan
                      </p>
                    </div>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">What are the next steps?</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Identify recommended actions
                      </p>
                    </div>
                  </>
                )}

                {/* Generic examples for custom role */}
                {agent.role === "custom" && (
                  <>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">Help me with...</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        General assistance query
                      </p>
                    </div>
                    <div className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors">
                      <p className="text-sm font-medium">Analyze and explain...</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Request analysis and explanation
                      </p>
                    </div>
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4">
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
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="timeout">Timeout</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
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
                <div className="text-center py-16 space-y-4">
                  <History className="w-12 h-12 mx-auto text-muted-foreground" />
                  <div className="space-y-1">
                    <p className="font-medium text-lg">No executions found</p>
                    <p className="text-sm text-muted-foreground">
                      {searchQuery || statusFilter !== "all"
                        ? "Try adjusting your filters"
                        : "Execute queries to see them here"}
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <div className="space-y-3">
                    {paginatedExecutions.map((execution) => {
                      const isExpanded = expandedExecutionId === execution.id;
                      const canExpand = execution.status === "completed" || execution.status === "failed";

                      return (
                        <Card
                          key={execution.id}
                          className={`transition-colors ${
                            execution.status === "completed"
                              ? "border-green-200 dark:border-green-900 hover:bg-green-50 dark:hover:bg-green-950/20"
                              : execution.status === "failed"
                              ? "border-red-200 dark:border-red-900 hover:bg-red-50 dark:hover:bg-red-950/20"
                              : execution.status === "cancelled"
                              ? "border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-950/20"
                              : "border-orange-200 dark:border-orange-900 hover:bg-orange-50 dark:hover:bg-orange-950/20"
                          } ${canExpand ? "cursor-pointer" : ""}`}
                          onClick={() => canExpand && toggleExecutionExpanded(execution.id)}
                        >
                          <CardHeader className="pb-3">
                            <div className="flex items-start justify-between">
                              <div className="space-y-1 flex-1">
                                <div className="flex items-center gap-2">
                                  <CardTitle className="text-base">{execution.query}</CardTitle>
                                  <Badge variant="outline" className="text-xs">
                                    Standalone Agent
                                  </Badge>
                                </div>
                                <CardDescription className="text-xs flex items-center gap-3">
                                  <span className="flex items-center gap-1">
                                    <Calendar className="w-3 h-3" />
                                    {new Date(execution.created).toLocaleDateString()}
                                  </span>
                                  <span className="flex items-center gap-1">
                                    <Clock className="w-3 h-3" />
                                    {new Date(execution.created).toLocaleTimeString()}
                                  </span>
                                  {execution.status === "running" && (
                                    <span className="text-orange-600 dark:text-orange-400 font-medium">
                                      • Running for {getElapsedTime(execution.created)}
                                    </span>
                                  )}
                                  {execution.duration_ms && execution.status !== "running" && (
                                    <span>• {execution.duration_ms}ms</span>
                                  )}
                                </CardDescription>
                              </div>
                              <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                                <Badge
                                  variant={
                                    execution.status === "completed"
                                      ? "default"
                                      : execution.status === "failed"
                                      ? "destructive"
                                      : execution.status === "cancelled"
                                      ? "outline"
                                      : "secondary"
                                  }
                                  className={
                                    execution.status === "completed"
                                      ? "bg-green-600 dark:bg-green-700 hover:bg-green-700 dark:hover:bg-green-800"
                                      : ""
                                  }
                                >
                                  {execution.status}
                                </Badge>
                                {execution.status === "running" && (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleCancelExecution(execution.id)}
                                    disabled={cancelExecutionMutation.isPending}
                                  >
                                    <XCircle className="w-3 h-3 mr-1" />
                                    Cancel
                                  </Button>
                                )}
                                {canExpand && (
                                  <Button variant="ghost" size="sm">
                                    {isExpanded ? (
                                      <ChevronUp className="h-4 w-4" />
                                    ) : (
                                      <ChevronDown className="h-4 w-4" />
                                    )}
                                  </Button>
                                )}
                              </div>
                            </div>
                          </CardHeader>
                          {isExpanded && execution.result && (
                            <CardContent>
                              <div className="space-y-2">
                                <Label className="text-sm font-medium">Result</Label>
                                <div className="prose prose-sm max-w-none dark:prose-invert">
                                  <ReactMarkdown
                                    remarkPlugins={[remarkGfm]}
                                    rehypePlugins={[rehypeHighlight]}
                                    components={{
                                      pre: ({ children, ...props }: any) => (
                                        <pre
                                          className="overflow-x-auto max-w-full bg-gray-900 text-gray-100 p-4 rounded-lg my-4"
                                          {...props}
                                        >
                                          {children}
                                        </pre>
                                      ),
                                      code: ({ inline, children, ...props }: any) =>
                                        inline ? (
                                          <code
                                            className="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm"
                                            {...props}
                                          >
                                            {children}
                                          </code>
                                        ) : (
                                          <code {...props}>{children}</code>
                                        ),
                                    }}
                                  >
                                    {typeof execution.result === "string"
                                      ? execution.result
                                      : (execution.result as any)?.response
                                      ? (execution.result as any).response
                                      : JSON.stringify(execution.result, null, 2)}
                                  </ReactMarkdown>
                                </div>
                              </div>
                            </CardContent>
                          )}
                          {isExpanded && execution.error && (
                            <CardContent>
                              <div className="space-y-2">
                                <Label className="text-sm font-medium text-red-600 dark:text-red-400">Error</Label>
                                <div className="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 p-3 rounded">
                                  {execution.error}
                                </div>
                              </div>
                            </CardContent>
                          )}
                        </Card>
                      );
                    })}
                  </div>

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

      {/* Load Prompt Dialog */}
      <Dialog open={showLoadPromptDialog} onOpenChange={setShowLoadPromptDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Load Saved Prompt</DialogTitle>
          </DialogHeader>

          <div className="space-y-3 max-h-96 overflow-y-auto">
            {promptsData && promptsData.length > 0 ? (
              promptsData.map((prompt: any) => (
                <div
                  key={prompt.id}
                  className="p-4 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
                  onClick={() => handleSelectPrompt(prompt.id)}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium">{prompt.name}</h4>
                        {prompt.category && (
                          <Badge variant="outline" className="text-xs">
                            {prompt.category}
                          </Badge>
                        )}
                      </div>
                      {prompt.description && (
                        <p className="text-sm text-muted-foreground">{prompt.description}</p>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeletePrompt(prompt.id);
                      }}
                    >
                      <Trash2 className="w-4 h-4 text-destructive" />
                    </Button>
                  </div>
                  <div className="mt-2 p-2 bg-muted rounded text-sm">
                    <pre className="whitespace-pre-wrap text-xs">{prompt.query_text}</pre>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <Library className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No saved prompts yet</p>
                <p className="text-sm mt-1">Save your first prompt to see it here</p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowLoadPromptDialog(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Save Prompt Dialog */}
      <Dialog open={showSavePromptDialog} onOpenChange={setShowSavePromptDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save Prompt</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="prompt-name">Prompt Name *</Label>
              <Input
                id="prompt-name"
                value={promptName}
                onChange={(e) => setPromptName(e.target.value)}
                placeholder="e.g., SWOT Analysis Query"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="prompt-description">Description (Optional)</Label>
              <Textarea
                id="prompt-description"
                value={promptDescription}
                onChange={(e) => setPromptDescription(e.target.value)}
                placeholder="Brief description of what this prompt does..."
                rows={2}
              />
            </div>

            <div className="space-y-2">
              <Label>Query to Save</Label>
              <div className="p-3 bg-muted rounded-lg">
                <pre className="text-sm whitespace-pre-wrap">{query}</pre>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowSavePromptDialog(false);
                setPromptName("");
                setPromptDescription("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSavePrompt}
              disabled={createPromptMutation.isPending}
            >
              {createPromptMutation.isPending && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              Save Prompt
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
