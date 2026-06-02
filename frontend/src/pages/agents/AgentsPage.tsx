import { useState, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { agentsApi } from "@/lib/api/agents";
import { modelsApi } from "@/lib/api/models";
import { sourcesApi } from "@/lib/api/sources";
import { toolsApi } from "@/lib/api/tools";
import { listStandaloneAgents } from "@/lib/api/standalone-agents";
import { queryKeys } from "@/lib/query-client";
import type {
  AgentTeam,
  TeamCreateRequest,
  Agent,
  AgentConfig,
  AgentRole,
  OrchestrationPattern,
  PatternConfig,
  StandaloneAgent,
} from "@/lib/types";
import { ORCHESTRATION_PATTERNS } from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
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
  Bot,
  Plus,
  Trash2,
  Users,
  Loader2,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Activity,
  Brain,
  Search as SearchIcon,
  FileText,
  Zap,
  Pencil,
  Play,
  CheckCircle2,
  AlertCircle,
  Database,
  Workflow,
  Award,
  Network,
  Code2,
} from "lucide-react";
import { toast } from "sonner";
import { AgentTeamViewer } from "@/components/agents/AgentTeamViewer";
import { MemoryBrowser } from "@/components/memory/MemoryBrowser";
import { StandaloneAgentsManager } from "@/components/agents/StandaloneAgentsManager";
import { AgentApiConsole } from "@/components/agents/AgentApiConsole";
import { useNavigate } from "react-router-dom";

// ---------------------------------------------------------------------------
// Role display helpers
// ---------------------------------------------------------------------------

const ROLE_CONFIG: Record<
  string,
  { label: string; color: string; icon: typeof Bot }
> = {
  planner: { label: "Planner", color: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200", icon: Brain },
  researcher: { label: "Researcher", color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200", icon: SearchIcon },
  analyst: { label: "Analyst", color: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200", icon: Activity },
  writer: { label: "Writer", color: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200", icon: FileText },
  reviewer: { label: "Reviewer", color: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200", icon: Zap },
  judge: { label: "Judge", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200", icon: Award },
  data_scientist: { label: "Data Scientist", color: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200", icon: Activity },
  developer: { label: "Developer", color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", icon: Bot },
  tester: { label: "Tester", color: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200", icon: Zap },
  designer: { label: "Designer", color: "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200", icon: Pencil },
  coordinator: { label: "Coordinator", color: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200", icon: Users },
  custom: { label: "Custom", color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200", icon: Bot },
};

const AVAILABLE_ROLES: { value: AgentRole; label: string }[] = [
  { value: "planner", label: "Planner" },
  { value: "researcher", label: "Researcher" },
  { value: "analyst", label: "Analyst" },
  { value: "data_scientist", label: "Data Scientist" },
  { value: "writer", label: "Writer" },
  { value: "developer", label: "Developer" },
  { value: "tester", label: "Tester" },
  { value: "designer", label: "Designer" },
  { value: "reviewer", label: "Reviewer" },
  { value: "judge", label: "Judge" },
  { value: "coordinator", label: "Coordinator" },
  { value: "custom", label: "Custom" },
];

const AVAILABLE_CAPABILITIES = [
  { value: "search", label: "Search & Retrieval" },
  { value: "data_query", label: "Data Query (SQL)" },
  { value: "analysis", label: "Data Analysis" },
  { value: "writing", label: "Content Writing" },
  { value: "summarization", label: "Summarization" },
  { value: "code_generation", label: "Code Generation" },
  { value: "reasoning", label: "Complex Reasoning" },
  { value: "planning", label: "Task Planning" },
];

function RoleBadge({ role }: { role: string }) {
  const config = ROLE_CONFIG[role] || {
    label: role,
    color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200",
    icon: Bot,
  };
  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}
    >
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    idle: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
    working: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    waiting: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
    planning: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
    executing: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
    reviewing: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
    completed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
    error: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  };
  return (
    <Badge className={`${colors[status] || colors.idle} border-0`}>
      {status}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Agent Card
// ---------------------------------------------------------------------------

function AgentCard({ agent }: { agent: Agent }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border bg-card">
      <div className="mt-0.5">
        <Bot className="w-5 h-5 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm truncate">{agent.name}</span>
          <StatusBadge status={agent.status} />
        </div>
        {(agent.description || agent.system_prompt) && (
          <p className="text-xs text-muted-foreground line-clamp-1">
            {agent.description || agent.system_prompt}
          </p>
        )}
        <div className="flex items-center gap-2 flex-wrap">
          <RoleBadge role={agent.role} />
          {(agent.model || agent.model_override) && (
            <span className="text-xs text-muted-foreground font-mono">
              {agent.model || agent.model_override}
            </span>
          )}
          {((agent.tools && agent.tools.length > 0) || (agent.tool_ids && agent.tool_ids.length > 0)) && (
            <span className="text-xs text-muted-foreground">
              {(agent.tools?.length || agent.tool_ids?.length || 0)} tool{(agent.tools?.length || agent.tool_ids?.length || 0) !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Team Card
// ---------------------------------------------------------------------------

function TeamCard({
  team,
  onDelete,
  onEdit,
  isSelected,
  onSelect,
  execStats,
}: {
  team: AgentTeam;
  onDelete: (team: AgentTeam) => void;
  onEdit: (team: AgentTeam) => void;
  isSelected?: boolean;
  onSelect?: () => void;
  execStats?: { total: number; completed: number; failed: number; running: number };
}) {
  const navigate = useNavigate();

  return (
    <Card
      className={`group relative overflow-hidden border-2 hover:border-primary/50 transition-all duration-300 hover:shadow-xl ${
        isSelected ? "ring-2 ring-blue-500" : ""
      }`}
    >
      {/* Gradient Background Accent */}
      <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500" />

      <CardHeader className="pb-4 pt-5">
        {/* Header with Icon and Badge */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            {/* Icon with gradient background */}
            <div className="shrink-0 w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg">
              <Users className="w-6 h-6 text-white" />
            </div>

            {/* Title and Description */}
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-base truncate mb-1">{team.name}</h3>
              {team.description && (
                <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                  {team.description}
                </p>
              )}
            </div>
          </div>

          {/* Agent Count Badge */}
          <Badge variant="outline" className="shrink-0 text-xs font-medium">
            {team.agents.length} agent{team.agents.length !== 1 ? "s" : ""}
          </Badge>
        </div>

        {/* Architecture pattern badge */}
        {team.orchestration_pattern && (
          <div className="mb-2">
            <Badge
              variant="secondary"
              className="text-[10px] font-medium gap-1"
              title={
                ORCHESTRATION_PATTERNS.find((p) => p.key === team.orchestration_pattern)
                  ?.description || team.orchestration_pattern
              }
            >
              <Network className="w-3 h-3" />
              {ORCHESTRATION_PATTERNS.find((p) => p.key === team.orchestration_pattern)
                ?.label || team.orchestration_pattern}
            </Badge>
          </div>
        )}

        {/* Compact Stats Row */}
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-primary/5 text-primary font-medium">
            <Workflow className="w-3 h-3" />
            <span>
              {team.agents.reduce((sum, agent) =>
                sum + (agent.tools?.length || agent.tool_ids?.length || 0), 0
              )}
            </span>
          </div>
          <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-blue-500/5 text-blue-600 dark:text-blue-400 font-medium">
            <Database className="w-3 h-3" />
            <span>
              {team.agents.reduce((sum, agent) =>
                sum + (agent.data_source_ids?.length || 0), 0
              )}
            </span>
          </div>
        </div>

        {/* Agent Roles */}
        {team.agents.length > 0 && (
          <div className="space-y-1.5 mt-2">
            <div className="flex flex-wrap gap-1.5">
              {team.agents.map((agent, idx) => (
                <div key={idx} className="group relative">
                  <RoleBadge role={agent.role} />
                  {/* Agent name tooltip */}
                  <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-1 px-2 py-1 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                    {agent.name}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-3 pt-0">
        {/* Execution History Compact View - Always Shown */}
        <div
          className={`p-2.5 bg-gradient-to-r from-muted/30 to-muted/50 rounded-lg border border-muted-foreground/10 transition-all ${
            execStats && execStats.total > 0
              ? 'cursor-pointer hover:border-primary/30 group/history'
              : 'cursor-default opacity-60'
          }`}
          onClick={() => {
            if (execStats && execStats.total > 0) {
              navigate(`/agents/teams/${team.id}/execute?tab=history`);
            }
          }}
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5" />
              Execution History
            </span>
            <Badge variant="outline" className="text-xs h-5 px-1.5">
              {execStats?.total || 0} total
            </Badge>
          </div>
          <div className="flex gap-3">
            <div className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400 font-medium">
              <CheckCircle2 className="w-3 h-3" />
              <span>{execStats?.completed || 0}</span>
            </div>
            <div className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-medium">
              <AlertCircle className="w-3 h-3" />
              <span>{execStats?.failed || 0}</span>
            </div>
            <div className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 font-medium">
              <Loader2 className={`w-3 h-3 ${execStats?.running && execStats.running > 0 ? 'animate-spin' : ''}`} />
              <span>{execStats?.running || 0}</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2 pt-1">
          <Button
            size="sm"
            className="flex-1 h-8 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 shadow-md"
            onClick={() => navigate(`/agents/teams/${team.id}/execute`)}
          >
            <Play className="w-3.5 h-3.5 mr-1.5" />
            Execute
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8"
            onClick={(e) => {
              e.stopPropagation();
              onEdit(team);
            }}
          >
            <Pencil className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 hover:bg-destructive hover:text-destructive-foreground hover:border-destructive"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(team);
            }}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Create Team Dialog
//
// New shape: pick existing standalone agents from a multi-select dropdown,
// then choose a Team Architecture pattern. The pattern drives execution on
// the backend (see backend/open_notebook/agents/patterns/).
// ---------------------------------------------------------------------------

function CreateTeamDialog({
  open,
  onClose,
  editingTeam,
}: {
  open: boolean;
  onClose: () => void;
  editingTeam?: AgentTeam;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [agentIds, setAgentIds] = useState<string[]>([]);
  const [pattern, setPattern] = useState<OrchestrationPattern>("orchestrator_worker");
  const [patternConfig, setPatternConfig] = useState<PatternConfig>({});
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [maxIterations, setMaxIterations] = useState<number | "">("");
  const [timeoutSeconds, setTimeoutSeconds] = useState<number | "">("");
  const [autoAnswer, setAutoAnswer] = useState(false);
  const [agentPickerOpen, setAgentPickerOpen] = useState(false);
  const [agentSearch, setAgentSearch] = useState("");

  // Fetch the standalone-agent catalog to populate the multi-select.
  const { data: standaloneData } = useQuery({
    queryKey: ["standalone-agents", "for-team-picker"],
    queryFn: () => listStandaloneAgents({ status: "active", limit: 200 }),
    enabled: open,
  });
  const standaloneAgents: StandaloneAgent[] = standaloneData?.agents || [];
  const standaloneById = useMemo(
    () => Object.fromEntries(standaloneAgents.map((a) => [a.id, a])),
    [standaloneAgents]
  );

  // Selected agents in the order the user added them. Drives Sequential
  // pattern execution order. Reorderable in-place via ↑/↓ buttons.
  const selectedAgents = useMemo(
    () => agentIds.map((id) => standaloneById[id]).filter(Boolean) as StandaloneAgent[],
    [agentIds, standaloneById]
  );

  // Load editing team data when dialog opens
  useEffect(() => {
    if (open && editingTeam) {
      setName(editingTeam.name);
      setDescription(editingTeam.description || "");
      // Prefer the standalone_agent_id back-link; fall back to instance.id
      // for legacy teams (which won't resolve in the dropdown but at least
      // won't crash).
      const ids = editingTeam.agents
        .map((a) => a.standalone_agent_id)
        .filter((id): id is string => Boolean(id));
      setAgentIds(ids);
      setPattern((editingTeam.orchestration_pattern as OrchestrationPattern) || "orchestrator_worker");
      setPatternConfig(editingTeam.pattern_config || {});
      const cfg = (editingTeam as any).config || {};
      setAutoAnswer(Boolean(cfg.auto_answer));
      setMaxIterations(typeof cfg.max_iterations === "number" ? cfg.max_iterations : "");
      setTimeoutSeconds(typeof cfg.timeout_seconds === "number" ? cfg.timeout_seconds : "");
    } else if (open && !editingTeam) {
      setName("");
      setDescription("");
      setAgentIds([]);
      setPattern("orchestrator_worker");
      setPatternConfig({});
      setMaxIterations("");
      setTimeoutSeconds("");
      setAutoAnswer(false);
      setShowAdvanced(false);
    }
  }, [open, editingTeam]);

  // Sensible defaults for pattern_config whenever the pattern changes or the
  // selected-agent list changes — picks orchestrator/router as the first
  // planner/coordinator if the user hasn't explicitly chosen one.
  useEffect(() => {
    if (selectedAgents.length === 0) return;
    const next: PatternConfig = { ...patternConfig };
    const findByRole = (role: string) =>
      selectedAgents.find((a) => (a.role || "").toLowerCase() === role)?.id;
    const firstId = selectedAgents[0]?.id;
    const secondId = selectedAgents[1]?.id;

    const inSelection = (id?: string) => Boolean(id && agentIds.includes(id));

    if (pattern === "orchestrator_worker" || pattern === "router") {
      if (!inSelection(next.orchestrator_agent_id)) {
        next.orchestrator_agent_id =
          findByRole("planner") || findByRole("coordinator") || firstId;
      }
    }
    if (pattern === "review_critique") {
      if (!inSelection(next.producer_agent_id)) {
        next.producer_agent_id = firstId;
      }
      if (!inSelection(next.reviewer_agent_id) || next.reviewer_agent_id === next.producer_agent_id) {
        next.reviewer_agent_id =
          findByRole("reviewer") || findByRole("judge") || secondId || firstId;
      }
      if (!next.max_rounds) next.max_rounds = 3;
    }
    if (pattern === "group_chat") {
      if (!next.max_turns) next.max_turns = 5;
    }
    setPatternConfig(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pattern, agentIds.join(",")]);

  // Mutations
  const createMutation = useMutation({
    mutationFn: (req: TeamCreateRequest) => agentsApi.createTeam(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agentTeams });
      toast.success("Team created");
      onClose();
    },
    onError: () => toast.error("Failed to create team"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, req }: { id: string; req: TeamCreateRequest }) =>
      agentsApi.updateTeam(id, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agentTeams });
      toast.success("Team updated");
      onClose();
    },
    onError: () => toast.error("Failed to update team"),
  });

  const toggleAgent = (id: string) => {
    setAgentIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };
  const removeAgent = (id: string) => setAgentIds((prev) => prev.filter((x) => x !== id));
  const moveAgent = (idx: number, delta: number) => {
    setAgentIds((prev) => {
      const next = [...prev];
      const target = idx + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  };

  const filteredCatalog = useMemo(() => {
    const q = agentSearch.trim().toLowerCase();
    if (!q) return standaloneAgents;
    return standaloneAgents.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.role || "").toLowerCase().includes(q) ||
        (a.description || "").toLowerCase().includes(q)
    );
  }, [agentSearch, standaloneAgents]);

  const handleSubmit = () => {
    if (!name.trim()) {
      toast.error("Team name is required");
      return;
    }
    if (agentIds.length === 0) {
      toast.error("Select at least one agent");
      return;
    }
    // Per-pattern minimums.
    if ((pattern === "review_critique") && agentIds.length < 2) {
      toast.error("Review & Critique needs at least two agents (producer + reviewer)");
      return;
    }
    if ((pattern === "router" || pattern === "orchestrator_worker") && agentIds.length < 2) {
      toast.error(`${pattern === "router" ? "Router" : "Orchestrator-Worker"} needs at least two agents`);
      return;
    }

    const config: Record<string, any> = {};
    if (typeof maxIterations === "number") config.max_iterations = maxIterations;
    if (typeof timeoutSeconds === "number") config.timeout_seconds = timeoutSeconds;
    if (autoAnswer) config.auto_answer = true;

    const request: TeamCreateRequest = {
      name: name.trim(),
      description: description.trim() || undefined,
      agent_ids: agentIds,
      orchestration_pattern: pattern,
      pattern_config: patternConfig,
      config: Object.keys(config).length ? config : undefined,
    };

    if (editingTeam) {
      updateMutation.mutate({ id: editingTeam.id, req: request });
    } else {
      createMutation.mutate(request);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            {editingTeam ? "Edit Agent Team" : "Create Agent Team"}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Team info */}
          <div className="space-y-4">
            <div>
              <Label>Team Name</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Research Team"
              />
            </div>
            <div>
              <Label>Goal</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What is this team trying to achieve?"
                rows={2}
              />
            </div>
          </div>

          {/* Agents — multi-select dropdown sourced from standalone agents */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-base font-semibold">Agents</Label>
              <Popover open={agentPickerOpen} onOpenChange={setAgentPickerOpen}>
                <PopoverTrigger asChild>
                  <Button variant="outline" size="sm">
                    <Plus className="w-3.5 h-3.5 mr-1" />
                    Select agents
                    <ChevronDown className="w-3.5 h-3.5 ml-1" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent
                  className="w-[400px] p-0 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700"
                  align="end"
                >
                  <div className="p-2 border-b border-gray-200 dark:border-gray-800">
                    <Input
                      autoFocus
                      placeholder="Search agents…"
                      value={agentSearch}
                      onChange={(e) => setAgentSearch(e.target.value)}
                      className="h-8"
                    />
                  </div>
                  <div className="max-h-72 overflow-y-auto p-2 space-y-1">
                    {filteredCatalog.length === 0 ? (
                      <p className="text-xs text-muted-foreground p-2">
                        {standaloneAgents.length === 0
                          ? "No standalone agents yet. Create some on the Agents tab first."
                          : "No matches."}
                      </p>
                    ) : (
                      filteredCatalog.map((a) => {
                        const checked = agentIds.includes(a.id);
                        return (
                          <label
                            key={a.id}
                            className="flex items-start gap-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
                          >
                            <Checkbox
                              checked={checked}
                              onCheckedChange={() => toggleAgent(a.id)}
                              className="mt-0.5"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium truncate">{a.name}</span>
                                <Badge variant="outline" className="text-[10px] py-0">
                                  {a.role}
                                </Badge>
                              </div>
                              {a.description && (
                                <p className="text-xs text-muted-foreground line-clamp-2">
                                  {a.description}
                                </p>
                              )}
                            </div>
                          </label>
                        );
                      })
                    )}
                  </div>
                </PopoverContent>
              </Popover>
            </div>

            {/* Selected agents — badge row with remove + reorder */}
            <div className="border rounded-md p-3 min-h-[60px] bg-gray-50 dark:bg-gray-900">
              {selectedAgents.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No agents selected. Click "Select agents" to add some.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {selectedAgents.map((a, idx) => (
                    <li
                      key={a.id}
                      className="flex items-center gap-2 bg-white dark:bg-gray-800 rounded px-2 py-1.5 border border-gray-200 dark:border-gray-700"
                    >
                      <span className="text-xs text-muted-foreground tabular-nums w-5">
                        {idx + 1}.
                      </span>
                      <Bot className="w-3.5 h-3.5 text-muted-foreground" />
                      <span className="text-sm font-medium flex-1 truncate">{a.name}</span>
                      <Badge variant="outline" className="text-[10px] py-0">
                        {a.role}
                      </Badge>
                      {pattern === "sequential" && (
                        <>
                          <button
                            type="button"
                            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30"
                            disabled={idx === 0}
                            onClick={() => moveAgent(idx, -1)}
                            aria-label="Move up"
                          >
                            <ChevronUp className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-30"
                            disabled={idx === selectedAgents.length - 1}
                            onClick={() => moveAgent(idx, +1)}
                            aria-label="Move down"
                          >
                            <ChevronDown className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                      <button
                        type="button"
                        className="p-1 rounded hover:bg-destructive/10 hover:text-destructive"
                        onClick={() => removeAgent(a.id)}
                        aria-label="Remove agent"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Architecture pattern */}
          <div className="space-y-2">
            <Label className="text-base font-semibold">Team Architecture</Label>
            <RadioGroup
              value={pattern}
              onValueChange={(v) => setPattern(v as OrchestrationPattern)}
              className="grid grid-cols-1 sm:grid-cols-2 gap-2"
            >
              {ORCHESTRATION_PATTERNS.map((p) => (
                <label
                  key={p.key}
                  htmlFor={`pat-${p.key}`}
                  className={`flex items-start gap-3 p-3 rounded-md border cursor-pointer transition-colors ${
                    pattern === p.key
                      ? "border-primary bg-primary/5"
                      : "border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                  }`}
                >
                  <RadioGroupItem value={p.key} id={`pat-${p.key}`} className="mt-1" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-semibold">{p.label}</span>
                      <span className="text-xs text-muted-foreground">{p.tagline}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">{p.description}</p>
                  </div>
                </label>
              ))}
            </RadioGroup>
          </div>

          {/* Pattern-specific options */}
          {selectedAgents.length > 0 && (
            <PatternOptionsPanel
              pattern={pattern}
              agents={selectedAgents}
              config={patternConfig}
              onChange={setPatternConfig}
            />
          )}

          {/* Advanced — defaults are visible inline so users know what's
              applied when they leave the inputs blank. */}
          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <div className="flex items-center justify-between">
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
                >
                  {showAdvanced ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                  Advanced
                </button>
              </CollapsibleTrigger>
              <span className="text-[11px] text-muted-foreground">
                Defaults: max iterations{" "}
                <span className="font-mono">
                  {typeof maxIterations === "number" ? maxIterations : 10}
                </span>
                {typeof maxIterations === "number" && (
                  <span className="text-primary"> (overridden)</span>
                )}
                , timeout{" "}
                <span className="font-mono">
                  {typeof timeoutSeconds === "number" ? timeoutSeconds : 300}
                </span>
                s
                {typeof timeoutSeconds === "number" && (
                  <span className="text-primary"> (overridden)</span>
                )}
              </span>
            </div>
            <CollapsibleContent className="mt-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label className="text-xs">
                    Max iterations <span className="text-muted-foreground">(default 10)</span>
                  </Label>
                  <Input
                    type="number"
                    min={1}
                    placeholder="10"
                    value={maxIterations}
                    onChange={(e) =>
                      setMaxIterations(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  />
                </div>
                <div>
                  <Label className="text-xs">
                    Timeout (seconds) <span className="text-muted-foreground">(default 300)</span>
                  </Label>
                  <Input
                    type="number"
                    min={1}
                    placeholder="300"
                    value={timeoutSeconds}
                    onChange={(e) =>
                      setTimeoutSeconds(e.target.value === "" ? "" : Number(e.target.value))
                    }
                  />
                </div>
              </div>

              {/* Auto-answer: when an agent asks the user for clarification,
                  the orchestrator synthesizes a plausible answer from the
                  team goal instead of pausing. Useful for unattended runs. */}
              <label className="mt-3 flex items-start gap-2 cursor-pointer">
                <Checkbox
                  checked={autoAnswer}
                  onCheckedChange={(v) => setAutoAnswer(Boolean(v))}
                  className="mt-0.5"
                />
                <div className="text-xs">
                  <div className="font-medium">Auto-answer clarifying questions</div>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    If an agent asks for clarification, synthesize an answer
                    from the team goal and continue. Off by default — the
                    user is prompted via a popup.
                  </p>
                </div>
              </label>
            </CollapsibleContent>
          </Collapsible>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            {(createMutation.isPending || updateMutation.isPending) ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {editingTeam ? "Updating..." : "Creating..."}
              </>
            ) : (
              editingTeam ? "Update Team" : "Create Team"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Per-pattern options panel
//
// Shown below the pattern radio group; renders only the controls relevant to
// the chosen pattern so the dialog stays compact.
// ---------------------------------------------------------------------------

function PatternOptionsPanel({
  pattern,
  agents,
  config,
  onChange,
}: {
  pattern: OrchestrationPattern;
  agents: StandaloneAgent[];
  config: PatternConfig;
  onChange: (next: PatternConfig) => void;
}) {
  const set = (patch: PatternConfig) => onChange({ ...config, ...patch });

  if (pattern === "sequential") {
    return (
      <div className="rounded-md border border-dashed border-gray-300 dark:border-gray-700 p-3 text-xs text-muted-foreground">
        Agents will run in the order shown above. Use the ↑/↓ buttons to reorder.
      </div>
    );
  }

  const AgentSelect = ({
    label,
    valueKey,
    placeholder,
  }: {
    label: string;
    valueKey: keyof PatternConfig;
    placeholder: string;
  }) => (
    <div>
      <Label className="text-xs">{label}</Label>
      <Select
        value={(config[valueKey] as string) || ""}
        onValueChange={(v) => set({ [valueKey]: v } as PatternConfig)}
      >
        <SelectTrigger>
          <SelectValue placeholder={placeholder} />
        </SelectTrigger>
        <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
          {agents.map((a) => (
            <SelectItem key={a.id} value={a.id}>
              <span className="flex items-center gap-2">
                <span>{a.name}</span>
                <Badge variant="outline" className="text-[10px] py-0">
                  {a.role}
                </Badge>
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );

  return (
    <div className="rounded-md border border-gray-200 dark:border-gray-700 p-3 space-y-3 bg-gray-50 dark:bg-gray-900">
      <div className="text-xs font-medium text-muted-foreground">Pattern options</div>
      {(pattern === "orchestrator_worker" || pattern === "router") && (
        <AgentSelect
          label={pattern === "router" ? "Router agent" : "Orchestrator agent"}
          valueKey="orchestrator_agent_id"
          placeholder="Choose…"
        />
      )}
      {pattern === "review_critique" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <AgentSelect label="Producer" valueKey="producer_agent_id" placeholder="Choose…" />
          <AgentSelect label="Reviewer" valueKey="reviewer_agent_id" placeholder="Choose…" />
          <div className="sm:col-span-2">
            <Label className="text-xs">Max rounds</Label>
            <Input
              type="number"
              min={1}
              max={20}
              value={config.max_rounds ?? 3}
              onChange={(e) => set({ max_rounds: Number(e.target.value) || 3 })}
            />
            <p className="text-[11px] text-muted-foreground mt-1">
              Loop ends early when the reviewer replies with APPROVED.
            </p>
          </div>
        </div>
      )}
      {pattern === "parallel" && (
        <div>
          <Label className="text-xs">Aggregator agent (optional)</Label>
          <Select
            value={(config.aggregator_agent_id as string) || "__none__"}
            onValueChange={(v) =>
              set({ aggregator_agent_id: v === "__none__" ? undefined : v })
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Synthesize via LLM (default)" />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
              <SelectItem value="__none__">Synthesize via LLM (default)</SelectItem>
              {agents.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.name} <span className="text-xs text-muted-foreground">({a.role})</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      {pattern === "group_chat" && (
        <div>
          <Label className="text-xs">Max turns (per agent)</Label>
          <Input
            type="number"
            min={1}
            max={50}
            value={config.max_turns ?? 5}
            onChange={(e) => set({ max_turns: Number(e.target.value) || 5 })}
          />
          <p className="text-[11px] text-muted-foreground mt-1">
            Chat ends early when an agent emits the sentinel <code>&lt;&lt;DONE&gt;&gt;</code>.
          </p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Agents Settings Page
// ---------------------------------------------------------------------------

export default function AgentsSettingsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editingTeam, setEditingTeam] = useState<AgentTeam | null>(null);
  const [deleteTeam, setDeleteTeam] = useState<AgentTeam | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("standalone");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const { data: teamsData = [], isLoading } = useQuery({
    queryKey: queryKeys.agentTeams,
    queryFn: agentsApi.listTeams,
  });

  // Ensure teams is always an array
  const teams = Array.isArray(teamsData) ? teamsData : [];

  // Get execution counts for all teams
  const teamExecutionCounts = useQuery({
    queryKey: ["agent-teams-execution-counts", teams.map(t => t.id)],
    queryFn: async () => {
      if (!teams || teams.length === 0) return {};

      const counts: Record<string, { total: number; completed: number; failed: number; running: number }> = {};

      await Promise.all(
        teams.map(async (team) => {
          try {
            const executions = await agentsApi.listExecutions(team.id);
            counts[team.id] = {
              total: executions.length,
              completed: executions.filter(e => e.status === "completed").length,
              failed: executions.filter(e => e.status === "error").length,
              running: executions.filter(e => e.status === "planning" || e.status === "executing" || e.status === "reviewing").length,
            };
          } catch (error) {
            counts[team.id] = { total: 0, completed: 0, failed: 0, running: 0 };
          }
        })
      );

      return counts;
    },
    enabled: teams.length > 0,
  });

  const executionCounts = teamExecutionCounts.data || {};

  // Filter teams based on search query
  const filteredTeams = teams.filter((team) => {
    if (!searchQuery.trim()) return true;

    const query = searchQuery.toLowerCase();
    return (
      team.name.toLowerCase().includes(query) ||
      team.description?.toLowerCase().includes(query) ||
      team.agents.some(agent =>
        agent.name.toLowerCase().includes(query) ||
        agent.role.toLowerCase().includes(query)
      )
    );
  });

  const deleteMutation = useMutation({
    mutationFn: (teamId: string) => agentsApi.deleteTeam(teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agentTeams });
      toast.success("Team deleted");
      setDeleteTeam(null);
      if (deleteTeam && selectedTeamId === deleteTeam.id) {
        setSelectedTeamId(null);
      }
    },
    onError: () => toast.error("Failed to delete team"),
  });

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Agent(s)</h1>
          <p className="text-muted-foreground mt-1">
            Agent teams that analyze complexity and spawn specialized agents
          </p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="animate-fade-in-up animation-delay-200">
        <TabsList className="h-12">
          <TabsTrigger value="standalone" className="text-sm font-semibold">
            <Bot className="h-4 w-4 mr-1.5" />
            Standalone
          </TabsTrigger>
          <TabsTrigger value="teams" className="text-sm font-semibold">
            <Users className="h-4 w-4 mr-1.5" />
            Teams
          </TabsTrigger>
          <TabsTrigger value="memory" className="text-sm font-semibold">
            <Brain className="h-4 w-4 mr-1.5" />
            Memory
          </TabsTrigger>
          <TabsTrigger value="api" className="text-sm font-semibold">
            <Code2 className="h-4 w-4 mr-1.5" />
            API
          </TabsTrigger>
          <TabsTrigger value="team-api" className="text-sm font-semibold">
            <Code2 className="h-4 w-4 mr-1.5" />
            Team API
          </TabsTrigger>
        </TabsList>

        {/* Teams Tab */}
        <TabsContent value="teams" className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1 max-w-md">
              <div className="relative">
                <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search teams by name, description, or agent role..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              {teams.length > 0 && searchQuery && (
                <span className="text-sm text-muted-foreground">
                  {filteredTeams.length} of {teams.length}
                </span>
              )}
              <Button onClick={() => setShowCreate(true)} size="sm">
                <Plus className="w-4 h-4 mr-2" />
                Create Team
              </Button>
            </div>
          </div>

          {/* Teams list */}
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            </div>
          ) : teams.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 px-4">
              <div className="rounded-full bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 p-6 mb-6 shadow-lg">
                <Users className="w-16 h-16 text-white" />
              </div>
              <h3 className="text-2xl font-bold mb-2">No agent teams yet</h3>
              <p className="text-gray-500 dark:text-gray-400 max-w-md text-center mb-8">
                Create your first team of specialized AI agents that work together to research, analyze, and execute complex tasks autonomously.
              </p>
              <Button onClick={() => setShowCreate(true)} size="lg" className="shadow-lg">
                <Plus className="w-5 h-5 mr-2" />
                Create Orchestration
              </Button>
            </div>
          ) : filteredTeams.length === 0 ? (
            <Card>
              <CardContent className="py-16 text-center space-y-4">
                <SearchIcon className="w-12 h-12 mx-auto text-muted-foreground" />
                <div className="space-y-1">
                  <p className="font-medium text-lg">No teams found</p>
                  <p className="text-sm text-muted-foreground max-w-md mx-auto">
                    No teams match your search query &quot;{searchQuery}&quot;
                  </p>
                </div>
                <Button variant="outline" onClick={() => setSearchQuery("")}>
                  Clear Search
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {filteredTeams.map((team: AgentTeam) => (
                <TeamCard
                  key={team.id}
                  team={team}
                  onDelete={setDeleteTeam}
                  onEdit={(team) => {
                    setEditingTeam(team);
                    setShowCreate(true);
                  }}
                  isSelected={selectedTeamId === team.id}
                  onSelect={() => setSelectedTeamId(team.id)}
                  execStats={executionCounts[team.id]}
                />
              ))}
            </div>
          )}

          {/* Info Card */}
          <Card className="border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30">
            <CardHeader>
              <CardTitle className="text-base">About Agent Teams</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
              <p>
                Agent teams enable multi-agent orchestration where specialized AI agents
                collaborate to handle complex queries. Each agent has a specific role:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                <div className="flex items-center gap-2">
                  <RoleBadge role="researcher" />
                  <span className="text-xs">Searches and retrieves information</span>
                </div>
                <div className="flex items-center gap-2">
                  <RoleBadge role="analyst" />
                  <span className="text-xs">Analyzes data and patterns</span>
                </div>
                <div className="flex items-center gap-2">
                  <RoleBadge role="writer" />
                  <span className="text-xs">Generates formatted output</span>
                </div>
                <div className="flex items-center gap-2">
                  <RoleBadge role="reviewer" />
                  <span className="text-xs">Reviews and validates findings</span>
                </div>
              </div>
              <p className="pt-1">
                Click the <strong>Execute</strong> button on a team card to run queries.
                The query analyzer automatically routes queries based on complexity.
                After running executions, use the <strong>History</strong> button to view past results, steps, and agent messages.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Standalone Agents Tab */}
        <TabsContent value="standalone">
          <StandaloneAgentsManager />
        </TabsContent>

        {/* Memory Tab */}
        <TabsContent value="memory">
          <MemoryBrowser />
        </TabsContent>

        {/* API Tab — REST endpoints, JSON schemas and a live test console for
            every standalone agent. */}
        <TabsContent value="api">
          <AgentApiConsole />
        </TabsContent>

        {/* Team API Tab — same surface as the standalone API tab, but for
            agent teams. Endpoints map to /api/agents/teams/{id}/execute(/stream). */}
        <TabsContent value="team-api">
          <AgentApiConsole kind="team" />
        </TabsContent>
      </Tabs>

      {/* Create/Edit Team Dialog */}
      <CreateTeamDialog
        open={showCreate}
        onClose={() => {
          setShowCreate(false);
          setEditingTeam(null);
        }}
        editingTeam={editingTeam || undefined}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteTeam}
        onOpenChange={() => setDeleteTeam(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete team?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove &quot;{deleteTeam?.name}&quot; and all its
              agents. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() =>
                deleteTeam && deleteMutation.mutate(deleteTeam.id)
              }
              disabled={deleteMutation.isPending}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      </div>
    </div>
  );
}
