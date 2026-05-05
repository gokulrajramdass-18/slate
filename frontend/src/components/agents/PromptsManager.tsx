"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { promptsApi, type PromptTemplate, type PromptTemplateUpdate } from "@/lib/api/agent-prompts";
import { queryKeys } from "@/lib/query-client";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2, FileText, Bot, Settings, Library, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { PromptEditor } from "./PromptEditor";
import { SavedQueryPromptsManager } from "./SavedQueryPromptsManager";

export function PromptsManager() {
  const queryClient = useQueryClient();
  const [selectedRole, setSelectedRole] = useState<string>("");
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newRole, setNewRole] = useState("");
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newTemplate, setNewTemplate] = useState("");

  const { data: templates, isLoading } = useQuery({
    queryKey: queryKeys.promptTemplates,
    queryFn: promptsApi.list,
  });

  const selectedTemplate = templates?.find((t) => t.role === selectedRole);

  // Auto-select first template when data loads
  if (templates && templates.length > 0 && !selectedRole) {
    setSelectedRole(templates[0].role);
  }

  const createMutation = useMutation({
    mutationFn: (data: PromptTemplateUpdate) => promptsApi.create(data),
    onSuccess: (newTemplate) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptTemplates });
      setSelectedRole(newTemplate.role);
      setShowCreateDialog(false);
      // Reset form
      setNewRole("");
      setNewName("");
      setNewDescription("");
      setNewTemplate("");
      toast.success("Agent role created successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to create agent role");
    },
  });

  const handleCreate = () => {
    if (!newRole.trim()) {
      toast.error("Role name is required");
      return;
    }
    if (!newTemplate.trim()) {
      toast.error("System prompt is required");
      return;
    }

    createMutation.mutate({
      role: newRole.trim().toLowerCase().replace(/\s+/g, "_"),
      name: newName.trim() || newRole.trim(),
      description: newDescription.trim(),
      template: newTemplate.trim(),
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!templates || templates.length === 0) {
    return (
      <Card>
        <CardContent className="py-16 text-center space-y-4">
          <FileText className="w-12 h-12 mx-auto text-muted-foreground" />
          <div className="space-y-1">
            <p className="font-medium text-lg">No prompt templates</p>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Prompt templates will be available once the backend is configured.
              They define the system prompts used by each agent role.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Tabs defaultValue="agent-roles" className="space-y-6">
      <TabsList>
        <TabsTrigger value="agent-roles">
          <Bot className="h-4 w-4 mr-1.5" />
          Agent Roles
        </TabsTrigger>
        <TabsTrigger value="saved">
          <Library className="h-4 w-4 mr-1.5" />
          Saved Queries
        </TabsTrigger>
      </TabsList>

      {/* Agent Roles Tab */}
      <TabsContent value="agent-roles" className="space-y-6">
        {/* Role selector and Create button */}
        <div className="flex items-end gap-4">
          <div className="flex-1 space-y-2">
            <Label>Agent Role</Label>
            <Select value={selectedRole} onValueChange={setSelectedRole}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select a role..." />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                {templates.map((template) => (
                  <SelectItem key={template.role} value={template.role}>
                    <div className="flex items-center gap-2">
                      <span className="capitalize">{template.name || template.role}</span>
                      {!template.is_default && (
                        <span className="text-xs text-amber-600">(custom)</span>
                      )}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => setShowCreateDialog(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Create New Role
          </Button>
        </div>

        {/* Prompt editor */}
        {selectedTemplate && (
          <PromptEditor key={selectedTemplate.role} template={selectedTemplate} />
        )}

        {/* Info */}
        <Card className="border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30">
          <CardContent className="py-4 text-sm text-gray-600 dark:text-gray-400 space-y-2">
            <p className="font-medium text-gray-700 dark:text-gray-300">
              About Agent Role Prompts
            </p>
            <p>
              Each agent role has a system prompt that defines its behavior and capabilities.
              You can customize these prompts to fine-tune how agents operate. Reset to
              restore the built-in defaults.
            </p>
            <p>
              Variables like <code className="text-xs bg-gray-200 dark:bg-gray-800 px-1 py-0.5 rounded">{"{context}"}</code> and{" "}
              <code className="text-xs bg-gray-200 dark:bg-gray-800 px-1 py-0.5 rounded">{"{tools}"}</code>{" "}
              are automatically replaced at runtime.
            </p>
          </CardContent>
        </Card>
      </TabsContent>

      {/* Saved Queries Tab */}
      <TabsContent value="saved">
        <SavedQueryPromptsManager />
      </TabsContent>

      {/* Create New Role Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Create New Agent Role</DialogTitle>
            <DialogDescription>
              Define a custom agent role with its own system prompt. This role will be available when creating agent teams.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="role">Role Name*</Label>
              <Input
                id="role"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
                placeholder="e.g., data_scientist"
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground">
                Use lowercase with underscores (e.g., data_scientist, code_reviewer)
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Display Name</Label>
              <Input
                id="name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g., Data Scientist"
              />
              <p className="text-xs text-muted-foreground">
                Human-readable name shown in the UI
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="e.g., Analyzes data and generates insights"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template">System Prompt*</Label>
              <Textarea
                id="template"
                value={newTemplate}
                onChange={(e) => setNewTemplate(e.target.value)}
                placeholder="You are a data scientist AI assistant. Your role is to..."
                className="min-h-[200px] font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Define how this agent should behave. You can use variables like {"{context}"}, {"{tools}"}, etc.
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending}>
              {createMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Role"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Tabs>
  );
}

