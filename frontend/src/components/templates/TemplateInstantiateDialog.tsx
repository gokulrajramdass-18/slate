"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
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
import { toast } from "sonner";

interface TemplateInstantiateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  templateId: string;
  templateName: string;
  parameters: TemplateParameter[];
}

export function TemplateInstantiateDialog({
  open,
  onOpenChange,
  templateId,
  templateName,
  parameters,
}: TemplateInstantiateDialogProps) {
  const router = useRouter();
  const queryClient = useQueryClient();

  // Initialize parameter values with defaults
  const [workspaceName, setWorkspaceName] = useState(`${templateName} - ${new Date().toLocaleDateString()}`);
  const [paramValues, setParamValues] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = {};
    parameters.forEach((param) => {
      initial[param.name] = param.default_value ?? "";
    });
    return initial;
  });
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const instantiateMutation = useMutation({
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

      return templatesApi.instantiate(templateId, {
        parameters: paramValues,
        workspace_name: workspaceName,
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["templates", templateId] });
      queryClient.invalidateQueries({ queryKey: ["notebooks"] });
      toast.success("Workspace created successfully!");
      onOpenChange(false);

      // Navigate to the new workspace
      router.push(`/workspaces/${data.workspace_id}`);
    },
    onError: (error: any) => {
      toast.error(error.message || error.response?.data?.detail || "Failed to create workspace");
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
    const hasError = !!validationErrors[param.name];

    switch (param.type) {
      case "boolean":
        return (
          <div className="flex items-center justify-between space-x-2">
            <Label htmlFor={param.name} className="flex-1">
              {param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
              {param.description && (
                <p className="text-sm text-muted-foreground font-normal mt-1">
                  {param.description}
                </p>
              )}
            </Label>
            <Switch
              id={param.name}
              checked={paramValues[param.name] || false}
              onCheckedChange={(checked) => handleParamChange(param.name, checked)}
            />
          </div>
        );

      case "select":
        return (
          <div className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Select
              value={paramValues[param.name] || ""}
              onValueChange={(value) => handleParamChange(param.name, value)}
            >
              <SelectTrigger className={hasError ? "border-red-500" : ""}>
                <SelectValue placeholder="Select an option" />
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
              <p className="text-sm text-red-500 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {validationErrors[param.name]}
              </p>
            )}
          </div>
        );

      case "number":
        return (
          <div className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Input
              id={param.name}
              type="number"
              value={paramValues[param.name] ?? ""}
              onChange={(e) => handleParamChange(param.name, parseFloat(e.target.value))}
              className={hasError ? "border-red-500" : ""}
            />
            {hasError && (
              <p className="text-sm text-red-500 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {validationErrors[param.name]}
              </p>
            )}
          </div>
        );

      case "date":
        return (
          <div className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Input
              id={param.name}
              type="date"
              value={paramValues[param.name] || ""}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
              className={hasError ? "border-red-500" : ""}
            />
            {hasError && (
              <p className="text-sm text-red-500 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {validationErrors[param.name]}
              </p>
            )}
          </div>
        );

      default: // string
        return (
          <div className="space-y-2">
            <Label htmlFor={param.name}>
              {param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            {param.description && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
            <Input
              id={param.name}
              type="text"
              value={paramValues[param.name] || ""}
              onChange={(e) => handleParamChange(param.name, e.target.value)}
              placeholder={param.default_value}
              className={hasError ? "border-red-500" : ""}
            />
            {hasError && (
              <p className="text-sm text-red-500 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {validationErrors[param.name]}
              </p>
            )}
          </div>
        );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Run Template: {templateName}</DialogTitle>
          <DialogDescription>
            Configure parameters and create a new workspace from this template.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Workspace Name */}
          <div className="space-y-2">
            <Label htmlFor="workspace-name">
              Workspace Name
              <span className="text-red-500 ml-1">*</span>
            </Label>
            <Input
              id="workspace-name"
              type="text"
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              placeholder="Enter workspace name"
            />
          </div>

          {/* Template Parameters */}
          {parameters.length > 0 ? (
            <>
              <div className="border-t pt-4">
                <h3 className="text-sm font-medium mb-4">Template Parameters</h3>
                <div className="space-y-4">
                  {parameters.map((param) => (
                    <div key={param.name}>{renderParameterInput(param)}</div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              This template has no configurable parameters.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={instantiateMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={() => instantiateMutation.mutate()}
            disabled={instantiateMutation.isPending || !workspaceName.trim()}
          >
            {instantiateMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Create Workspace
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
