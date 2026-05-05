"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, RotateCcw, Save, Power, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import * as systemPromptsApi from "@/lib/api/system-prompts";

interface SystemPromptEditorProps {
  templateKey: string;
  category: string;
}

export function SystemPromptEditor({ templateKey, category }: SystemPromptEditorProps) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [hasChanges, setHasChanges] = useState(false);

  // Fetch template
  const { data: template, isLoading } = useQuery({
    queryKey: ["system-prompt", templateKey],
    queryFn: () => systemPromptsApi.getTemplate(templateKey),
    enabled: !!templateKey,
  });

  // Update state when template data changes
  useEffect(() => {
    if (template) {
      setContent(template.template);
      setName(template.name);
      setDescription(template.description || "");
      setHasChanges(false);
    }
  }, [template]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: systemPromptsApi.SystemPromptTemplateUpdate) =>
      systemPromptsApi.updateTemplate(templateKey, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system-prompt", templateKey] });
      queryClient.invalidateQueries({ queryKey: ["system-prompts", category] });
      setHasChanges(false);
    },
  });

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: () => systemPromptsApi.resetTemplate(templateKey),
    onSuccess: (data) => {
      setContent(data.template);
      setName(data.name);
      setDescription(data.description || "");
      setHasChanges(false);
      queryClient.invalidateQueries({ queryKey: ["system-prompt", templateKey] });
      queryClient.invalidateQueries({ queryKey: ["system-prompts", category] });
    },
  });

  // Toggle mutation
  const toggleMutation = useMutation({
    mutationFn: () => systemPromptsApi.toggleTemplate(templateKey),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system-prompt", templateKey] });
      queryClient.invalidateQueries({ queryKey: ["system-prompts", category] });
    },
  });

  const handleSave = () => {
    updateMutation.mutate({
      template: content,
      name: name !== template?.name ? name : undefined,
      description: description !== template?.description ? description : undefined,
    });
  };

  const handleReset = () => {
    if (confirm("Reset this template to its factory default? This cannot be undone.")) {
      resetMutation.mutate();
    }
  };

  const handleToggle = () => {
    const action = template?.is_active ? "disable" : "enable";
    if (confirm(`Are you sure you want to ${action} this template?`)) {
      toggleMutation.mutate();
    }
  };

  const handleContentChange = (value: string) => {
    setContent(value);
    setHasChanges(value !== template?.template);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-sm text-muted-foreground">Loading template...</div>
      </div>
    );
  }

  if (!template) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-sm text-muted-foreground">Template not found</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header with badges and actions */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-lg font-semibold">{template.name}</h3>
            <Badge variant="outline" className="text-xs">
              {template.metadata.output_format}
            </Badge>
            {template.metadata.composition && (
              <Badge variant="secondary" className="text-xs">
                {template.metadata.composition}
              </Badge>
            )}
            {!template.is_default && (
              <Badge variant="default" className="text-xs">
                Custom
              </Badge>
            )}
            {!template.is_active && (
              <Badge variant="destructive" className="text-xs">
                Disabled
              </Badge>
            )}
          </div>
          {template.description && (
            <p className="text-sm text-muted-foreground">{template.description}</p>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleToggle}
            disabled={toggleMutation.isPending}
          >
            <Power className="h-4 w-4 mr-1.5" />
            {template.is_active ? "Disable" : "Enable"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReset}
            disabled={resetMutation.isPending || template.is_default}
          >
            <RotateCcw className="h-4 w-4 mr-1.5" />
            Reset
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || updateMutation.isPending}
          >
            <Save className="h-4 w-4 mr-1.5" />
            Save
          </Button>
        </div>
      </div>

      {/* Variables reference (collapsible) */}
      {template.variables.length > 0 && (
        <Collapsible>
          <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium hover:underline">
            <Badge variant="outline" className="text-xs">
              {template.variables.length} variable{template.variables.length !== 1 ? "s" : ""}
            </Badge>
            <ChevronDown className="h-4 w-4" />
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            <div className="border rounded-lg p-4 space-y-3 bg-muted/30">
              <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Available Variables
              </div>
              {template.variables.map((v) => (
                <div key={v.name} className="text-sm space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <code className="px-1.5 py-0.5 rounded bg-background font-mono text-xs">
                      {`{${v.name}}`}
                    </code>
                    <Badge variant="secondary" className="text-xs">
                      {v.type}
                    </Badge>
                    {v.required && (
                      <Badge variant="destructive" className="text-xs">
                        required
                      </Badge>
                    )}
                  </div>
                  {v.description && (
                    <p className="text-xs text-muted-foreground">{v.description}</p>
                  )}
                  {v.example && (
                    <p className="text-xs text-muted-foreground">
                      Example: <code className="text-xs">{v.example}</code>
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>
      )}

      {/* Inactive warning */}
      {!template.is_active && (
        <div className="flex items-start gap-2 p-3 border border-destructive/50 bg-destructive/10 rounded-lg">
          <AlertCircle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
          <div className="text-sm text-destructive">
            <strong>Template Disabled:</strong> The system will use the hardcoded fallback prompt
            instead of this template. Enable it to use the database version.
          </div>
        </div>
      )}

      {/* Editor */}
      <Textarea
        value={content}
        onChange={(e) => handleContentChange(e.target.value)}
        className={cn(
          "min-h-[500px] font-mono text-sm",
          !template.is_active && "opacity-50"
        )}
        disabled={!template.is_active}
        placeholder="Enter prompt template..."
      />

      {/* Footer info */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-4">
          <span>{content.length} characters</span>
          {template.metadata.max_length && (
            <span>
              Max: {template.metadata.max_length} (
              {Math.round((content.length / template.metadata.max_length) * 100)}%)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span>Output: {template.metadata.output_format}</span>
          {hasChanges && (
            <Badge variant="outline" className="text-xs">
              Unsaved changes
            </Badge>
          )}
        </div>
      </div>

      {/* Metadata note */}
      {template.metadata.note && (
        <div className="text-xs text-muted-foreground p-3 bg-muted/50 rounded-lg border">
          <strong>Note:</strong> {template.metadata.note}
        </div>
      )}
    </div>
  );
}
