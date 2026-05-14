import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { agentsApi } from "@/lib/api/agents";
import { modelsApi } from "@/lib/api/models";
import { sourcesApi } from "@/lib/api/sources";
import { toolsApi } from "@/lib/api/tools";
import { queryKeys } from "@/lib/query-client";
import type {
  AgentTeam,
  TeamCreateRequest,
  Agent,
  AgentConfig,
  AgentRole,
} from "@/lib/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
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
  Activity,
  Brain,
  Search as SearchIcon,
  FileText,
  Zap,
  Pencil,
  Play,
  CheckCircle2,
  AlertCircle,
  History,
} from "lucide-react";
import { toast } from "sonner";
import { AgentTeamViewer } from "@/components/agents/AgentTeamViewer";
import { MemoryBrowser } from "@/components/memory/MemoryBrowser";
import { PromptsManager } from "@/components/agents/PromptsManager";
import { SettingsHeader } from "@/components/settings/settings-header";

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
  onExecute,
  execStats,
}: {
  team: AgentTeam;
  onDelete: (team: AgentTeam) => void;
  onEdit: (team: AgentTeam) => void;
  onExecute: (team: AgentTeam) => void;
  execStats?: { total: number; completed: number; failed: number; running: number };
}) {
  const [expanded, setExpanded] = useState(false);
  const stats = execStats || { total: 0, completed: 0, failed: 0, running: 0 };

  return (
    <Card className="relative">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-primary" />
            <CardTitle className="text-lg">{team.name}</CardTitle>
          </div>
          <StatusBadge status={team.status} />
        </div>
        {team.description && (
          <CardDescription className="mt-2">{team.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Configuration Summary */}
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="text-center p-2 bg-muted rounded">
            <div className="font-medium text-lg">{team.agents.length}</div>
            <div className="text-muted-foreground text-xs">Agents</div>
          </div>
          <div className="text-center p-2 bg-muted rounded">
            <div className="font-medium text-lg">
              {team.agents.reduce((sum, agent) => sum + (agent.tools?.length || agent.tool_ids?.length || 0), 0)}
            </div>
            <div className="text-muted-foreground text-xs">Tools</div>
          </div>
          <div className="text-center p-2 bg-muted rounded">
            <div className="font-medium text-lg">
              {new Date(team.created).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric' })}
            </div>
            <div className="text-muted-foreground text-xs">Created</div>
          </div>
        </div>

        {/* Execution History Summary */}
        {stats.total > 0 && (
          <div className="p-3 bg-muted/50 rounded-lg space-y-2">
            <div className="flex items-center justify-between text-sm font-medium">
              <span>Execution History</span>
              <Badge variant="outline">{stats.total} total</Badge>
            </div>
            <div className="flex gap-2 text-xs flex-wrap">
              {stats.completed > 0 && (
                <div className="flex items-center gap-1 text-green-600 dark:text-green-400">
                  <CheckCircle2 className="w-3 h-3" />
                  <span>{stats.completed} completed</span>
                </div>
              )}
              {stats.failed > 0 && (
                <div className="flex items-center gap-1 text-red-600 dark:text-red-400">
                  <AlertCircle className="w-3 h-3" />
                  <span>{stats.failed} failed</span>
                </div>
              )}
              {stats.running > 0 && (
                <div className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span>{stats.running} running</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Agent list toggle */}
        {team.agents.length > 0 && (
          <>
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-between text-muted-foreground hover:bg-muted/50"
              onClick={(e) => {
                e.stopPropagation();
                setExpanded(!expanded);
              }}
            >
              <span className="text-xs">View agents</span>
              {expanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </Button>
            {expanded && (
              <div className="space-y-2 pt-2">
                {team.agents.map((agent) => (
                  <AgentCard key={agent.id} agent={agent} />
                ))}
              </div>
            )}
          </>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <Button
            className="flex-1"
            onClick={(e) => {
              e.stopPropagation();
              onExecute(team);
            }}
          >
            <Play className="w-4 h-4 mr-2" />
            Execute
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={(e) => {
              e.stopPropagation();
              onEdit(team);
            }}
            title="Edit team"
          >
            <Pencil className="w-4 h-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(team);
            }}
            title="Delete team"
            className="text-destructive hover:text-destructive"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>

        {/* Status */}
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
          <span>Status: {team.status}</span>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Create Team Dialog
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
  const [agents, setAgents] = useState<AgentConfig[]>([
    { name: "Researcher", role: "researcher", description: "Searches and retrieves information from sources" },
  ]);

  // Load editing team data when dialog opens
  useEffect(() => {
    if (open && editingTeam) {
      setName(editingTeam.name);
      setDescription(editingTeam.description || "");

      // Convert agents to AgentConfig format
      const agentConfigs: AgentConfig[] = editingTeam.agents.map((agent) => ({
        name: agent.name,
        role: agent.role,
        description: agent.system_prompt || agent.description || "",
        model: agent.model_override || agent.model,
        tools: agent.tool_ids || agent.tools,
        capabilities: agent.config?.capabilities,
      }));

      setAgents(agentConfigs.length > 0 ? agentConfigs : [
        { name: "Researcher", role: "researcher", description: "Searches and retrieves information from sources" },
      ]);
    } else if (open && !editingTeam) {
      // Reset for new team
      setName("");
      setDescription("");
      setAgents([
        { name: "Researcher", role: "researcher", description: "Searches and retrieves information from sources" },
      ]);
    }
  }, [open, editingTeam]);

  // Fetch available models
  const { data: modelsData } = useQuery({
    queryKey: ["models", "available"],
    queryFn: modelsApi.listAvailable,
  });
  const availableModels = modelsData?.models || [];

  // Fetch available tools
  const { data: toolsData } = useQuery({
    queryKey: ["tools"],
    queryFn: () => toolsApi.list({ enabled: true }),
  });
  const availableTools = toolsData || [];

  // Fetch available data sources (from notebook sources)
  const { data: sourcesData } = useQuery({
    queryKey: ["sources"],
    queryFn: () => sourcesApi.list(),
  });
  const availableSources = sourcesData || [];

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

  const addAgent = () => {
    setAgents([
      ...agents,
      { name: "", role: "analyst", description: "" },
    ]);
  };

  const removeAgent = (index: number) => {
    if (agents.length <= 1) return;
    setAgents(agents.filter((_, i) => i !== index));
  };

  const updateAgent = (index: number, field: keyof AgentConfig, value: string | string[]) => {
    const updated = [...agents];
    (updated[index] as any)[field] = value;
    setAgents(updated);
  };

  // Toggle tool selection
  const toggleTool = (agentIndex: number, toolId: string) => {
    const updated = [...agents];
    const current = updated[agentIndex].tools || [];
    if (current.includes(toolId)) {
      updated[agentIndex].tools = current.filter(id => id !== toolId);
    } else {
      updated[agentIndex].tools = [...current, toolId];
    }
    setAgents(updated);
  };

  // Toggle capability selection
  const toggleCapability = (agentIndex: number, capability: string) => {
    const updated = [...agents];
    const current = updated[agentIndex].capabilities || [];
    if (current.includes(capability)) {
      updated[agentIndex].capabilities = current.filter(c => c !== capability);
    } else {
      updated[agentIndex].capabilities = [...current, capability];
    }
    setAgents(updated);
  };

  const handleSubmit = () => {
    if (!name.trim()) {
      toast.error("Team name is required");
      return;
    }
    if (agents.some((a) => !a.name.trim() || !a.description.trim())) {
      toast.error("All agents need a name and description");
      return;
    }

    const request: TeamCreateRequest = {
      name: name.trim(),
      description: description.trim() || undefined,
      agent_configs: agents,
    };

    if (editingTeam) {
      updateMutation.mutate({ id: editingTeam.id, req: request });
    } else {
      createMutation.mutate(request);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-[90vw] max-h-[90vh] overflow-y-auto">
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
              <Label>Description</Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What does this team do?"
                rows={2}
              />
            </div>
          </div>

          {/* Agent definitions with tabs */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-base font-semibold">Agents</Label>
              <Button size="sm" variant="outline" onClick={addAgent}>
                <Plus className="w-3.5 h-3.5 mr-1" />
                Add Agent
              </Button>
            </div>

            <Tabs defaultValue="agent-0" className="w-full">
              <div className="flex items-center gap-2 mb-4">
                <TabsList className="flex-1 justify-start overflow-x-auto">
                  {agents.map((agent, idx) => (
                    <TabsTrigger
                      key={idx}
                      value={`agent-${idx}`}
                      className="flex items-center gap-2 relative group"
                    >
                      <Bot className="w-3.5 h-3.5" />
                      <span className="max-w-[120px] truncate">
                        {agent.name || `Agent ${idx + 1}`}
                      </span>
                      {agents.length > 1 && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            removeAgent(idx);
                          }}
                          className="ml-1 opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </div>

              {agents.map((agent, idx) => (
                <TabsContent key={idx} value={`agent-${idx}`} className="space-y-4 mt-0">
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Bot className="w-4 h-4" />
                        Agent Configuration
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label className="text-xs">Name</Label>
                          <Input
                            value={agent.name}
                            onChange={(e) =>
                              updateAgent(idx, "name", e.target.value)
                            }
                            placeholder="Agent name"
                          />
                        </div>
                        <div>
                          <Label className="text-xs">Role</Label>
                          <Select
                            value={agent.role}
                            onValueChange={(val) =>
                              updateAgent(idx, "role", val)
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 shadow-lg">
                              {AVAILABLE_ROLES.map((r) => (
                                <SelectItem key={r.value} value={r.value}>
                                  {r.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs">Description</Label>
                        <Textarea
                          value={agent.description}
                          onChange={(e) =>
                            updateAgent(idx, "description", e.target.value)
                          }
                          placeholder="What does this agent do?"
                          rows={3}
                        />
                      </div>
                      <div>
                        <Label className="text-xs">Model (optional)</Label>
                        <Select
                          value={agent.model || "default"}
                          onValueChange={(val) =>
                            updateAgent(idx, "model", val === "default" ? "" : val)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Use default model" />
                    </SelectTrigger>
                    <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 shadow-lg">
                      <SelectItem value="default">
                        <span className="text-muted-foreground">Use default model</span>
                      </SelectItem>
                      {availableModels.length > 0 ? (
                        availableModels.map((model: any) => (
                          <SelectItem key={model.id} value={model.id}>
                            <div className="flex items-center gap-2">
                              <span>{model.name || model.id}</span>
                              <span className="text-xs text-muted-foreground">({model.provider})</span>
                            </div>
                          </SelectItem>
                        ))
                      ) : (
                        <SelectItem value="gpt-4" disabled>
                          <span className="text-xs text-muted-foreground">
                            No models configured - add credentials in API Keys
                          </span>
                        </SelectItem>
                      )}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-1">
                    Select from configured models or leave default
                  </p>
                </div>

                {/* Tools Selection */}
                <div>
                  <Label className="text-xs">Tools (optional)</Label>
                  <div className="border rounded-md p-3 max-h-48 overflow-y-auto space-y-2 bg-gray-50 dark:bg-gray-900">
                    {availableTools.length > 0 ? (
                      availableTools.map((tool: any) => (
                        <div key={tool.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={`tool-${idx}-${tool.id}`}
                            checked={agent.tools?.includes(tool.id) || false}
                            onCheckedChange={() => toggleTool(idx, tool.id)}
                          />
                          <label
                            htmlFor={`tool-${idx}-${tool.id}`}
                            className="text-sm font-normal cursor-pointer flex-1"
                          >
                            <div className="flex items-center justify-between">
                              <span>{tool.name}</span>
                              {tool.category && (
                                <Badge variant="outline" className="text-xs ml-2">
                                  {tool.category}
                                </Badge>
                              )}
                            </div>
                            {tool.description && (
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {tool.description}
                              </p>
                            )}
                          </label>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-muted-foreground">No tools available</p>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Select tools this agent can use
                  </p>
                </div>

                {/* Data Sources Selection */}
                <div>
                  <Label className="text-xs">Data Sources (optional)</Label>
                  <div className="border rounded-md p-3 max-h-48 overflow-y-auto space-y-2 bg-gray-50 dark:bg-gray-900">
                    {availableSources.length > 0 ? (
                      availableSources.map((source: any) => (
                        <div key={source.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={`source-${idx}-${source.id}`}
                            checked={agent.tools?.includes(`source:${source.id}`) || false}
                            onCheckedChange={() => toggleTool(idx, `source:${source.id}`)}
                          />
                          <label
                            htmlFor={`source-${idx}-${source.id}`}
                            className="text-sm font-normal cursor-pointer flex-1"
                          >
                            <div className="flex items-center justify-between">
                              <span>{source.name || source.title}</span>
                              <Badge variant="outline" className="text-xs ml-2">
                                {source.source_type}
                              </Badge>
                            </div>
                          </label>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-muted-foreground">No data sources available</p>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Select data sources this agent can access
                  </p>
                </div>
                    </CardContent>
                  </Card>
                </TabsContent>
              ))}
            </Tabs>
          </div>
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
// Main Agents Settings Page
// ---------------------------------------------------------------------------

export default function SettingsAgentsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);
  const [editingTeam, setEditingTeam] = useState<AgentTeam | null>(null);
  const [deleteTeam, setDeleteTeam] = useState<AgentTeam | null>(null);
  const [activeTab, setActiveTab] = useState<string>("teams");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const { data: teamsData = [], isLoading } = useQuery({
    queryKey: queryKeys.agentTeams,
    queryFn: agentsApi.listTeams,
  });

  // Ensure teams is always an array
  const teams = Array.isArray(teamsData) ? teamsData : [];

  // Fetch execution statistics for all teams
  const [executionCounts, setExecutionCounts] = useState<Record<string, { total: number; completed: number; failed: number; running: number }>>({});

  useEffect(() => {
    const fetchExecutionStats = async () => {
      const stats: Record<string, { total: number; completed: number; failed: number; running: number }> = {};

      for (const team of teams) {
        try {
          const executions = await agentsApi.listExecutions(team.id);
          stats[team.id] = {
            total: executions.length,
            completed: executions.filter(e => e.status === 'completed').length,
            failed: executions.filter(e => e.status === 'error').length,
            running: executions.filter(e => e.status === 'planning' || e.status === 'executing' || e.status === 'reviewing').length,
          };
        } catch (error) {
          stats[team.id] = { total: 0, completed: 0, failed: 0, running: 0 };
        }
      }

      setExecutionCounts(stats);
    };

    if (teams.length > 0) {
      fetchExecutionStats();
    }
  }, [teams]);

  const deleteMutation = useMutation({
    mutationFn: (teamId: string) => agentsApi.deleteTeam(teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agentTeams });
      toast.success("Team deleted");
      setDeleteTeam(null);
    },
    onError: () => toast.error("Failed to delete team"),
  });

  const handleExecute = (team: AgentTeam) => {
    // Navigate to the execution interface in standalone mode
    navigate(`/settings/agents/teams/${team.id}/execute`);
  };

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

  return (
    <div className="space-y-6 max-w-5xl">
      <SettingsHeader
        title="Agent Configuration"
        description="Configure multi-agent teams, view executions, and browse the memory system"
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="teams">
            <Users className="h-4 w-4 mr-1.5" />
            Teams
          </TabsTrigger>
          <TabsTrigger value="standalone">
            <Bot className="h-4 w-4 mr-1.5" />
            Standalone
          </TabsTrigger>
          <TabsTrigger value="memory">
            <Brain className="h-4 w-4 mr-1.5" />
            Memory
          </TabsTrigger>
          <TabsTrigger value="prompts">
            <FileText className="h-4 w-4 mr-1.5" />
            Prompts
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
              <span className="text-sm text-muted-foreground">
                {filteredTeams.length} {filteredTeams.length === 1 ? 'team' : 'teams'}
              </span>
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
            <Card>
              <CardContent className="py-16 text-center space-y-4">
                <Users className="w-12 h-12 mx-auto text-muted-foreground" />
                <div className="space-y-1">
                  <p className="font-medium text-lg">No agent teams yet</p>
                  <p className="text-sm text-muted-foreground max-w-md mx-auto">
                    Create a team of specialized AI agents that work together to
                    research, analyze, and synthesize information from your notebook
                    sources.
                  </p>
                </div>
                <Button onClick={() => setShowCreate(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  Create Your First Team
                </Button>
              </CardContent>
            </Card>
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
                <Button onClick={() => setSearchQuery("")} variant="outline">
                  Clear Search
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredTeams.map((team: AgentTeam) => (
                <TeamCard
                  key={team.id}
                  team={team}
                  onDelete={setDeleteTeam}
                  onEdit={(team) => {
                    setEditingTeam(team);
                    setShowCreate(true);
                  }}
                  onExecute={handleExecute}
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
                Select a team and switch to the Execute tab to run queries.
                The query analyzer automatically routes queries based on complexity.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Standalone Tab */}
        <TabsContent value="standalone">
          <Card>
            <CardContent className="py-8 text-center text-sm text-gray-500">
              Standalone agents are managed in a separate section.
            </CardContent>
          </Card>
        </TabsContent>

        {/* Memory Tab */}
        <TabsContent value="memory">
          <MemoryBrowser />
        </TabsContent>

        {/* Prompts Tab */}
        <TabsContent value="prompts">
          <PromptsManager />
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
  );
}
