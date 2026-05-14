"use client";

import { useState } from "react";
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query";
import { useRouter } from "@/lib/routing/navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Play, AlertCircle } from "lucide-react";
import { templatesApi, type TemplateParameter } from "@/lib/api/templates";
import { workspacesApi } from "@/lib/api/workspaces";
import { toast } from "sonner";

interface TemplateExecutionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  templateId: string;
  templateName: string;
  sourceWorkspaceId?: string;
  parameters: TemplateParameter[];
}

export function TemplateExecutionDialog({
  open,
  onOpenChange,
  templateId,
  templateName,
  sourceWorkspaceId,
  parameters,
}: TemplateExecutionDialogProps) {
  const router = useRouter();
  const queryClient = useQueryClient();

  // Initialize parameter values with defaults
  const [paramValues, setParamValues] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = {};
    parameters.forEach((param) => {
      initial[param.name] = param.default_value ?? "";
    });
    return initial;
  });
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Get source workspace name
  const { data: sourceWorkspace } = useQuery({
    queryKey: ["workspaces", sourceWorkspaceId],
    queryFn: () => sourceWorkspaceId ? workspacesApi.get(sourceWorkspaceId) : null,
    enabled: open && !!sourceWorkspaceId,
  });

  const executeMutation = useMutation({
    mutationFn: async () => {
      // Validate required parameters
      const errors: Record<string, string> = {};
      parameters.forEach((param) => {
        if (param.required && !paramValues[param.name]) {
          errors[param.name] = "This field is required";
        }
      });

      if (Object.keys(errors).length > 0) {
        setValidationErrors(errors);
        throw new Error("Please fill in all required fields");
      }

      // Close dialog immediately when execution starts
      onOpenChange(false);

      return templatesApi.execute(templateId, {
        parameters: paramValues,
        target_workspace_id: sourceWorkspaceId, // Always use source workspace
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["templates", templateId] });
      queryClient.invalidateQueries({ queryKey: ["workspaces", data.target_workspace_id] });
      toast.success(
        <div>
          <div className="font-semibold">Template executed successfully!</div>
          <div className="text-sm text-muted-foreground mt-1">
            Results saved to: Template Executions/{data.note_title}
          </div>
        </div>
      );

      // Navigate to workspace with folder expanded
      router.push(`/workspaces/${data.target_workspace_id}?folder=${data.folder_id}`);
    },
    onError: (error: any) => {
      toast.error(error.message || error.response?.data?.detail || "Failed to execute template");
    },
  });

  const handleParamChange = (paramName: string, value: any) => {
    setParamValues((prev) => ({ ...prev, [paramName]: value }));
    // Clear validation error when user starts typing
    if (validationErrors[paramName]) {
      setValidationErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[paramName];
        return newErrors;
      });
    }
  };

  const renderParameterInput = (param: TemplateParameter) => {
    const hasError = validationErrors[param.name];

    switch (param.type) {
      case "string":
        return (
          <div key={param.name} className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-destructive ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Input
              id={param.name}
              value={paramValues[param.name] || ""}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
              placeholder={param.default_value || `Enter ${param.name}`}
              className={hasError ? "border-destructive" : ""}
            />
            {hasError && (
              <p className="text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {hasError}
              </p>
            )}
          </div>
        );

      case "number":
        return (
          <div key={param.name} className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-destructive ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Input
              id={param.name}
              type="number"
              value={paramValues[param.name] || ""}
              onChange={(e) => handleParamChange(param.name, parseFloat(e.target.value))}
              placeholder={param.default_value?.toString() || `Enter ${param.name}`}
              className={hasError ? "border-destructive" : ""}
            />
            {hasError && (
              <p className="text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {hasError}
              </p>
            )}
          </div>
        );

      case "date":
        return (
          <div key={param.name} className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-destructive ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Input
              id={param.name}
              type="date"
              value={paramValues[param.name] || ""}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
              className={hasError ? "border-destructive" : ""}
            />
            {hasError && (
              <p className="text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {hasError}
              </p>
            )}
          </div>
        );

      case "boolean":
        return (
          <div key={param.name} className="flex items-center justify-between space-y-2">
            <div className="space-y-0.5">
              <Label htmlFor={param.name}>
                {param.name}
                {param.required && <span className="text-destructive ml-1">*</span>}
              </Label>
              {param.description && (
                <p className="text-sm text-muted-foreground">{param.description}</p>
              )}
            </div>
            <Switch
              id={param.name}
              checked={paramValues[param.name] || false}
              onCheckedChange={(checked) => handleParamChange(param.name, checked)}
            />
          </div>
        );

      case "select":
        return (
          <div key={param.name} className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-destructive ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Select
              value={paramValues[param.name] || ""}
              onValueChange={(value) => handleParamChange(param.name, value)}
            >
              <SelectTrigger className={hasError ? "border-destructive" : ""}>
                <SelectValue placeholder={`Select ${param.name}`} />
              </SelectTrigger>
              <SelectContent>
                {param.options?.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {hasError && (
              <p className="text-sm text-destructive flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {hasError}
              </p>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Execute Template: {templateName}</DialogTitle>
          <DialogDescription>
            {sourceWorkspaceId ? (
              sourceWorkspace ? (
                <>
                  Results will be stored in workspace <span className="font-semibold text-foreground">{sourceWorkspace.name}</span> under{" "}
                  <span className="font-mono text-sm">Template Executions/{templateName}/</span>
                </>
              ) : (
                <>
                  Results will be stored under{" "}
                  <span className="font-mono text-sm">Template Executions/{templateName}/</span>
                </>
              )
            ) : (
              <div className="flex items-center gap-2 text-amber-600 dark:text-amber-500">
                <AlertCircle className="h-4 w-4" />
                <span>
                  This template has no linked workspace. Please recreate the template from a workspace to enable execution.
                </span>
              </div>
            )}
          </DialogDescription>
        </DialogHeader>

        {sourceWorkspaceId ? (
          <>
            <div className="space-y-6 py-4">
              {/* Parameters */}
              {parameters.length > 0 ? (
                <div className="space-y-4">
                  {parameters.map((param) => renderParameterInput(param))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  This template has no parameters.
                </p>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={executeMutation.isPending}>
                Cancel
              </Button>
              <Button onClick={() => executeMutation.mutate()} disabled={executeMutation.isPending}>
                {executeMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Executing...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Execute Template
                  </>
                )}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
