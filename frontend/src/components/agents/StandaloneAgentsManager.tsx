/**
 * Standalone Agents Manager Component
 *
 * Manages individual agents with their own tools, MCP servers, and data sources
 */

"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-client";
import * as standaloneAgentsApi from "@/lib/api/standalone-agents";
import { toolsApi } from "@/lib/api/tools";
import { sourcesApi } from "@/lib/api/sources";
import { agentSkillsApi, type Skill } from "@/lib/api/agent-skills";
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
import { Bot, Plus, Trash2, Loader2, Activity, Brain, Search as SearchIcon, FileText, Zap, Pencil, Users, Database, Play, CheckCircle2, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";

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

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    role: "planner" as AgentRole | "custom",
    system_prompt: "",
    model_name: "",
    tool_ids: [] as string[],
    mcp_server_ids: [] as string[],
    data_source_ids: [] as string[],
    skill_ids: [] as string[],
  });

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

  const { data: skillsData, isLoading: skillsLoading, error: skillsError } = useQuery({
    queryKey: ["agent-skills"],
    queryFn: () => agentSkillsApi.listSkills(),
  });

  const agents = agentsData?.agents || [];
  const tools = toolsData || [];
  const sources = sourcesData || [];
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
      system_prompt: "",
      model_name: "",
      tool_ids: [],
      mcp_server_ids: [],
      data_source_ids: [],
      skill_ids: [],
    });
    setEditingAgentId(null);
  };

  const handleCreate = () => {
    if (!formData.name.trim()) {
      toast.error("Agent name is required");
      return;
    }

    const agentData: StandaloneAgentCreate = {
      name: formData.name,
      description: formData.description || undefined,
      role: formData.role,
      system_prompt: formData.system_prompt || undefined,
      model_name: formData.model_name || undefined,
      tool_ids: formData.tool_ids,
      mcp_server_ids: formData.mcp_server_ids,
      data_source_ids: formData.data_source_ids,
      skill_ids: formData.skill_ids,
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
            const execStats = executionCounts[agent.id] || { total: 0, completed: 0, failed: 0, running: 0 };

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
                      {roleConfig.label}
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
                        setFormData({
                          name: agent.name,
                          role: agent.role as AgentRole | "custom",
                          description: agent.description || "",
                          system_prompt: agent.system_prompt || "",
                          model_name: agent.model_name || "",
                          tool_ids: agent.tool_ids || [],
                          data_source_ids: agent.data_source_ids || [],
                          mcp_server_ids: agent.mcp_server_ids || [],
                          skill_ids: agent.skill_ids || [],
                        });
                        setEditingAgentId(agent.id);
                        setShowCreateDialog(true);
                      }}
                    >
                      <Pencil className="w-3.5 h-3.5" />
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
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingAgentId ? "Edit Agent" : "Create Standalone Agent"}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            {/* Basic Info */}
            <div className="space-y-2">
              <Label htmlFor="name">Agent Name *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="My Research Agent"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="What does this agent do?"
                rows={2}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Select value={formData.role} onValueChange={(value: any) => setFormData({ ...formData, role: value })}>
                <SelectTrigger>
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

            {/* Advanced Config */}
            <div className="space-y-2">
              <Label htmlFor="system_prompt">System Prompt (Optional)</Label>
              <Textarea
                id="system_prompt"
                value={formData.system_prompt}
                onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                placeholder="Custom instructions for this agent..."
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="model_name">Model Override (Optional)</Label>
              <Input
                id="model_name"
                value={formData.model_name}
                onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                placeholder="e.g., gpt-4, claude-3-opus-20240229"
              />
            </div>

            {/* Tools */}
            <div className="space-y-2">
              <Label>Tools ({formData.tool_ids.length} selected)</Label>
              <div className="border rounded p-3 max-h-32 overflow-y-auto space-y-1">
                {tools.map((tool: any) => (
                  <label key={tool.id} className="flex items-center gap-2 cursor-pointer hover:bg-muted p-1 rounded">
                    <input
                      type="checkbox"
                      checked={formData.tool_ids.includes(tool.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({ ...formData, tool_ids: [...formData.tool_ids, tool.id] });
                        } else {
                          setFormData({ ...formData, tool_ids: formData.tool_ids.filter(id => id !== tool.id) });
                        }
                      }}
                    />
                    <span className="text-sm">{tool.name}</span>
                  </label>
                ))}
                {tools.length === 0 && (
                  <p className="text-sm text-muted-foreground">No tools available</p>
                )}
              </div>
            </div>

            {/* Data Sources */}
            <div className="space-y-2">
              <Label>Data Sources ({formData.data_source_ids.length} selected)</Label>
              <div className="border rounded p-3 max-h-32 overflow-y-auto space-y-1">
                {sources.map((source: any) => (
                  <label key={source.id} className="flex items-center gap-2 cursor-pointer hover:bg-muted p-1 rounded">
                    <input
                      type="checkbox"
                      checked={formData.data_source_ids.includes(source.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({ ...formData, data_source_ids: [...formData.data_source_ids, source.id] });
                        } else {
                          setFormData({ ...formData, data_source_ids: formData.data_source_ids.filter(id => id !== source.id) });
                        }
                      }}
                    />
                    <span className="text-sm">{source.title}</span>
                    <Badge variant="outline" className="text-xs">{source.source_type}</Badge>
                  </label>
                ))}
                {sources.length === 0 && (
                  <p className="text-sm text-muted-foreground">No sources available</p>
                )}
              </div>
            </div>

            {/* Skills */}
            <div className="space-y-2">
              <Label>Skills ({formData.skill_ids.length} selected)</Label>
              <div className="border rounded p-3 max-h-32 overflow-y-auto space-y-1">
                {skillsLoading ? (
                  <p className="text-sm text-muted-foreground">Loading skills...</p>
                ) : skillsError ? (
                  <p className="text-sm text-red-600">Error loading skills</p>
                ) : skills.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No skills available</p>
                ) : (
                  skills.map((skill: Skill) => (
                  <label key={skill.id} className="flex items-center gap-2 cursor-pointer hover:bg-muted p-1 rounded">
                    <input
                      type="checkbox"
                      checked={formData.skill_ids.includes(skill.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({ ...formData, skill_ids: [...formData.skill_ids, skill.id] });
                        } else {
                          setFormData({ ...formData, skill_ids: formData.skill_ids.filter(id => id !== skill.id) });
                        }
                      }}
                    />
                    <span className="text-sm">{skill.name}</span>
                    <Badge variant="outline" className="text-xs">{skill.category}</Badge>
                  </label>
                  ))
                )}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowCreateDialog(false);
              resetForm();
            }}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending || updateMutation.isPending}>
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
