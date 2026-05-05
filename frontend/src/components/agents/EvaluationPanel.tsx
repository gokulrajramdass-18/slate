"use client";

import { Award, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { AgentEvaluation } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

interface EvaluationPanelProps {
  evaluations: AgentEvaluation[];
}

export function EvaluationPanel({ evaluations }: EvaluationPanelProps) {
  if (!evaluations || evaluations.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No evaluations available
      </div>
    );
  }

  const getApprovalColor = (status: string) => {
    switch (status) {
      case "approved":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
      case "needs_revision":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
      case "requires_rework":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    }
  };

  const getApprovalIcon = (status: string) => {
    switch (status) {
      case "approved":
        return <CheckCircle2 className="h-4 w-4 text-green-600" />;
      case "needs_revision":
        return <AlertCircle className="h-4 w-4 text-yellow-600" />;
      case "requires_rework":
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return <AlertCircle className="h-4 w-4 text-gray-600" />;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-2">
        <Award className="h-5 w-5 text-yellow-600" />
        <h3 className="text-lg font-semibold">Judge Evaluations</h3>
      </div>

      {evaluations.map((evaluation) => (
        <Card key={evaluation.id} className="p-4">
          <div className="space-y-3">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">
                  {evaluation.scope === "final_result"
                    ? "Final Result Evaluation"
                    : `${evaluation.target_agent_name || "Agent"} Output`}
                </div>
                <div className="text-xs text-muted-foreground">
                  by {evaluation.judge_name || "Judge"}
                </div>
              </div>
              <Badge className={getApprovalColor(evaluation.approval_status)}>
                {getApprovalIcon(evaluation.approval_status)}
                <span className="ml-1 capitalize">
                  {evaluation.approval_status.replace("_", " ")}
                </span>
              </Badge>
            </div>

            {/* Overall Score */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Overall Score</span>
                <span className="text-lg font-bold text-yellow-600">
                  {evaluation.overall_score.toFixed(1)}/10
                </span>
              </div>
              <Progress value={evaluation.overall_score * 10} className="h-2" />
            </div>

            {/* Criteria Scores */}
            {evaluation.criteria_scores && Object.keys(evaluation.criteria_scores).length > 0 && (
              <div className="flex flex-wrap gap-2">
                {Object.entries(evaluation.criteria_scores).map(([key, value]) => (
                  <Badge key={key} variant="outline" className="font-normal">
                    {key.charAt(0).toUpperCase() + key.slice(1)}: {value}/10
                  </Badge>
                ))}
              </div>
            )}

            {/* Feedback */}
            {evaluation.feedback && (
              <div className="rounded-lg bg-muted p-3">
                <div className="text-sm font-medium mb-1">Feedback</div>
                <div className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {evaluation.feedback}
                </div>
              </div>
            )}

            {/* Confidence */}
            {evaluation.confidence && (
              <div className="text-xs text-muted-foreground">
                Confidence: {(evaluation.confidence * 100).toFixed(0)}%
              </div>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}
