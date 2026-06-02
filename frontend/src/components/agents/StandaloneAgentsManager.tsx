/**
 * Standalone Agents Manager Component
 *
 * Manages individual agents with their own tools, MCP servers, and data sources
 */

"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-client";
import * as standaloneAgentsApi from "@/lib/api/standalone-agents";
import { toolsApi } from "@/lib/api/tools";
import { sourcesApi } from "@/lib/api/sources";
import { mcpServersApi } from "@/lib/api/mcp-servers";
import { promptsApi } from "@/lib/api/agent-prompts";
import { agentSkillsApi, type Skill } from "@/lib/api/agent-skills";
import { evaluationApi, type EvaluationSummary } from "@/lib/api/evaluations";
import type { StandaloneAgent, StandaloneAgentCreate, AgentRole } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { AgentModelSelector } from "@/components/agents/AgentModelSelector";
import { ResourceSelectionSection } from "@/components/agents/ResourceSelectionSection";
import { MemoryConfigSection } from "@/components/agents/MemoryConfigSection";
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
import { Bot, Plus, Trash2, Loader2, Activity, Brain, Search as SearchIcon, FileText, Zap, Pencil, Users, Database, Play, CheckCircle2, AlertCircle, BarChart3, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "@/lib/routing/navigation";

const ROLE_CONFIG: Record<string, { label: string; color: string; icon: typeof Bot }> = {
  planner: { label: "Planner", color: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200", icon: Brain },
  researcher: { label: "Researcher", color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200", icon: SearchIcon },
  analyst: { label: "Analyst", color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200", icon: Activity },
  synthesizer: { label: "Synthesizer", color: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200", icon: FileText },
  custom: { label: "Custom", color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200", icon: Bot },
};

const AVAILABLE_ROLES: { value: AgentRole | "custom"; label: string }[] = [
  { value: "planner", label: "Planner" },
  { value: "researcher", label: "Researcher" },
  { value: "analyst", label: "Analyst" },
  { value: "data_scientist", label: "Data Scientist" },
  { value: "developer", label: "Developer" },
  { value: "writer", label: "Writer" },
  { value: "tester", label: "Tester" },
  { value: "designer", label: "Designer" },
  { value: "reviewer", label: "Reviewer" },
  { value: "coordinator", label: "Coordinator" },
  { value: "custom", label: "Custom" },
];

export function StandaloneAgentsManager() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [deleteDialogAgent, setDeleteDialogAgent] = useState<string | null>(null);
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Agentic memory configuration. Persisted under config.memory and
  // round-tripped via the agent create/update payload.
  const DEFAULT_MEMORY_CONFIG = {
    short_term_enabled: true,
    episodic_enabled: true,
    episodic_retention_days: 90,
    episodic_max_entries: 500,
    semantic_enabled: true,
    semantic_max_facts: 200,
    procedural_enabled: false,
    procedural_min_attempts: 3,
    procedural_min_success_rate: 0.6,
  };

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    role: "planner" as AgentRole | "custom",
    custom_role_name: "",
    system_prompt: "",
    model_name: "",
    tool_ids: [] as string[],
    mcp_server_ids: [] as string[],
    data_source_ids: [] as string[],
    skill_ids: [] as string[],
    memory: { ...DEFAULT_MEMORY_CONFIG },
  });
  // Tracks whether the user has manually edited the system prompt;
  // we only auto-fill from the role template while it is still untouched.
  const [systemPromptDirty, setSystemPromptDirty] = useState(false);

  // Queries
  const { data: agentsData, isLoading } = useQuery({
    queryKey: queryKeys.standaloneAgents,
    queryFn: () => standaloneAgentsApi.listStandaloneAgents(),
  });

  const { data: toolsData } = useQuery({
    queryKey: queryKeys.tools,
    queryFn: () => toolsApi.list(),
  });

  const { data: sourcesData } = useQuery({
    queryKey: queryKeys.sources,
    queryFn: () => sourcesApi.list(),
  });

  const { data: mcpServersData } = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: () => mcpServersApi.list(),
  });

  const { data: skillsData, isLoading: skillsLoading, error: skillsError } = useQuery({
    queryKey: ["agent-skills"],
    queryFn: () => agentSkillsApi.listSkills(),
  });

  const agents = agentsData?.agents || [];
  const tools = toolsData || [];
  const sources = sourcesData || [];
  const mcpServers = mcpServersData || [];
  const skills = Array.isArray(skillsData) ? skillsData : [];

  // Filter agents based on search query
  const filteredAgents = agents.filter((agent) => {
    if (!searchQuery.trim()) return true;

    const query = searchQuery.toLowerCase();
    return (
      agent.name.toLowerCase().includes(query) ||
      agent.description?.toLowerCase().includes(query) ||
      agent.role.toLowerCase().includes(query) ||
      agent.model_name?.toLowerCase().includes(query)
    );
  });

  // Get execution counts for all agents
  const agentExecutionCounts = useQuery({
    queryKey: ["standalone-agents-execution-counts", agents.map(a => a.id)],
    queryFn: async () => {
      if (!agents || agents.length === 0) return {};

      const counts: Record<string, { total: number; completed: number; failed: number; running: number }> = {};

      await Promise.all(
        agents.map(async (agent) => {
          try {
            const data = await standaloneAgentsApi.listStandaloneAgentExecutions(agent.id, { limit: 100 });
            const executions = data.executions || [];
            counts[agent.id] = {
              total: executions.length,
              completed: executions.filter(e => e.status === "completed").length,
              failed: executions.filter(e => e.status === "failed").length,
              running: executions.filter(e => e.status === "running").length,
            };
          } catch (error) {
            counts[agent.id] = { total: 0, completed: 0, failed: 0, running: 0 };
          }
        })
      );

      return counts;
    },
    enabled: agents.length > 0,
  });

  // Get evaluation summary for each agent (pass-rate, run count) for the inline badge.
  // Fan-out matches the executionCounts pattern above; missing/errored summaries are
  // silently treated as "no runs yet".
  const agentEvaluationSummaries = useQuery({
    queryKey: ["standalone-agents-evaluation-summaries", agents.map(a => a.id)],
    queryFn: async () => {
      if (!agents || agents.length === 0) return {};

      const summaries: Record<string, EvaluationSummary> = {};

      await Promise.all(
        agents.map(async (agent) => {
          try {
            summaries[agent.id] = await evaluationApi.getAgentSummary(agent.id);
          } catch {
            // Treat as no runs.
          }
        })
      );

      return summaries;
    },
    enabled: agents.length > 0,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: standaloneAgentsApi.createStandaloneAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.standaloneAgents });
      toast.success("Agent created successfully");
      setShowCreateDialog(false);
      resetForm();
    },
    onError: (error: any) => {
      toast.error(error.message || "Failed to create agent");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: StandaloneAgentCreate }) =>
      standaloneAgentsApi.updateStandaloneAgent(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.standaloneAgents });
      toast.success("Agent updated successfully");
      setShowCreateDialog(false);
      resetForm();
      setEditingAgentId(null);
    },
    onError: (error: any) => {
      toast.error(error.message || "Failed to update agent");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: standaloneAgentsApi.deleteStandaloneAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.standaloneAgents });
      toast.success("Agent deleted successfully");
      setDeleteDialogAgent(null);
    },
    onError: (error: any) => {
      toast.error(error.message || "Failed to delete agent");
    },
  });

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      role: "planner",
      custom_role_name: "",
      system_prompt: "",
      model_name: "",
      tool_ids: [],
      mcp_server_ids: [],
      data_source_ids: [],
      skill_ids: [],
      memory: { ...DEFAULT_MEMORY_CONFIG },
    });
    setSystemPromptDirty(false);
    setEditingAgentId(null);
  };

  // When the role changes, fetch its prompt template and pre-fill the system
  // prompt — but only while the user hasn't typed in the prompt field yet.
  const handleRoleChange = async (value: AgentRole | "custom") => {
    setFormData((prev) => ({ ...prev, role: value }));

    if (systemPromptDirty) return;
    if (value === "custom") {
      setFormData((prev) => ({ ...prev, role: value, system_prompt: "" }));
      return;
    }

    try {
      const template = await promptsApi.getByRole(value);
      setFormData((prev) => ({
        ...prev,
        role: value,
        system_prompt: template?.template || "",
      }));
    } catch {
      // No template defined for this role — leave the prompt empty.
      setFormData((prev) => ({ ...prev, role: value, system_prompt: "" }));
    }
  };

  // On dialog open in *create* mode, pre-fill the system prompt for the
  // currently-selected role. Without this, the textarea on first open
  // shows only the placeholder ("Auto-filled from the role…") because
  // handleRoleChange only fires on user interaction. We skip when
  // editing (the edit click handler injects the agent's saved prompt
  // and sets systemPromptDirty), or when the user has already typed.
  useEffect(() => {
    if (!showCreateDialog) return;
    if (editingAgentId) return;
    if (systemPromptDirty) return;
    if (formData.system_prompt) return;
    if (formData.role === "custom") return;

    let cancelled = false;
    (async () => {
      try {
        const template = await promptsApi.getByRole(formData.role);
        if (cancelled) return;
        setFormData((prev) =>
          // Race guard: only fill if no edits arrived while we awaited.
          prev.system_prompt
            ? prev
            : { ...prev, system_prompt: template?.template || "" },
        );
      } catch {
        // No template for this role — leave the placeholder visible.
      }
    })();

    return () => {
      cancelled = true;
    };
    // We deliberately depend only on the open transition + role + edit
    // mode, not on `formData.system_prompt`/`systemPromptDirty`, so that
    // typing into the field doesn't re-trigger the fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCreateDialog, editingAgentId, formData.role]);

  const handleCreate = () => {
    if (!formData.name.trim()) {
      toast.error("Agent name is required");
      return;
    }

    if (formData.role === "custom" && !formData.custom_role_name.trim()) {
      toast.error("Custom role name is required when role is Custom");
      return;
    }

    const agentData: StandaloneAgentCreate = {
      name: formData.name,
      role: formData.role,
      system_prompt: formData.system_prompt || undefined,
      model_name: formData.model_name || undefined,
      tool_ids: formData.tool_ids,
      mcp_server_ids: formData.mcp_server_ids,
      data_source_ids: formData.data_source_ids,
      skill_ids: formData.skill_ids,
      // Persist the custom role label inside config so the backend's fixed-set
      // role validation still passes (role stays as "custom" on the column).
      // Memory config rides under config.memory so the standalone-agent route
      // doesn't need a dedicated column.
      config: {
        ...(formData.role === "custom"
          ? { custom_role_name: formData.custom_role_name.trim() }
          : {}),
        memory: formData.memory,
      },
    };

    if (editingAgentId) {
      // Update existing agent
      updateMutation.mutate({ id: editingAgentId, data: agentData });
    } else {
      // Create new agent
      createMutation.mutate(agentData);
    }
  };

  const executionCounts = agentExecutionCounts.data || {};
  const evaluationSummaries: Record<string, EvaluationSummary> = agentEvaluationSummaries.data || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">Standalone Agents</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Individual agents with their own tools, data sources, and MCP servers
          </p>
        </div>
        <div className="flex items-center gap-3">
          {agents.length > 0 && searchQuery && (
            <span className="text-sm text-muted-foreground">
              {filteredAgents.length} of {agents.length}
            </span>
          )}
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Create Agent
          </Button>
        </div>
      </div>

      {/* Search Bar */}
      {agents.length > 0 && (
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search agents by name, description, role, or model..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>
      )}

      {/* Agent List */}
      {isLoading ? (
        <Card>
          <CardContent className="py-16 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
          </CardContent>
        </Card>
      ) : agents.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center space-y-4">
            <Bot className="w-12 h-12 mx-auto text-muted-foreground" />
            <div className="space-y-1">
              <p className="font-medium text-lg">No standalone agents yet</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Create individual agents configured with specific tools, data sources, and capabilities
              </p>
            </div>
            <Button onClick={() => setShowCreateDialog(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create First Agent
            </Button>
          </CardContent>
        </Card>
      ) : filteredAgents.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center space-y-4">
            <SearchIcon className="w-12 h-12 mx-auto text-muted-foreground" />
            <div className="space-y-1">
              <p className="font-medium text-lg">No agents found</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                No agents match your search query &quot;{searchQuery}&quot;
              </p>
            </div>
            <Button variant="outline" onClick={() => setSearchQuery("")}>
              Clear Search
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredAgents.map((agent) => {
            const roleConfig = ROLE_CONFIG[agent.role] || ROLE_CONFIG.custom;
            const RoleIcon = roleConfig.icon;
            const customRoleName =
              agent.role === "custom"
                ? ((agent as any).config?.custom_role_name as string | undefined)
                : undefined;
            const roleLabel = customRoleName?.trim() || roleConfig.label;
            const execStats = executionCounts[agent.id] || { total: 0, completed: 0, failed: 0, running: 0 };
            const evalSummary = evaluationSummaries[agent.id];
            const evalPassPct = evalSummary && evalSummary.total_runs > 0
              ? Math.round(evalSummary.avg_pass_rate * 100)
              : null;
            const evalToneClass =
              evalPassPct === null
                ? ""
                : evalPassPct >= 85
                  ? "text-green-600 dark:text-green-400"
                  : evalPassPct >= 60
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-red-600 dark:text-red-400";

            return (
              <Card
                key={agent.id}
                className="group relative overflow-hidden border-2 hover:border-primary/50 transition-all duration-300 hover:shadow-xl"
              >
                {/* Gradient Background Accent */}
                <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500" />

                <CardHeader className="pb-4 pt-5">
                  {/* Header with Icon and Badge */}
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      {/* Icon with gradient background */}
                      <div className="shrink-0 w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg">
                        <RoleIcon className="w-6 h-6 text-white" />
                      </div>

                      {/* Title and Description */}
                      <div className="flex-1 min-w-0">
                        <CardTitle className="text-base font-semibold truncate mb-1">
                          {agent.name}
                        </CardTitle>
                        {agent.description && (
                          <CardDescription className="text-xs line-clamp-2 leading-relaxed">
                            {agent.description}
                          </CardDescription>
                        )}
                      </div>
                    </div>

                    {/* Role Badge */}
                    <Badge className={`${roleConfig.color} shrink-0 text-xs font-medium`}>
                      {roleLabel}
                    </Badge>
                  </div>

                  {/* Compact Stats Row */}
                  <div className="flex items-center gap-2 text-xs">
                    <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-primary/5 text-primary font-medium">
                      <Zap className="w-3 h-3" />
                      <span>{agent.tool_ids?.length || 0}</span>
                    </div>
                    <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-purple-500/5 text-purple-600 dark:text-purple-400 font-medium">
                      <Database className="w-3 h-3" />
                      <span>{agent.mcp_server_ids?.length || 0}</span>
                    </div>
                    <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-blue-500/5 text-blue-600 dark:text-blue-400 font-medium">
                      <FileText className="w-3 h-3" />
                      <span>{agent.data_source_ids?.length || 0}</span>
                    </div>
                    <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-pink-500/5 text-pink-600 dark:text-pink-400 font-medium">
                      <Brain className="w-3 h-3" />
                      <span>{agent.skill_ids?.length || 0}</span>
                    </div>
                    {evalPassPct !== null && (
                      <div
                        className={`flex items-center gap-1 px-2 py-1 rounded-md bg-muted/40 font-medium cursor-pointer hover:bg-muted/70 transition-colors ${evalToneClass}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          router.push(`/agents/standalone/${agent.id}/execute?tab=evaluations`);
                        }}
                        title={`${evalSummary!.total_runs} eval run${evalSummary!.total_runs === 1 ? '' : 's'} · avg score ${(evalSummary!.avg_score * 10).toFixed(1)}/10`}
                      >
                        <TrendingUp className="w-3 h-3" />
                        <span>{evalPassPct}%</span>
                      </div>
                    )}
                  </div>
                </CardHeader>

                <CardContent className="space-y-3 pt-0">
                  {/* Execution History Compact View - Always Shown */}
                  <div
                    className={`p-2.5 bg-gradient-to-r from-muted/30 to-muted/50 rounded-lg border border-muted-foreground/10 transition-all ${
                      execStats.total > 0
                        ? 'cursor-pointer hover:border-primary/30 group/history'
                        : 'cursor-default opacity-60'
                    }`}
                    onClick={() => {
                      if (execStats.total > 0) {
                        router.push(`/agents/standalone/${agent.id}/execute?tab=history`);
                      }
                    }}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-medium flex items-center gap-1.5">
                        <Activity className="w-3.5 h-3.5" />
                        Execution History
                      </span>
                      <Badge variant="outline" className="text-xs h-5 px-1.5">
                        {execStats.total} total
                      </Badge>
                    </div>
                    <div className="flex gap-3">
                      <div className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400 font-medium">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>{execStats.completed || 0}</span>
                      </div>
                      <div className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-medium">
                        <AlertCircle className="w-3 h-3" />
                        <span>{execStats.failed || 0}</span>
                      </div>
                      <div className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 font-medium">
                        <Loader2 className={`w-3 h-3 ${execStats.running > 0 ? 'animate-spin' : ''}`} />
                        <span>{execStats.running || 0}</span>
                      </div>
                    </div>
                  </div>

                  {/* Model Info */}
                  {agent.model_name && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground px-2 py-1.5 bg-muted/30 rounded-md">
                      <Bot className="w-3 h-3" />
                      <span className="truncate font-mono" title={agent.model_name}>
                        {agent.model_name}
                      </span>
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div className="flex gap-2 pt-1">
                    <Button
                      size="sm"
                      className="flex-1 h-8 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-md"
                      onClick={() => router.push(`/agents/standalone/${agent.id}/execute`)}
                    >
                      <Play className="w-3.5 h-3.5 mr-1.5" />
                      Execute
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8"
                      onClick={() => {
                        const cfg = (agent as any).config || {};
                        setFormData({
                          name: agent.name,
                          role: agent.role as AgentRole | "custom",
                          custom_role_name:
                            typeof cfg.custom_role_name === "string"
                              ? cfg.custom_role_name
                              : "",
                          description: agent.description || "",
                          system_prompt: agent.system_prompt || "",
                          model_name: agent.model_name || "",
                          tool_ids: agent.tool_ids || [],
                          data_source_ids: agent.data_source_ids || [],
                          mcp_server_ids: agent.mcp_server_ids || [],
                          skill_ids: agent.skill_ids || [],
                          memory: {
                            ...DEFAULT_MEMORY_CONFIG,
                            ...(cfg.memory || {}),
                          },
                        });
                        // Editing an existing agent — keep its prompt as-is.
                        setSystemPromptDirty(true);
                        setEditingAgentId(agent.id);
                        setShowCreateDialog(true);
                      }}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8"
                      title="Memory inspector"
                      onClick={() => router.push(`/agents/standalone/${agent.id}/memory`)}
                    >
                      <Brain className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8"
                      title="Evaluations"
                      onClick={() => router.push(`/agents/standalone/${agent.id}/execute?tab=evaluations`)}
                    >
                      <BarChart3 className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 hover:bg-destructive hover:text-destructive-foreground hover:border-destructive"
                      onClick={() => setDeleteDialogAgent(agent.id)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>

                  {/* Status Footer */}
                  <div className="flex items-center gap-2 pt-1 border-t border-muted-foreground/10">
                    <div className="flex items-center gap-1.5 text-xs">
                      <div className={`w-1.5 h-1.5 rounded-full ${
                        agent.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                      }`} />
                      <span className="text-muted-foreground capitalize">{agent.status}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="w-[min(70vw,1200px)] max-w-[min(70vw,1200px)] sm:max-w-[min(70vw,1200px)] max-h-[88vh] overflow-hidden p-0 flex flex-col">
          <DialogHeader className="px-6 pt-6 pb-3 border-b shrink-0">
            <DialogTitle className="text-lg font-semibold">
              {editingAgentId ? "Edit Agent" : "Create Standalone Agent"}
            </DialogTitle>
            <p className="text-xs text-muted-foreground">
              Configure your agent with tools, data sources, and skills
            </p>
          </DialogHeader>

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {/* Basics — Name + Role on one row */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-xs font-medium">
                  Agent Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="My Research Agent"
                  className="h-9"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="role" className="text-xs font-medium">Role</Label>
                <Select value={formData.role} onValueChange={(value: any) => handleRoleChange(value)}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                    {AVAILABLE_ROLES.map((role) => (
                      <SelectItem key={role.value} value={role.value}>
                        {role.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Custom Role Name — only when role === "custom" */}
            {formData.role === "custom" && (
              <div className="space-y-1.5">
                <Label htmlFor="custom_role_name" className="text-xs font-medium">
                  Custom Role Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="custom_role_name"
                  value={formData.custom_role_name}
                  onChange={(e) =>
                    setFormData({ ...formData, custom_role_name: e.target.value })
                  }
                  placeholder="e.g. Compliance Auditor"
                  className="h-9"
                />
              </div>
            )}

            {/* Configuration: model picker + system prompt */}
            <div className="space-y-3">
              <AgentModelSelector
                selectedModelName={formData.model_name}
                onSelect={(model) => setFormData({ ...formData, model_name: model.name || "" })}
                label="Language Model"
                description="Uses default if not specified."
              />

              <div className="space-y-1.5">
                <Label htmlFor="system_prompt" className="text-xs font-medium">
                  System Prompt
                </Label>
                <Textarea
                  id="system_prompt"
                  value={formData.system_prompt}
                  onChange={(e) => {
                    setFormData({ ...formData, system_prompt: e.target.value });
                    setSystemPromptDirty(true);
                  }}
                  placeholder="Auto-filled from the role. Edit to customize."
                  rows={4}
                  className="resize-none text-sm"
                />
              </div>
            </div>

            {/* Resources — tabbed */}
            <div className="space-y-2 pt-1">
              <Label className="text-xs font-medium">Resources</Label>
              <Tabs defaultValue="tools" className="w-full">
                <TabsList className="grid w-full grid-cols-5 h-9">
                  <TabsTrigger value="tools" className="text-xs">
                    Tools
                    {formData.tool_ids.length > 0 && (
                      <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                        {formData.tool_ids.length}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="mcp" className="text-xs">
                    MCP
                    {formData.mcp_server_ids.length > 0 && (
                      <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                        {formData.mcp_server_ids.length}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="sources" className="text-xs">
                    Sources
                    {formData.data_source_ids.length > 0 && (
                      <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                        {formData.data_source_ids.length}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="skills" className="text-xs">
                    Skills
                    {formData.skill_ids.length > 0 && (
                      <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                        {formData.skill_ids.length}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="memory" className="text-xs">
                    <Brain className="w-3 h-3 mr-1" />
                    Memory
                    <Badge variant="secondary" className="ml-1.5 h-4 px-1.5 text-[10px]">
                      {[
                        formData.memory.short_term_enabled,
                        formData.memory.episodic_enabled,
                        formData.memory.semantic_enabled,
                        formData.memory.procedural_enabled,
                      ].filter(Boolean).length}
                      /4
                    </Badge>
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="tools" className="mt-3">
                  <ResourceSelectionSection
                    type="tools"
                    hideHeader
                    listHeight={260}
                    items={tools.map((t: any) => ({
                      id: t.id,
                      name: t.name,
                      description: t.description,
                      badge: t.category,
                    }))}
                    selectedIds={formData.tool_ids}
                    onSelect={(id) => setFormData({ ...formData, tool_ids: [...formData.tool_ids, id] })}
                    onDeselect={(id) => setFormData({ ...formData, tool_ids: formData.tool_ids.filter((x) => x !== id) })}
                    loading={false}
                  />
                </TabsContent>

                <TabsContent value="mcp" className="mt-3">
                  <ResourceSelectionSection
                    type="mcp"
                    hideHeader
                    listHeight={260}
                    items={mcpServers.map((m: any) => ({
                      id: m.id,
                      name: m.name,
                      description: m.description,
                      badge: m.protocol,
                    }))}
                    selectedIds={formData.mcp_server_ids}
                    onSelect={(id) =>
                      setFormData({ ...formData, mcp_server_ids: [...formData.mcp_server_ids, id] })
                    }
                    onDeselect={(id) =>
                      setFormData({
                        ...formData,
                        mcp_server_ids: formData.mcp_server_ids.filter((x) => x !== id),
                      })
                    }
                    loading={false}
                  />
                </TabsContent>

                <TabsContent value="sources" className="mt-3">
                  <ResourceSelectionSection
                    type="datasources"
                    hideHeader
                    listHeight={260}
                    items={sources.map((s: any) => ({
                      id: s.id,
                      name: s.title,
                      description: s.description,
                      badge: s.source_type,
                    }))}
                    selectedIds={formData.data_source_ids}
                    onSelect={(id) => setFormData({ ...formData, data_source_ids: [...formData.data_source_ids, id] })}
                    onDeselect={(id) =>
                      setFormData({ ...formData, data_source_ids: formData.data_source_ids.filter((x) => x !== id) })
                    }
                    loading={false}
                  />
                </TabsContent>

                <TabsContent value="skills" className="mt-3">
                  <ResourceSelectionSection
                    type="skills"
                    hideHeader
                    listHeight={260}
                    items={skills.map((s: Skill) => ({
                      id: s.id,
                      name: s.name,
                      description: s.description || "",
                      badge: s.category,
                    }))}
                    selectedIds={formData.skill_ids}
                    onSelect={(id) => setFormData({ ...formData, skill_ids: [...formData.skill_ids, id] })}
                    onDeselect={(id) => setFormData({ ...formData, skill_ids: formData.skill_ids.filter((x) => x !== id) })}
                    loading={skillsLoading}
                    error={skillsError as Error | null}
                  />
                </TabsContent>

                <TabsContent value="memory" className="mt-3">
                  <MemoryConfigSection
                    value={formData.memory}
                    onChange={(memory) => setFormData((prev) => ({ ...prev, memory }))}
                    agentId={editingAgentId}
                  />
                </TabsContent>
              </Tabs>
            </div>
          </div>

          <DialogFooter className="px-6 py-3 border-t shrink-0 gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowCreateDialog(false);
                resetForm();
              }}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={handleCreate} disabled={createMutation.isPending || updateMutation.isPending}>
              {(createMutation.isPending || updateMutation.isPending) && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              {editingAgentId ? "Update Agent" : "Create Agent"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteDialogAgent} onOpenChange={() => setDeleteDialogAgent(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Agent?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the agent and all its execution history. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteDialogAgent && deleteMutation.mutate(deleteDialogAgent)}
              className="bg-destructive hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
