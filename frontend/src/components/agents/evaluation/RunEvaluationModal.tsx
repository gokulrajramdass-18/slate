"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { evaluationApi, type EvaluationDataset } from "@/lib/api/evaluations";
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
import { PlayCircle, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

interface RunEvaluationModalProps {
  agentId: string;
  agentName: string;
  dataset: EvaluationDataset;
  onClose: () => void;
  onSuccess: () => void;
}

export function RunEvaluationModal({
  agentId,
  agentName,
  dataset,
  onClose,
  onSuccess,
}: RunEvaluationModalProps) {
  const { toast } = useToast();
  const [runName, setRunName] = useState(
    `${agentName} - ${dataset.name} - ${new Date().toLocaleDateString()}`
  );
  const [modelOverride, setModelOverride] = useState("");

  const runMutation = useMutation({
    mutationFn: async () => {
      return evaluationApi.createRun({
        dataset_id: dataset.id,
        agent_id: agentId,
        run_name: runName,
        model_override: modelOverride || undefined,
      });
    },
    onSuccess: () => {
      toast({
        title: "Evaluation started",
        description: `Running ${dataset.test_case_count} test cases...`,
      });
      onSuccess();
    },
    onError: (error: any) => {
      toast({
        title: "Failed to start evaluation",
        description: error.message || "An error occurred",
        variant: "destructive",
      });
    },
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Run Evaluation</DialogTitle>
          <DialogDescription>
            Execute {dataset.test_case_count} test cases from "{dataset.name}"
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div>
            <Label htmlFor="run-name">Run Name</Label>
            <Input
              id="run-name"
              value={runName}
              onChange={(e) => setRunName(e.target.value)}
              placeholder="Evaluation run name"
              className="mt-2"
            />
          </div>

          <div>
            <Label htmlFor="model-override">Model Override (Optional)</Label>
            <Input
              id="model-override"
              value={modelOverride}
              onChange={(e) => setModelOverride(e.target.value)}
              placeholder="e.g., gpt-4, claude-3-opus"
              className="mt-2"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Leave empty to use agent's default model
            </p>
          </div>

          <div className="p-4 bg-muted rounded-lg">
            <div className="text-sm space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Test Cases:</span>
                <span className="font-medium">{dataset.test_case_count}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Scoring Method:</span>
                <span className="font-medium capitalize">{dataset.scoring_method}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Criteria:</span>
                <span className="font-medium">{dataset.criteria.join(", ")}</span>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={runMutation.isPending}>
            Cancel
          </Button>
          <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
            {runMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <PlayCircle className="h-4 w-4 mr-2" />
                Start Evaluation
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
