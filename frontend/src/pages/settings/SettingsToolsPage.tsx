import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toolsApi } from "@/lib/api/tools";
import { queryKeys } from "@/lib/query-client";
import type {
  Tool,
  ToolCreate,
  ToolPermission,
  PermissionCreate,
} from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { Plus, Search, Shield, Settings2, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { SettingsHeader } from "@/components/settings/settings-header";

// ---------------------------------------------------------------------------
// Category helpers
// ---------------------------------------------------------------------------

const CATEGORIES = [
  { value: "all", label: "All Categories" },
  { value: "data_query", label: "Data Query" },
  { value: "web", label: "Web" },
  { value: "computation", label: "Computation" },
  { value: "file_analysis", label: "File Analysis" },
];

const TOOL_TYPES = [
  { value: "hana_query", label: "HANA Query" },
  { value: "api_call", label: "API Call" },
  { value: "web_search", label: "Web Search" },
  { value: "code_exec", label: "Code Execution" },
  { value: "file_analysis", label: "File Analysis" },
  { value: "custom", label: "Custom" },
];

function categoryLabel(cat?: string) {
  return CATEGORIES.find((c) => c.value === cat)?.label ?? cat ?? "Uncategorized";
}

// ---------------------------------------------------------------------------
// PermissionMatrix component
// ---------------------------------------------------------------------------

function PermissionMatrix({
  tool,
  onClose,
}: {
  tool: Tool;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [newRole, setNewRole] = useState("");
  const [newUserId, setNewUserId] = useState("");
  const [newRateLimit, setNewRateLimit] = useState("");

  const { data: permissions = [], isLoading } = useQuery({
    queryKey: queryKeys.toolPermissions(tool.id),
    queryFn: () => toolsApi.listPermissions(tool.id),
  });

  const addMutation = useMutation({
    mutationFn: (perm: PermissionCreate) =>
      toolsApi.addPermission(tool.id, perm),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.toolPermissions(tool.id),
      });
      setNewRole("");
      setNewUserId("");
      setNewRateLimit("");
      toast.success("Permission added");
    },
    onError: () => toast.error("Failed to add permission"),
  });

  const updateMutation = useMutation({
    mutationFn: ({
      permId,
      update,
    }: {
      permId: string;
      update: { allowed?: boolean; rate_limit?: number };
    }) => toolsApi.updatePermission(permId, update),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.toolPermissions(tool.id),
      });
    },
    onError: () => toast.error("Failed to update permission"),
  });

  const deleteMutation = useMutation({
    mutationFn: (permId: string) => toolsApi.deletePermission(permId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.toolPermissions(tool.id),
      });
      toast.success("Permission removed");
    },
    onError: () => toast.error("Failed to remove permission"),
  });

  const handleAdd = () => {
    if (!newRole && !newUserId) {
      toast.error("Specify either a role or user ID");
      return;
    }
    addMutation.mutate({
      role: newRole || undefined,
      user_id: newUserId || undefined,
      allowed: true,
      rate_limit: newRateLimit ? parseInt(newRateLimit, 10) : undefined,
    });
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="w-5 h-5" />
            Permissions for {tool.name}
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <p className="text-sm text-muted-foreground py-4">Loading...</p>
        ) : (
          <div className="space-y-4">
            {/* Existing permissions table */}
            {permissions.length > 0 ? (
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left px-4 py-2 font-medium">
                        User / Role
                      </th>
                      <th className="text-left px-4 py-2 font-medium">
                        Access
                      </th>
                      <th className="text-left px-4 py-2 font-medium">
                        Rate Limit
                      </th>
                      <th className="px-4 py-2 w-10" />
                    </tr>
                  </thead>
                  <tbody>
                    {permissions.map((perm: ToolPermission) => (
                      <tr key={perm.id} className="border-t">
                        <td className="px-4 py-2">
                          {perm.user_id ? (
                            <span className="font-mono text-xs">
                              {perm.user_id}
                            </span>
                          ) : (
                            <Badge variant="secondary">{perm.role}</Badge>
                          )}
                        </td>
                        <td className="px-4 py-2">
                          <Switch
                            checked={perm.allowed}
                            onCheckedChange={(allowed) =>
                              updateMutation.mutate({
                                permId: perm.id,
                                update: { allowed },
                              })
                            }
                          />
                        </td>
                        <td className="px-4 py-2">
                          <Input
                            type="number"
                            className="h-8 w-24"
                            placeholder="None"
                            value={perm.rate_limit ?? ""}
                            onChange={(e) => {
                              const val = e.target.value
                                ? parseInt(e.target.value, 10)
                                : undefined;
                              updateMutation.mutate({
                                permId: perm.id,
                                update: { rate_limit: val },
                              });
                            }}
                          />
                        </td>
                        <td className="px-4 py-2">
                          <Button
                            size="icon"
                            variant="ghost"
                            onClick={() => deleteMutation.mutate(perm.id)}
                          >
                            <Trash2 className="w-4 h-4 text-destructive" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No custom permissions. Tool is allowed for all users by default.
              </p>
            )}

            {/* Add new permission */}
            <div className="border rounded-lg p-4 space-y-3">
              <p className="text-sm font-medium">Add Permission</p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-xs">Role</Label>
                  <Input
                    placeholder="e.g. admin"
                    value={newRole}
                    onChange={(e) => {
                      setNewRole(e.target.value);
                      if (e.target.value) setNewUserId("");
                    }}
                  />
                </div>
                <div>
                  <Label className="text-xs">Or User ID</Label>
                  <Input
                    placeholder="user-uuid"
                    value={newUserId}
                    onChange={(e) => {
                      setNewUserId(e.target.value);
                      if (e.target.value) setNewRole("");
                    }}
                  />
                </div>
                <div>
                  <Label className="text-xs">Rate Limit (calls/min)</Label>
                  <Input
                    type="number"
                    placeholder="No limit"
                    value={newRateLimit}
                    onChange={(e) => setNewRateLimit(e.target.value)}
                  />
                </div>
              </div>
              <Button
                size="sm"
                onClick={handleAdd}
                disabled={addMutation.isPending}
              >
                <Plus className="w-4 h-4 mr-1" />
                Add
              </Button>
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Create / Edit Tool Dialog
// ---------------------------------------------------------------------------

function CreateToolDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [toolType, setToolType] = useState("custom");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");

  const createMutation = useMutation({
    mutationFn: (tool: ToolCreate) => toolsApi.create(tool),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
      toast.success("Tool created");
      onClose();
      setName("");
      setDescription("");
    },
    onError: () => toast.error("Failed to create tool"),
  });

  const handleSubmit = () => {
    if (!name || !description) {
      toast.error("Name and description are required");
      return;
    }
    createMutation.mutate({
      name,
      tool_type: toolType as any,
      category: category || undefined,
      description,
      enabled: true,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register New Tool</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Name</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. web_search"
            />
          </div>
          <div>
            <Label>Type</Label>
            <Select value={toolType} onValueChange={setToolType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                {TOOL_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Category</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger>
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                {CATEGORIES.filter((c) => c.value !== "all").map((c) => (
                  <SelectItem key={c.value} value={c.value}>
                    {c.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this tool do?"
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Main Tools Page
// ---------------------------------------------------------------------------

export default function SettingsToolsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [permsTool, setPermsTool] = useState<Tool | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTool, setDeleteTool] = useState<Tool | null>(null);

  const { data: tools = [], isLoading } = useQuery({
    queryKey: [
      ...queryKeys.tools,
      category !== "all" ? category : undefined,
    ],
    queryFn: () =>
      toolsApi.list(
        category !== "all" ? { category } : undefined
      ),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      toolsApi.toggle(id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
    },
    onError: () => toast.error("Failed to toggle tool"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => toolsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
      toast.success("Tool deleted");
      setDeleteTool(null);
    },
    onError: () => toast.error("Failed to delete tool"),
  });

  const filtered = tools.filter((t: Tool) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      t.name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <SettingsHeader
        title="Tool Catalog"
        description="Configure available tools for chat agents"
      />
      <Button onClick={() => setShowCreate(true)}>
        <Plus className="w-4 h-4 mr-2" />
        Register Tool
      </Button>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search tools..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
            {CATEGORIES.map((c) => (
              <SelectItem key={c.value} value={c.value}>
                {c.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tool Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-5 bg-muted rounded w-3/4" />
              </CardHeader>
              <CardContent>
                <div className="h-4 bg-muted rounded w-full mb-2" />
                <div className="h-4 bg-muted rounded w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            {tools.length === 0
              ? "No tools registered yet. Click \"Register Tool\" to add one."
              : "No tools match your search."}
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((tool: Tool) => (
            <Card key={tool.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-base">{tool.name}</CardTitle>
                    <div className="flex gap-1.5">
                      <Badge variant="outline" className="text-xs">
                        {tool.tool_type}
                      </Badge>
                      {tool.category && (
                        <Badge variant="secondary" className="text-xs">
                          {categoryLabel(tool.category)}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <Switch
                    checked={tool.enabled}
                    onCheckedChange={(enabled) =>
                      toggleMutation.mutate({ id: tool.id, enabled })
                    }
                  />
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
                  {tool.description}
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setPermsTool(tool)}
                  >
                    <Shield className="w-3.5 h-3.5 mr-1" />
                    Permissions
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setDeleteTool(tool)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Permission Matrix Dialog */}
      {permsTool && (
        <PermissionMatrix
          tool={permsTool}
          onClose={() => setPermsTool(null)}
        />
      )}

      {/* Create Tool Dialog */}
      <CreateToolDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
      />

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteTool}
        onOpenChange={() => setDeleteTool(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete tool?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove &quot;{deleteTool?.name}&quot; and
              all its permissions. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteTool && deleteMutation.mutate(deleteTool.id)}
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
