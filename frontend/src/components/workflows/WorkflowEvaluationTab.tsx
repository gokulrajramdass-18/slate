"use client";

/**
 * Workflow evaluation tab — clone of AgentEvaluationTab but bound to a
 * workflow target. Reuses the same datasets / runs / results flows; the only
 * difference is `target_type='workflow'` is set when creating datasets and runs.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  evaluationApi,
  type EvaluationDataset,
  type EvaluationRun,
} from "@/lib/api/evaluations";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Upload,
  PlayCircle,
  FileText,
  TrendingUp,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  ChevronRight,
} from "lucide-react";
import {
  DatasetUploadModal,
  EvaluationResultsModal,
  EvaluationTrendChart,
} from "@/components/agents/evaluation";
import { apiClient } from "@/lib/api/client";

interface WorkflowEvaluationTabProps {
  workflowId: string;
  workflowName: string;
}

export function WorkflowEvaluationTab({ workflowId, workflowName }: WorkflowEvaluationTabProps) {
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null);
  const [showResultsModal, setShowResultsModal] = useState(false);
  const [runningDatasetId, setRunningDatasetId] = useState<string | null>(null);

  // Datasets bound to this workflow.
  // The backend list endpoint filters by agent_id, not workflow_id, so we fetch
  // all and filter client-side. Acceptable while authoring is per-workflow.
  const { data: allDatasets = [], isLoading: datasetsLoading, refetch: refetchDatasets } = useQuery({
    queryKey: ["evaluation-datasets", "all-for-workflow"],
    queryFn: () => evaluationApi.listDatasets(),
  });
  const datasets = allDatasets.filter((d: any) => d.workflow_id === workflowId || (!d.workflow_id && d.target_type === "workflow"));

  // Runs for this workflow — fetched globally and filtered locally.
  const { data: allRuns = [], isLoading: runsLoading, refetch: refetchRuns } = useQuery({
    queryKey: ["evaluation-runs", "all-for-workflow"],
    queryFn: () => evaluationApi.listRuns(),
  });
  const runs = allRuns.filter((r: any) => r.workflow_id === workflowId);

  const handleRunStart = async (dataset: EvaluationDataset) => {
    try {
      setRunningDatasetId(dataset.id);
      // Direct POST so we can include workflow_id + target_type without changing
      // the typed createRun signature (the API accepts these as optional).
      await apiClient.post("/agent-evaluations/runs", {
        dataset_id: dataset.id,
        workflow_id: workflowId,
        target_type: "workflow",
        run_name: `${workflowName} · ${new Date().toLocaleString()}`,
      });
      refetchRuns();
    } finally {
      setRunningDatasetId(null);
    }
  };

  const handleViewResults = (run: EvaluationRun) => {
    setSelectedRun(run);
    setShowResultsModal(true);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-500";
      case "running":
        return "bg-blue-500";
      case "failed":
        return "bg-red-500";
      default:
        return "bg-gray-500";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-4 w-4" />;
      case "running":
        return <Loader2 className="h-4 w-4 animate-spin" />;
      case "failed":
        return <XCircle className="h-4 w-4" />;
      default:
        return <Clock className="h-4 w-4" />;
    }
  };

  return (
    <div className="space-y-6">
      {runs.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Accuracy over time</CardTitle>
            <CardDescription>Pass rate and avg score across recent workflow runs</CardDescription>
          </CardHeader>
          <CardContent>
            <EvaluationTrendChart runs={runs} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Datasets</CardTitle>
              <CardDescription>
                Test cases for evaluating <span className="font-medium">{workflowName}</span>
              </CardDescription>
            </div>
            <Button onClick={() => setShowUploadModal(true)}>
              <Upload className="h-4 w-4 mr-2" />
              Upload Dataset
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {datasetsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : datasets.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground mb-4">No datasets yet</p>
              <Button variant="outline" onClick={() => setShowUploadModal(true)}>
                <Upload className="h-4 w-4 mr-2" />
                Upload Your First Dataset
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {datasets.map((dataset) => (
                <div
                  key={dataset.id}
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium">{dataset.name}</h4>
                      <Badge variant="secondary" className="text-xs">
                        {dataset.test_case_count} cases
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {dataset.scoring_method}
                      </Badge>
                    </div>
                    {dataset.description && (
                      <p className="text-sm text-muted-foreground">{dataset.description}</p>
                    )}
                  </div>
                  <Button
                    size="sm"
                    onClick={() => handleRunStart(dataset)}
                    disabled={runningDatasetId === dataset.id}
                  >
                    {runningDatasetId === dataset.id ? (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <PlayCircle className="h-4 w-4 mr-1" />
                    )}
                    Run
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent runs</CardTitle>
          <CardDescription>View results from past evaluations</CardDescription>
        </CardHeader>
        <CardContent>
          {runsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : runs.length === 0 ? (
            <div className="text-center py-8">
              <TrendingUp className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
              <p className="text-muted-foreground">No evaluation runs yet</p>
            </div>
          ) : (
            <div className="space-y-3">
              {runs.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center justify-between p-4 border rounded-lg hover:bg-accent transition-colors cursor-pointer"
                  onClick={() => run.status === "completed" && handleViewResults(run)}
                >
                  <div className="flex items-center gap-4 flex-1">
                    <div className={`p-2 rounded-full ${getStatusColor(run.status)}`}>
                      {getStatusIcon(run.status)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium">{run.run_name || run.dataset_name}</h4>
                        <Badge variant="secondary" className="text-xs capitalize">
                          {run.status}
                        </Badge>
                      </div>
                      {run.status === "completed" && (
                        <div className="flex items-center gap-4 text-sm text-muted-foreground">
                          <span>
                            <CheckCircle className="h-3 w-3 inline mr-1 text-green-600" />
                            {run.passed_cases}/{run.total_cases} passed
                          </span>
                          <span>Score: {((run.avg_score || 0) * 10).toFixed(1)}/10</span>
                          <span>Avg: {run.avg_latency_ms?.toFixed(0)}ms</span>
                        </div>
                      )}
                      {run.status === "running" && (
                        <div className="text-sm text-muted-foreground">Progress: {run.progress}%</div>
                      )}
                      {run.status === "failed" && run.error_message && (
                        <div className="text-sm text-red-600">{run.error_message}</div>
                      )}
                    </div>
                  </div>
                  {run.status === "completed" && (
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {showUploadModal && (
        <DatasetUploadModal
          workflowId={workflowId}
          onClose={() => setShowUploadModal(false)}
          onSuccess={() => {
            refetchDatasets();
            setShowUploadModal(false);
          }}
        />
      )}

      {showResultsModal && selectedRun && (
        <EvaluationResultsModal
          run={selectedRun}
          onClose={() => {
            setShowResultsModal(false);
            refetchRuns();
          }}
        />
      )}
    </div>
  );
}
