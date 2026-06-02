"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { evaluationApi, type EvaluationDataset, type EvaluationRun } from "@/lib/api/evaluations";
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
import { DatasetUploadModal } from "./DatasetUploadModal";
import { RunEvaluationModal } from "./RunEvaluationModal";
import { EvaluationResultsModal } from "./EvaluationResultsModal";
import { EvaluationTrendChart } from "./EvaluationTrendChart";

interface AgentEvaluationTabProps {
  agentId: string;
  agentName: string;
}

export function AgentEvaluationTab({ agentId, agentName }: AgentEvaluationTabProps) {
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showRunModal, setShowRunModal] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState<EvaluationDataset | null>(null);
  const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null);
  const [showResultsModal, setShowResultsModal] = useState(false);

  // Fetch datasets
  const { data: datasets = [], isLoading: datasetsLoading, refetch: refetchDatasets } = useQuery({
    queryKey: ["evaluation-datasets", agentId],
    queryFn: () => evaluationApi.listDatasets(agentId),
  });

  // Fetch runs
  const { data: runs = [], isLoading: runsLoading, refetch: refetchRuns } = useQuery({
    queryKey: ["evaluation-runs", agentId],
    queryFn: () => evaluationApi.listRuns(agentId),
  });

  // Fetch summary
  const { data: summary } = useQuery({
    queryKey: ["evaluation-summary", agentId],
    queryFn: () => evaluationApi.getAgentSummary(agentId),
  });

  const handleUploadSuccess = () => {
    refetchDatasets();
    setShowUploadModal(false);
  };

  const handleRunStart = (dataset: EvaluationDataset) => {
    setSelectedDataset(dataset);
    setShowRunModal(true);
  };

  const handleRunSuccess = () => {
    refetchRuns();
    setShowRunModal(false);
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
      {/* Summary Stats */}
      {summary && summary.total_runs > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.total_runs}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Avg Pass Rate</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary.avg_pass_rate * 100).toFixed(1)}%
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">Avg Score</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary.avg_score * 10).toFixed(1)}/10
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Trend chart — only renders once at least two completed runs exist */}
      {runs.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Accuracy over time</CardTitle>
            <CardDescription>Pass rate and avg score across recent runs</CardDescription>
          </CardHeader>
          <CardContent>
            <EvaluationTrendChart runs={runs} />
          </CardContent>
        </Card>
      )}

      {/* Datasets Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Evaluation Datasets</CardTitle>
              <CardDescription>
                Upload test cases to evaluate your agent's performance
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
                  >
                    <PlayCircle className="h-4 w-4 mr-1" />
                    Run
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Runs Section */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Evaluation Runs</CardTitle>
          <CardDescription>
            View results from past evaluations
          </CardDescription>
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
                          <span>
                            Score: {((run.avg_score || 0) * 10).toFixed(1)}/10
                          </span>
                          <span>
                            Avg: {run.avg_latency_ms?.toFixed(0)}ms
                          </span>
                        </div>
                      )}

                      {run.status === "running" && (
                        <div className="text-sm text-muted-foreground">
                          Progress: {run.progress}%
                        </div>
                      )}

                      {run.status === "failed" && run.error_message && (
                        <div className="text-sm text-red-600">
                          {run.error_message}
                        </div>
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

      {/* Modals */}
      {showUploadModal && (
        <DatasetUploadModal
          agentId={agentId}
          onClose={() => setShowUploadModal(false)}
          onSuccess={handleUploadSuccess}
        />
      )}

      {showRunModal && selectedDataset && (
        <RunEvaluationModal
          agentId={agentId}
          agentName={agentName}
          dataset={selectedDataset}
          onClose={() => setShowRunModal(false)}
          onSuccess={handleRunSuccess}
        />
      )}

      {showResultsModal && selectedRun && (
        <EvaluationResultsModal
          run={selectedRun}
          onClose={() => setShowResultsModal(false)}
        />
      )}
    </div>
  );
}
