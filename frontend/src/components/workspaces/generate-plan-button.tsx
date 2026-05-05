"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Sparkles, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

interface GeneratePlanButtonProps {
  workspaceId: string;
  workspaceName: string;
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg" | "icon";
  className?: string;
}

export function GeneratePlanButton({
  workspaceId,
  workspaceName,
  variant = "outline",
  size = "sm",
  className = "",
}: GeneratePlanButtonProps) {
  const queryClient = useQueryClient();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGeneratePlan = async () => {
    setIsGenerating(true);
    setError(null);
    setGenerationResult(null);

    try {
      const { data } = await apiClient.post(`/workspaces/${workspaceId}/generate-plan`);

      setGenerationResult(data);
      toast.success("Execution plan generated successfully!");

      // Invalidate queries to refresh workspace data
      queryClient.invalidateQueries({ queryKey: ["notebook", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["workspace-plan", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["workspace-tasks", workspaceId] });
      queryClient.invalidateQueries({ queryKey: ["workspaces", "with-plans"] });

    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || "Failed to generate plan";
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleClose = () => {
    setIsDialogOpen(false);
    setGenerationResult(null);
    setError(null);
  };

  return (
    <>
      <Button
        variant={variant}
        size={size}
        onClick={() => setIsDialogOpen(true)}
        className={`gap-1.5 ${className}`}
      >
        <Sparkles className="w-3.5 h-3.5" />
        <span className="hidden sm:inline">Generate Plan</span>
      </Button>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Generate Execution Plan</DialogTitle>
            <DialogDescription>
              AI will analyze your workspace and create a structured execution plan with phases, tasks, and agent assignments.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Workspace Info */}
            <div className="bg-muted/50 rounded-lg p-4">
              <h4 className="font-medium text-sm mb-2">Workspace</h4>
              <p className="text-sm text-muted-foreground">{workspaceName}</p>
            </div>

            {/* Generation Status */}
            {isGenerating && (
              <div className="flex items-center gap-3 p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
                <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                    Generating execution plan...
                  </p>
                  <p className="text-xs text-blue-700 dark:text-blue-300 mt-0.5">
                    Analyzing workspace sources, notes, and goal
                  </p>
                </div>
              </div>
            )}

            {/* Success Result */}
            {generationResult && !error && (
              <div className="space-y-3">
                <div className="flex items-center gap-3 p-4 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-green-900 dark:text-green-100">
                      Plan generated successfully!
                    </p>
                    <p className="text-xs text-green-700 dark:text-green-300 mt-0.5">
                      {generationResult.phases_count} phases with tasks and agent assignments
                    </p>
                  </div>
                </div>

                {/* Plan Summary */}
                <div className="border rounded-lg p-4 space-y-3">
                  <h4 className="font-medium text-sm">Generated Plan</h4>
                  {generationResult.plan?.phases?.map((phase: any, index: number) => (
                    <div key={index} className="pl-3 border-l-2 border-muted">
                      <p className="text-sm font-medium">{phase.phase}</p>
                      <p className="text-xs text-muted-foreground">
                        {phase.tasks?.length || 0} tasks
                      </p>
                    </div>
                  ))}
                </div>

                <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                  <p className="text-sm text-blue-900 dark:text-blue-100">
                    <strong>Next step:</strong> This workspace can now be converted to a template!
                  </p>
                  <p className="text-xs text-blue-700 dark:text-blue-300 mt-1">
                    Go to Templates → Create Template and select this workspace.
                  </p>
                </div>
              </div>
            )}

            {/* Error State */}
            {error && (
              <div className="flex items-start gap-3 p-4 bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 rounded-lg">
                <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-900 dark:text-red-100">
                    Generation failed
                  </p>
                  <p className="text-xs text-red-700 dark:text-red-300 mt-0.5">
                    {error}
                  </p>
                </div>
              </div>
            )}

            {/* Info Box (when not generating/complete) */}
            {!isGenerating && !generationResult && !error && (
              <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <p className="text-sm text-amber-900 dark:text-amber-100">
                  <strong>What happens?</strong>
                </p>
                <ul className="text-xs text-amber-700 dark:text-amber-300 mt-2 space-y-1 list-disc list-inside">
                  <li>AI analyzes your workspace sources and goal</li>
                  <li>Creates 2-4 phases with specific tasks</li>
                  <li>Assigns agents and collaboration patterns</li>
                  <li>Enables template creation for this workspace</li>
                </ul>
              </div>
            )}
          </div>

          <DialogFooter className="flex justify-between sm:justify-between">
            <Button
              type="button"
              variant="ghost"
              onClick={handleClose}
              disabled={isGenerating}
            >
              {generationResult ? "Close" : "Cancel"}
            </Button>
            {!generationResult && (
              <Button
                type="button"
                onClick={handleGeneratePlan}
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 mr-2" />
                    Generate Plan
                  </>
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
