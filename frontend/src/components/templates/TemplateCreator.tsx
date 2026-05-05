"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Plus, X, Loader2, Info } from "lucide-react";
import { workspacesApi } from "@/lib/api/workspaces";
import { templatesApi, type TemplateParameter } from "@/lib/api/templates";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface TemplateCreatorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialWorkspaceId?: string;
}

const parameterTypes = [
  { value: "string", label: "Text" },
  { value: "number", label: "Number" },
  { value: "date", label: "Date" },
  { value: "boolean", label: "Boolean" },
  { value: "select", label: "Select (Dropdown)" },
];

const categories = [
  { value: "data_pipeline", label: "Data Pipeline" },
  { value: "research", label: "Research" },
  { value: "reporting", label: "Reporting" },
  { value: "monitoring", label: "Monitoring" },
  { value: "analysis", label: "Analysis" },
  { value: "automation", label: "Automation" },
  { value: "other", label: "Other" },
];

export function TemplateCreator({ open, onOpenChange, initialWorkspaceId }: TemplateCreatorProps) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState(1);

  // Form state
  const [workspaceId, setWorkspaceId] = useState(initialWorkspaceId || "");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<string>("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [parameters, setParameters] = useState<TemplateParameter[]>([]);

  // Fetch workspaces with plans only
  const { data: workspaces, isLoading: isLoadingWorkspaces, error: workspacesError } = useQuery({
    queryKey: ["workspaces", "with-plans"],
    queryFn: () => workspacesApi.listWithPlans(),
  });

  // Debug logging
  console.log("Workspaces with plans:", workspaces);
  console.log("Loading:", isLoadingWorkspaces);
  console.log("Error:", workspacesError);

  // Create mutation
  const createMutation = useMutation({
    mutationFn: templatesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      toast.success("Template created successfully!");
      handleClose();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to create template");
    },
  });

  const handleClose = () => {
    setStep(1);
    setWorkspaceId(initialWorkspaceId || "");
    setName("");
    setDescription("");
    setCategory("");
    setTags([]);
    setTagInput("");
    setIsPublic(false);
    setParameters([]);
    onOpenChange(false);
  };

  const handleAddTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()]);
      setTagInput("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  const handleAddParameter = () => {
    setParameters([
      ...parameters,
      {
        name: "",
        type: "string",
        description: "",
        required: false,
      },
    ]);
  };

  const handleUpdateParameter = (index: number, updates: Partial<TemplateParameter>) => {
    const newParams = [...parameters];
    newParams[index] = { ...newParams[index], ...updates };
    setParameters(newParams);
  };

  const handleRemoveParameter = (index: number) => {
    setParameters(parameters.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    createMutation.mutate({
      workspace_id: workspaceId,
      name,
      description: description || undefined,
      category: category || undefined,
      parameters: parameters.length > 0 ? parameters : undefined,
      is_public: isPublic,
      tags: tags.length > 0 ? tags : undefined,
    });
  };

  const canProceedStep1 = workspaceId !== "";
  const canProceedStep2 = name.trim() !== "";
  const canSubmit = parameters.every((p) => p.name.trim() !== "");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Workspace Template</DialogTitle>
          <DialogDescription>
            Step {step} of 3: {step === 1 ? "Select Workspace" : step === 2 ? "Template Details" : "Parameters"}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Step 1: Workspace Selection */}
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <Label htmlFor="workspace">Select Workspace *</Label>
                <Select value={workspaceId} onValueChange={setWorkspaceId} disabled={isLoadingWorkspaces}>
                  <SelectTrigger id="workspace" className="mt-1.5">
                    <SelectValue placeholder={isLoadingWorkspaces ? "Loading workspaces..." : "Choose a workspace with a plan"} />
                  </SelectTrigger>
                  <SelectContent>
                    {workspaces && workspaces.length > 0 ? (
                      workspaces.map((workspace) => (
                        <SelectItem key={workspace.id} value={workspace.id}>
                          {workspace.name}
                        </SelectItem>
                      ))
                    ) : (
                      <div className="px-2 py-6 text-center text-sm text-muted-foreground">
                        No workspaces with plans found.<br />
                        Create a workspace using the Guided Setup to enable template creation.
                      </div>
                    )}
                  </SelectContent>
                </Select>
                <p className="text-sm text-muted-foreground mt-1.5">
                  Only workspaces with execution plans can be converted to templates
                </p>
                {workspaces && workspaces.length === 0 && !isLoadingWorkspaces && (
                  <p className="text-sm text-amber-600 dark:text-amber-400 mt-2">
                    ⚠️ No eligible workspaces found. Use "Guided Setup (AI-Powered)" when creating a workspace to enable template creation.
                  </p>
                )}
              </div>

              <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <div className="flex gap-2">
                  <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-900 dark:text-blue-100">
                    <p className="font-medium mb-1">What gets included?</p>
                    <ul className="list-disc list-inside space-y-1 text-blue-800 dark:text-blue-200">
                      <li>Phases and tasks structure</li>
                      <li>Agent assignments and collaboration patterns</li>
                      <li>Resource requirements</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Template Details */}
          {step === 2 && (
            <div className="space-y-4">
              <div>
                <Label htmlFor="name">Template Name *</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g., Daily Sales Analysis"
                  className="mt-1.5"
                />
              </div>

              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Describe what this template does..."
                  rows={3}
                  className="mt-1.5"
                />
              </div>

              <div>
                <Label htmlFor="category">Category</Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger id="category" className="mt-1.5">
                    <SelectValue placeholder="Select a category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((cat) => (
                      <SelectItem key={cat.value} value={cat.value}>
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="tags">Tags</Label>
                <div className="flex gap-2 mt-1.5">
                  <Input
                    id="tags"
                    value={tagInput}
                    onChange={(e) => setTagInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleAddTag())}
                    placeholder="Add tags..."
                  />
                  <Button type="button" onClick={handleAddTag} variant="outline">
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                {tags.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {tags.map((tag) => (
                      <Badge key={tag} variant="secondary" className="gap-1">
                        {tag}
                        <button onClick={() => handleRemoveTag(tag)} className="hover:text-destructive">
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox id="public" checked={isPublic} onCheckedChange={(checked) => setIsPublic(checked === true)} />
                <Label htmlFor="public" className="text-sm font-normal cursor-pointer">
                  Make this template public (visible to all users)
                </Label>
              </div>
            </div>
          )}

          {/* Step 3: Parameters */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium">Template Parameters</h3>
                  <p className="text-sm text-muted-foreground">Define variables that can be customized on execution</p>
                </div>
                <Button type="button" onClick={handleAddParameter} size="sm" variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Parameter
                </Button>
              </div>

              {parameters.length === 0 ? (
                <div className="text-center py-8 border-2 border-dashed rounded-lg">
                  <p className="text-sm text-muted-foreground">No parameters defined</p>
                  <p className="text-xs text-muted-foreground mt-1">Click "Add Parameter" to create one</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {parameters.map((param, index) => (
                    <div key={index} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-start justify-between">
                        <h4 className="font-medium text-sm">Parameter {index + 1}</h4>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveParameter(index)}
                          className="h-8 w-8 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs">Name *</Label>
                          <Input
                            value={param.name}
                            onChange={(e) => handleUpdateParameter(index, { name: e.target.value })}
                            placeholder="e.g., target_date"
                            className="mt-1"
                          />
                        </div>
                        <div>
                          <Label className="text-xs">Type</Label>
                          <Select
                            value={param.type}
                            onValueChange={(value: any) => handleUpdateParameter(index, { type: value })}
                          >
                            <SelectTrigger className="mt-1">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {parameterTypes.map((type) => (
                                <SelectItem key={type.value} value={type.value}>
                                  {type.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div>
                        <Label className="text-xs">Description</Label>
                        <Input
                          value={param.description}
                          onChange={(e) => handleUpdateParameter(index, { description: e.target.value })}
                          placeholder="Describe this parameter..."
                          className="mt-1"
                        />
                      </div>

                      {param.type === "select" && (
                        <div>
                          <Label className="text-xs">Options (comma-separated)</Label>
                          <Input
                            value={param.options?.join(", ") || ""}
                            onChange={(e) =>
                              handleUpdateParameter(index, {
                                options: e.target.value.split(",").map((o) => o.trim()),
                              })
                            }
                            placeholder="Option1, Option2, Option3"
                            className="mt-1"
                          />
                        </div>
                      )}

                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id={`required-${index}`}
                          checked={param.required}
                          onCheckedChange={(checked) => handleUpdateParameter(index, { required: checked === true })}
                        />
                        <Label htmlFor={`required-${index}`} className="text-sm font-normal cursor-pointer">
                          Required parameter
                        </Label>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <div className="flex gap-2">
                  <Info className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-amber-900 dark:text-amber-100">
                    <p className="font-medium mb-1">Using Parameters</p>
                    <p className="text-amber-800 dark:text-amber-200">
                      Use <code className="bg-amber-100 dark:bg-amber-900 px-1 rounded">{"{{parameter_name}}"}</code> in
                      task descriptions to reference parameter values.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex justify-between sm:justify-between">
          <div>
            {step > 1 && (
              <Button type="button" variant="outline" onClick={() => setStep(step - 1)}>
                Back
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" onClick={handleClose}>
              Cancel
            </Button>
            {step < 3 ? (
              <Button
                type="button"
                onClick={() => setStep(step + 1)}
                disabled={step === 1 ? !canProceedStep1 : !canProceedStep2}
              >
                Next
              </Button>
            ) : (
              <Button type="button" onClick={handleSubmit} disabled={!canSubmit || createMutation.isPending}>
                {createMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Create Template"
                )}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
