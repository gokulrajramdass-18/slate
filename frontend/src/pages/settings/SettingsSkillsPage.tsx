import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import {
  Search,
  Plus,
  Code,
  Database,
  Brain,
  FileText,
  Users,
  BookOpen,
  MessageSquare,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Settings as SettingsIcon,
  Trash2,
  Edit,
  Zap,
} from "lucide-react";
import { agentSkillsApi } from "@/lib/api/agent-skills";

// Skill category icons mapping
const categoryIcons = {
  search: Search,
  data_query: Database,
  analysis: Brain,
  synthesis: FileText,
  coordination: Users,
  memory: BookOpen,
  tools: Code,
  communication: MessageSquare,
  validation: CheckCircle2,
  transformation: AlertCircle,
};

// Skill category colors
const categoryColors = {
  search: "bg-blue-500",
  data_query: "bg-purple-500",
  analysis: "bg-green-500",
  synthesis: "bg-yellow-500",
  coordination: "bg-pink-500",
  memory: "bg-indigo-500",
  tools: "bg-orange-500",
  communication: "bg-cyan-500",
  validation: "bg-emerald-500",
  transformation: "bg-red-500",
};

export default function SettingsSkillsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [selectedSkill, setSelectedSkill] = useState<any>(null);
  const [bindDialogOpen, setBindDialogOpen] = useState(false);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [bindTarget, setBindTarget] = useState<"agent" | "role" | "team">("role");
  const [bindConfig, setBindConfig] = useState("{}");

  // Fetch all skills
  const { data: skills, isLoading } = useQuery({
    queryKey: ["agent-skills", categoryFilter],
    queryFn: () =>
      agentSkillsApi.listSkills(
        categoryFilter !== "all" ? categoryFilter : undefined
      ),
  });

  // Filter skills by search query
  const filteredSkills = skills?.filter((skill: any) =>
    skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    skill.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
    skill.tags.some((tag: string) =>
      tag.toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  // Group skills by category
  const skillsByCategory = filteredSkills?.reduce((acc: any, skill: any) => {
    if (!acc[skill.category]) {
      acc[skill.category] = [];
    }
    acc[skill.category].push(skill);
    return acc;
  }, {});

  const handleBindSkill = (skill: any) => {
    setSelectedSkill(skill);
    setBindDialogOpen(true);
  };

  const handleViewDetails = (skill: any) => {
    setSelectedSkill(skill);
    // Could open a details dialog
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agent Skills</h1>
          <p className="text-muted-foreground mt-2">
            Manage reusable capabilities that can be equipped to agents and teams.
          </p>
        </div>
        <Button
          onClick={() => setCreateDialogOpen(true)}
          size="lg"
        >
          <Plus className="h-4 w-4 mr-2" />
          Create Skill
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Skills</CardTitle>
            <Code className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{skills?.length || 0}</div>
            <p className="text-xs text-muted-foreground">Available skills</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Categories</CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {skillsByCategory ? Object.keys(skillsByCategory).length : 0}
            </div>
            <p className="text-xs text-muted-foreground">Skill categories</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Built-in</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {skills?.filter((s: any) => !s.author).length || 0}
            </div>
            <p className="text-xs text-muted-foreground">System skills</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Custom</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {skills?.filter((s: any) => s.author).length || 0}
            </div>
            <p className="text-xs text-muted-foreground">User-created</p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search skills by name, description, or tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full"
              />
            </div>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                <SelectItem value="all">All categories</SelectItem>
                <SelectItem value="search">Search</SelectItem>
                <SelectItem value="data_query">Data Query</SelectItem>
                <SelectItem value="analysis">Analysis</SelectItem>
                <SelectItem value="synthesis">Synthesis</SelectItem>
                <SelectItem value="coordination">Coordination</SelectItem>
                <SelectItem value="memory">Memory</SelectItem>
                <SelectItem value="tools">Tools</SelectItem>
                <SelectItem value="communication">Communication</SelectItem>
                <SelectItem value="validation">Validation</SelectItem>
                <SelectItem value="transformation">Transformation</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Skills List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : !skillsByCategory || Object.keys(skillsByCategory).length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Code className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium">No skills found</p>
            <p className="text-sm text-muted-foreground">
              {searchQuery
                ? "Try adjusting your search filters"
                : "No skills are currently registered"}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {Object.entries(skillsByCategory).map(([category, categorySkills]: [string, any]) => {
            const Icon = categoryIcons[category as keyof typeof categoryIcons] || Code;
            const colorClass = categoryColors[category as keyof typeof categoryColors] || "bg-gray-500";

            return (
              <div key={category}>
                <div className="flex items-center gap-2 mb-4">
                  <div className={`p-2 rounded-lg ${colorClass} text-white`}>
                    <Icon className="h-5 w-5" />
                  </div>
                  <h2 className="text-xl font-semibold capitalize">
                    {category.replace("_", " ")}
                  </h2>
                  <Badge variant="secondary">{categorySkills.length}</Badge>
                </div>

                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {categorySkills.map((skill: any) => (
                    <SkillCard
                      key={skill.id}
                      skill={skill}
                      onBind={handleBindSkill}
                      onViewDetails={handleViewDetails}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bind Skill Dialog */}
      <BindSkillDialog
        open={bindDialogOpen}
        onOpenChange={setBindDialogOpen}
        skill={selectedSkill}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["agent-skills"] });
          toast({
            title: "Skill bound successfully",
            description: `${selectedSkill?.name} has been bound.`,
          });
        }}
      />

      {/* Create Skill Dialog */}
      <CreateSkillDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["agent-skills"] });
          toast({
            title: "Skill created successfully",
            description: "Your custom skill has been registered.",
          });
        }}
      />
    </div>
  );
}

// Skill Card Component
function SkillCard({ skill, onBind, onViewDetails }: any) {
  const Icon = categoryIcons[skill.category as keyof typeof categoryIcons] || Code;

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${categoryColors[skill.category as keyof typeof categoryColors]} text-white`}>
              <Icon className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base">{skill.name}</CardTitle>
              <Badge variant="outline" className="mt-1 text-xs">
                v{skill.version}
              </Badge>
            </div>
          </div>
        </div>
        <CardDescription className="line-clamp-2 mt-2">
          {skill.description}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Tags */}
          {skill.tags && skill.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {skill.tags.slice(0, 3).map((tag: string) => (
                <Badge key={tag} variant="secondary" className="text-xs">
                  {tag}
                </Badge>
              ))}
              {skill.tags.length > 3 && (
                <Badge variant="secondary" className="text-xs">
                  +{skill.tags.length - 3}
                </Badge>
              )}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => onBind(skill)}
              className="flex-1"
            >
              <Plus className="h-3 w-3 mr-1" />
              Bind
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => onViewDetails(skill)}
            >
              <SettingsIcon className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Bind Skill Dialog Component
function BindSkillDialog({ open, onOpenChange, skill, onSuccess }: any) {
  const { toast } = useToast();
  const [bindType, setBindType] = useState<"agent" | "role" | "team">("role");
  const [targetId, setTargetId] = useState("");
  const [config, setConfig] = useState("{}");

  const bindMutation = useMutation({
    mutationFn: async () => {
      const configObj = config ? JSON.parse(config) : undefined;

      if (bindType === "agent") {
        return agentSkillsApi.bindToAgent(targetId, skill.id, configObj);
      } else if (bindType === "role") {
        return agentSkillsApi.bindToRole(targetId, skill.id, configObj);
      } else {
        return agentSkillsApi.bindToTeam(targetId, skill.id, configObj);
      }
    },
    onSuccess: () => {
      onSuccess();
      onOpenChange(false);
      setTargetId("");
      setConfig("{}");
    },
    onError: (error: any) => {
      toast({
        title: "Error binding skill",
        description: error.message || "Failed to bind skill",
        variant: "destructive",
      });
    },
  });

  const handleBind = () => {
    if (!targetId) {
      toast({
        title: "Missing target",
        description: "Please provide a target ID",
        variant: "destructive",
      });
      return;
    }

    try {
      // Validate JSON config
      if (config) {
        JSON.parse(config);
      }
      bindMutation.mutate();
    } catch (error) {
      toast({
        title: "Invalid config",
        description: "Config must be valid JSON",
        variant: "destructive",
      });
    }
  };

  if (!skill) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Bind Skill: {skill.name}</DialogTitle>
          <DialogDescription>
            Attach this skill to agents, roles, or teams.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Bind Type */}
          <div className="space-y-2">
            <Label>Bind To</Label>
            <Select value={bindType} onValueChange={(v: any) => setBindType(v)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                <SelectItem value="role">Role (all agents with this role)</SelectItem>
                <SelectItem value="agent">Specific Agent</SelectItem>
                <SelectItem value="team">Team (all team members)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Target ID */}
          <div className="space-y-2">
            <Label>
              {bindType === "role" ? "Role Name" : bindType === "agent" ? "Agent ID" : "Team ID"}
            </Label>
            <Input
              placeholder={
                bindType === "role"
                  ? "e.g., researcher, analyst"
                  : bindType === "agent"
                  ? "Agent UUID"
                  : "Team UUID"
              }
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
            />
          </div>

          {/* Configuration */}
          <div className="space-y-2">
            <Label>Configuration (JSON)</Label>
            <Textarea
              placeholder='{"max_results": 10, "strategy": "hybrid"}'
              value={config}
              onChange={(e) => setConfig(e.target.value)}
              rows={5}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Optional: Override default configuration for this binding
            </p>
          </div>

          {/* Skill Info */}
          <div className="rounded-lg bg-muted p-4 space-y-2">
            <p className="text-sm font-medium">Skill Information</p>
            <div className="text-sm text-muted-foreground space-y-1">
              <p>• Category: {skill.category}</p>
              <p>• Version: {skill.version}</p>
              {skill.tags && skill.tags.length > 0 && (
                <p>• Tags: {skill.tags.join(", ")}</p>
              )}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleBind}
            disabled={bindMutation.isPending}
          >
            {bindMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Bind Skill
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Create Skill Dialog Component
function CreateSkillDialog({ open, onOpenChange, onSuccess }: any) {
  const { toast } = useToast();
  const [formData, setFormData] = useState({
    id: "",
    name: "",
    description: "",
    category: "analysis",
    version: "1.0.0",
    tags: "",
    handlerModule: "",
    handlerFunction: "",
    allowedRoles: "",
    configSchema: "{}",
    defaultConfig: "{}",
    timeoutSeconds: 30,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      // Parse JSON fields
      const tags = formData.tags ? formData.tags.split(",").map(t => t.trim()) : [];
      const allowedRoles = formData.allowedRoles ? formData.allowedRoles.split(",").map(r => r.trim()) : [];
      const configSchema = formData.configSchema ? JSON.parse(formData.configSchema) : null;
      const defaultConfig = formData.defaultConfig ? JSON.parse(formData.defaultConfig) : {};

      const payload = {
        id: formData.id,
        name: formData.name,
        description: formData.description,
        category: formData.category,
        version: formData.version,
        tags,
        handler_module: formData.handlerModule,
        handler_function: formData.handlerFunction,
        allowed_roles: allowedRoles,
        config_schema: configSchema,
        default_config: defaultConfig,
        timeout_seconds: formData.timeoutSeconds,
      };

      return agentSkillsApi.createSkill(payload);
    },
    onSuccess: () => {
      onSuccess();
      onOpenChange(false);
      setFormData({
        id: "",
        name: "",
        description: "",
        category: "analysis",
        version: "1.0.0",
        tags: "",
        handlerModule: "",
        handlerFunction: "",
        allowedRoles: "",
        configSchema: "{}",
        defaultConfig: "{}",
        timeoutSeconds: 30,
      });
    },
    onError: (error: any) => {
      toast({
        title: "Error creating skill",
        description: error.message || "Failed to create skill",
        variant: "destructive",
      });
    },
  });

  const handleCreate = () => {
    // Validation
    if (!formData.id || !formData.name || !formData.description) {
      toast({
        title: "Missing required fields",
        description: "ID, name, and description are required",
        variant: "destructive",
      });
      return;
    }

    if (!formData.handlerModule || !formData.handlerFunction) {
      toast({
        title: "Missing handler",
        description: "Handler module and function are required",
        variant: "destructive",
      });
      return;
    }

    try {
      // Validate JSON
      if (formData.configSchema) JSON.parse(formData.configSchema);
      if (formData.defaultConfig) JSON.parse(formData.defaultConfig);
      createMutation.mutate();
    } catch (error) {
      toast({
        title: "Invalid JSON",
        description: "Config schema and default config must be valid JSON",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Create Custom Skill
          </DialogTitle>
          <DialogDescription>
            Register a new custom skill that can be used by agents and teams.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Basic Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Skill ID *</Label>
              <Input
                placeholder="e.g., my_custom_skill"
                value={formData.id}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Unique identifier (lowercase, underscores)
              </p>
            </div>

            <div className="space-y-2">
              <Label>Version</Label>
              <Input
                placeholder="1.0.0"
                value={formData.version}
                onChange={(e) => setFormData({ ...formData, version: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Name *</Label>
            <Input
              placeholder="My Custom Skill"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label>Description *</Label>
            <Textarea
              placeholder="What does this skill do?"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
            />
          </div>

          {/* Category & Tags */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Category</Label>
              <Select
                value={formData.category}
                onValueChange={(v) => setFormData({ ...formData, category: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                  <SelectItem value="search">Search</SelectItem>
                  <SelectItem value="data_query">Data Query</SelectItem>
                  <SelectItem value="analysis">Analysis</SelectItem>
                  <SelectItem value="synthesis">Synthesis</SelectItem>
                  <SelectItem value="coordination">Coordination</SelectItem>
                  <SelectItem value="memory">Memory</SelectItem>
                  <SelectItem value="tools">Tools</SelectItem>
                  <SelectItem value="communication">Communication</SelectItem>
                  <SelectItem value="validation">Validation</SelectItem>
                  <SelectItem value="transformation">Transformation</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Tags</Label>
              <Input
                placeholder="search, retrieval, rag"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">Comma-separated</p>
            </div>
          </div>

          {/* Handler */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Handler Module *</Label>
              <Input
                placeholder="open_notebook.agents.skills.builtin.my_skill"
                value={formData.handlerModule}
                onChange={(e) => setFormData({ ...formData, handlerModule: e.target.value })}
                className="font-mono text-sm"
              />
            </div>

            <div className="space-y-2">
              <Label>Handler Function *</Label>
              <Input
                placeholder="my_skill_handler"
                value={formData.handlerFunction}
                onChange={(e) => setFormData({ ...formData, handlerFunction: e.target.value })}
                className="font-mono text-sm"
              />
            </div>
          </div>

          {/* Access Control */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Allowed Roles</Label>
              <Input
                placeholder="researcher, analyst, writer"
                value={formData.allowedRoles}
                onChange={(e) => setFormData({ ...formData, allowedRoles: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Leave empty to allow all roles
              </p>
            </div>

            <div className="space-y-2">
              <Label>Timeout (seconds)</Label>
              <Input
                type="number"
                value={formData.timeoutSeconds}
                onChange={(e) => setFormData({ ...formData, timeoutSeconds: parseInt(e.target.value) || 30 })}
              />
            </div>
          </div>

          {/* Configuration Schema */}
          <div className="space-y-2">
            <Label>Config Schema (JSON)</Label>
            <Textarea
              placeholder='{"type": "object", "properties": {"limit": {"type": "integer", "default": 10}}}'
              value={formData.configSchema}
              onChange={(e) => setFormData({ ...formData, configSchema: e.target.value })}
              rows={4}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              JSON schema for skill configuration parameters
            </p>
          </div>

          {/* Default Config */}
          <div className="space-y-2">
            <Label>Default Config (JSON)</Label>
            <Textarea
              placeholder='{"limit": 10, "strategy": "hybrid"}'
              value={formData.defaultConfig}
              onChange={(e) => setFormData({ ...formData, defaultConfig: e.target.value })}
              rows={3}
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Default configuration values
            </p>
          </div>

          {/* Help Text */}
          <div className="rounded-lg bg-blue-50 dark:bg-blue-950 p-4 space-y-2">
            <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
              💡 Creating a Custom Skill
            </p>
            <ul className="text-sm text-blue-700 dark:text-blue-300 space-y-1 list-disc list-inside">
              <li>The handler function must exist in your Python codebase</li>
              <li>Handler signature: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">async def handler(context: SkillContext) -&gt; Any</code></li>
              <li>See implementation guide for examples</li>
            </ul>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleCreate}
            disabled={createMutation.isPending}
          >
            {createMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Skill
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
