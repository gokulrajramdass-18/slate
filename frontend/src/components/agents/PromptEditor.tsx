"use client";

import { useState, useEffect, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { promptsApi, type PromptTemplate } from "@/lib/api/agent-prompts";
import { queryKeys } from "@/lib/query-client";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
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
import { Save, RotateCcw, Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface PromptEditorProps {
  template: PromptTemplate;
}

export function PromptEditor({ template }: PromptEditorProps) {
  const queryClient = useQueryClient();
  const [content, setContent] = useState(template.template);
  const [showPreview, setShowPreview] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const hasChanges = content !== template.template;

  // Sync local state when template changes externally
  useEffect(() => {
    setContent(template.template);
  }, [template.template]);

  const saveMutation = useMutation({
    mutationFn: () => promptsApi.update(template.role, { template: content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.promptTemplates });
      queryClient.invalidateQueries({ queryKey: queryKeys.promptTemplate(template.role) });
      toast.success("Prompt saved");
    },
    onError: () => toast.error("Failed to save prompt"),
  });

  const resetMutation = useMutation({
    mutationFn: () => promptsApi.reset(template.role),
    onSuccess: (data) => {
      setContent(data.template);
      queryClient.invalidateQueries({ queryKey: queryKeys.promptTemplates });
      queryClient.invalidateQueries({ queryKey: queryKeys.promptTemplate(template.role) });
      toast.success("Prompt reset to default");
      setShowResetConfirm(false);
    },
    onError: () => toast.error("Failed to reset prompt"),
  });

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (hasChanges) saveMutation.mutate();
      }
    },
    [hasChanges, saveMutation]
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold capitalize">{template.role} Prompt</h3>
          {!template.is_default && (
            <Badge variant="outline" className="text-xs">
              Customized
            </Badge>
          )}
          {hasChanges && (
            <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200 border-0 text-xs">
              Unsaved changes
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setShowPreview(!showPreview)}
            title={showPreview ? "Edit" : "Preview"}
          >
            {showPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            {showPreview ? "Edit" : "Preview"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setShowResetConfirm(true)}
            disabled={template.is_default && !hasChanges}
          >
            <RotateCcw className="w-4 h-4 mr-1" />
            Reset
          </Button>
          <Button
            size="sm"
            onClick={() => saveMutation.mutate()}
            disabled={!hasChanges || saveMutation.isPending}
          >
            {saveMutation.isPending ? (
              <Loader2 className="w-4 h-4 mr-1 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-1" />
            )}
            Save
          </Button>
        </div>
      </div>

      {/* Description */}
      {template.description && (
        <p className="text-sm text-muted-foreground">{template.description}</p>
      )}

      {/* Editor / Preview */}
      {showPreview ? (
        <div className="min-h-[400px] p-4 rounded-md border bg-muted/30 font-mono text-sm whitespace-pre-wrap break-words">
          {content}
        </div>
      ) : (
        <Textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          className="min-h-[400px] font-mono text-sm resize-y"
          placeholder="Enter system prompt..."
        />
      )}

      {/* Character count */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{content.length.toLocaleString()} characters</span>
        <span className="text-xs">Cmd+S to save</span>
      </div>

      {/* Reset Confirmation */}
      <AlertDialog open={showResetConfirm} onOpenChange={setShowResetConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset to default?</AlertDialogTitle>
            <AlertDialogDescription>
              This will replace the current {template.role} prompt with the built-in
              default. Any customizations will be lost.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => resetMutation.mutate()}
              disabled={resetMutation.isPending}
            >
              {resetMutation.isPending ? "Resetting..." : "Reset"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
