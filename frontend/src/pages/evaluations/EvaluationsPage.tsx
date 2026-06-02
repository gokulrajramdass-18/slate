"use client";

import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  evaluationApi,
  type EvaluationDataset,
  type EvaluationRun,
  type EvaluationSummary,
} from "@/lib/api/evaluations";
import * as standaloneAgentsApi from "@/lib/api/standalone-agents";
import type { StandaloneAgent } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  BarChart3,
  CheckCircle,
  Clock,
  FileText,
  Loader2,
  PlayCircle,
  TrendingUp,
  Upload,
  XCircle,
} from "lucide-react";
import { DatasetUploadModal, EvaluationResultsModal, EvaluationTrendChart } from "@/components/agents/evaluation";

/**
 * Global evaluations page. Aggregates all datasets and runs across every
 * standalone agent (and, once Phase 4 ships, workflows). Authoring still
 * happens per-agent inside the AgentEvaluationTab; this page is read-mostly,
 * with one shortcut to upload a dataset that's not bound to a specific agent.
 */
export default function EvaluationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedRun, setSelectedRun] = useState<EvaluationRun | null>(null);
  const [showResultsModal, setShowResultsModal] = useState(false);

  const agentFilter = searchParams.get("agent") || "all";
  const statusFilter = searchParams.get("status") || "all";

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value === "all") next.delete(key);
    else next.set(key, value);
    setSearchParams(next, { replace: true });
  };

  // All standalone agents (for filter dropdown + name lookup)
  const { data: agentsData } = useQuery({
    queryKey: ["standalone-agents", "for-evals"],
    queryFn: () => standaloneAgentsApi.listStandaloneAgents({ limit: 200 }),
  });
  const agents: StandaloneAgent[] = agentsData?.agents || [];
  const agentNameById = useMemo(
    () => Object.fromEntries(agents.map((a) => [a.id, a.name])),
    [agents]
  );

  // All runs (no filter — we filter in-memory so the dropdowns stay fast)
  const { data: runs = [], isLoading: runsLoading, refetch: refetchRuns } = useQuery({
    queryKey: ["evaluation-runs", "all"],
    queryFn: () => evaluationApi.listRuns(),
  });

  // All datasets
  const { data: datasets = [], isLoading: datasetsLoading, refetch: refetchDatasets } = useQuery({
    queryKey: ["evaluation-datasets", "all"],
    queryFn: () => evaluationApi.listDatasets(),
  });

  // Per-agent summaries for the leaderboard tab
  const { data: summariesByAgent = {} } = useQuery({
    queryKey: ["evaluation-summaries", "all", agents.map((a) => a.id)],
    queryFn: async () => {
      const out: Record<string, EvaluationSummary> = {};
      await Promise.all(
        agents.map(async (a) => {
          try {
            out[a.id] = await evaluationApi.getAgentSummary(a.id);
          } catch {
            // ignore — agent has no eval runs yet
          }
        })
      );
      return out;
    },
    enabled: agents.length > 0,
  });

  const filteredRuns = useMemo(() => {
    return runs.filter((r) => {
      if (agentFilter !== "all" && r.agent_id !== agentFilter) return false;
      if (statusFilter !== "all" && r.status !== statusFilter) return false;
      return true;
    });
  }, [runs, agentFilter, statusFilter]);

  // KPI strip aggregates ON THE FILTERED set so changing filters re-scopes the view
  const kpis = useMemo(() => {
    const completed = filteredRuns.filter((r) => r.status === "completed");
    const totalCases = completed.reduce((s, r) => s + r.total_cases, 0);
    const totalPassed = completed.reduce((s, r) => s + r.passed_cases, 0);
    const passPct = totalCases > 0 ? (totalPassed / totalCases) * 100 : 0;
    const avgLatency =
      completed.length > 0
        ? completed.reduce((s, r) => s + (r.avg_latency_ms || 0), 0) / completed.length
        : 0;
    return {
      totalRuns: filteredRuns.length,
      passPct,
      avgLatency,
      datasetCount: datasets.length,
    };
  }, [filteredRuns, datasets]);

  const leaderboard = useMemo(() => {
    return agents
      .map((a) => ({
        agent: a,
        summary: summariesByAgent[a.id],
      }))
      .filter((x) => x.summary && x.summary.total_runs > 0)
      .sort((a, b) => (b.summary!.avg_pass_rate || 0) - (a.summary!.avg_pass_rate || 0));
  }, [agents, summariesByAgent]);

  const handleViewResults = (run: EvaluationRun) => {
    if (run.status !== "completed") return;
    setSelectedRun(run);
    setShowResultsModal(true);
  };

  const formatStatus = (status: string) => {
    const tones: Record<string, string> = {
      completed: "bg-green-500/10 text-green-700 dark:text-green-400",
      running: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
      failed: "bg-red-500/10 text-red-700 dark:text-red-400",
      pending: "bg-muted text-muted-foreground",
    };
    return tones[status] || "bg-muted text-muted-foreground";
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <BarChart3 className="w-7 h-7" />
            Evaluations
          </h1>
          <p className="text-muted-foreground mt-1">
            Test cases, accuracy scoring, and trends across all your agents.
          </p>
        </div>
        <Button onClick={() => setShowUploadModal(true)}>
          <Upload className="w-4 h-4 mr-2" />
          Upload Dataset
        </Button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total runs</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{kpis.totalRuns}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Avg pass rate</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{kpis.passPct.toFixed(1)}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Avg latency</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {kpis.avgLatency > 0 ? `${kpis.avgLatency.toFixed(0)}ms` : "—"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Datasets</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{kpis.datasetCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <span className="text-sm text-muted-foreground">Filter:</span>
        <Select value={agentFilter} onValueChange={(v) => setFilter("agent", v)}>
          <SelectTrigger className="w-[220px]">
            <SelectValue placeholder="All agents" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All agents</SelectItem>
            {agents.map((a) => (
              <SelectItem key={a.id} value={a.id}>
                {a.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={(v) => setFilter("status", v)}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="running">Running</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Trend chart on the filtered runs */}
      {filteredRuns.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Accuracy trend</CardTitle>
            <CardDescription>Across the runs matching your filters</CardDescription>
          </CardHeader>
          <CardContent>
            <EvaluationTrendChart runs={filteredRuns} height={260} />
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="runs" className="space-y-4">
        <TabsList>
          <TabsTrigger value="runs">Runs ({filteredRuns.length})</TabsTrigger>
          <TabsTrigger value="datasets">Datasets ({datasets.length})</TabsTrigger>
          <TabsTrigger value="agents">Agent leaderboard ({leaderboard.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="runs">
          <Card>
            <CardContent className="p-0">
              {runsLoading ? (
                <div className="py-12 text-center">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </div>
              ) : filteredRuns.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
                  <BarChart3 className="h-10 w-10 mx-auto mb-3 opacity-50" />
                  No runs match these filters.
                </div>
              ) : (
                <div className="divide-y">
                  {filteredRuns.map((run) => {
                    const passPct =
                      run.total_cases > 0
                        ? Math.round((run.passed_cases / run.total_cases) * 100)
                        : 0;
                    return (
                      <div
                        key={run.id}
                        className={`flex items-center justify-between p-4 hover:bg-accent/50 transition-colors ${
                          run.status === "completed" ? "cursor-pointer" : ""
                        }`}
                        onClick={() => handleViewResults(run)}
                      >
                        <div className="flex items-center gap-4 flex-1 min-w-0">
                          <div
                            className={`p-2 rounded-full ${formatStatus(run.status)} shrink-0`}
                          >
                            {run.status === "completed" ? (
                              <CheckCircle className="h-4 w-4" />
                            ) : run.status === "running" ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : run.status === "failed" ? (
                              <XCircle className="h-4 w-4" />
                            ) : (
                              <Clock className="h-4 w-4" />
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium truncate">
                                {run.run_name || run.dataset_name || "Untitled run"}
                              </span>
                              <Badge variant="outline" className="text-xs capitalize">
                                {run.status}
                              </Badge>
                            </div>
                            <div className="flex items-center gap-3 text-xs text-muted-foreground">
                              <Link
                                to={`/agents/standalone/${run.agent_id}/execute?tab=evaluations`}
                                className="hover:underline"
                                onClick={(e: React.MouseEvent) => e.stopPropagation()}
                              >
                                {run.agent_name || (run.agent_id ? agentNameById[run.agent_id] : null) || "agent"}
                              </Link>
                              {run.status === "completed" && (
                                <>
                                  <span>·</span>
                                  <span>
                                    {run.passed_cases}/{run.total_cases} passed ({passPct}%)
                                  </span>
                                  <span>·</span>
                                  <span>score {((run.avg_score || 0) * 10).toFixed(1)}/10</span>
                                </>
                              )}
                              {run.status === "running" && (
                                <>
                                  <span>·</span>
                                  <span>{run.progress}%</span>
                                </>
                              )}
                              {run.started_at && (
                                <>
                                  <span>·</span>
                                  <span>{new Date(run.started_at).toLocaleString()}</span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="datasets">
          <Card>
            <CardContent className="p-0">
              {datasetsLoading ? (
                <div className="py-12 text-center">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </div>
              ) : datasets.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
                  <FileText className="h-10 w-10 mx-auto mb-3 opacity-50" />
                  No datasets uploaded yet.
                  <div className="mt-4">
                    <Button variant="outline" onClick={() => setShowUploadModal(true)}>
                      <Upload className="h-4 w-4 mr-2" />
                      Upload your first dataset
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="divide-y">
                  {datasets.map((d: EvaluationDataset) => (
                    <div key={d.id} className="flex items-center justify-between p-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium truncate">{d.name}</span>
                          <Badge variant="secondary" className="text-xs">
                            {d.test_case_count} cases
                          </Badge>
                          <Badge variant="outline" className="text-xs">
                            {d.scoring_method}
                          </Badge>
                        </div>
                        {d.description && (
                          <p className="text-sm text-muted-foreground truncate">{d.description}</p>
                        )}
                        <p className="text-xs text-muted-foreground mt-1">
                          {d.agent_id ? (
                            <Link
                              className="hover:underline"
                              to={`/agents/standalone/${d.agent_id}/execute?tab=evaluations`}
                            >
                              For agent: {agentNameById[d.agent_id] || d.agent_id}
                            </Link>
                          ) : (
                            "Unbound (any agent)"
                          )}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="agents">
          <Card>
            <CardContent className="p-0">
              {leaderboard.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
                  No agents have been evaluated yet.
                </div>
              ) : (
                <div className="divide-y">
                  {leaderboard.map(({ agent, summary }, idx) => {
                    const passPct = Math.round((summary!.avg_pass_rate || 0) * 100);
                    const tone =
                      passPct >= 85
                        ? "text-green-600 dark:text-green-400"
                        : passPct >= 60
                          ? "text-amber-600 dark:text-amber-400"
                          : "text-red-600 dark:text-red-400";
                    return (
                      <Link
                        key={agent.id}
                        to={`/agents/standalone/${agent.id}/execute?tab=evaluations`}
                        className="flex items-center justify-between p-4 hover:bg-accent/50 transition-colors"
                      >
                        <div className="flex items-center gap-4">
                          <div className="text-2xl font-mono w-8 text-muted-foreground">
                            {idx + 1}
                          </div>
                          <div>
                            <div className="font-medium">{agent.name}</div>
                            <div className="text-xs text-muted-foreground">
                              {summary!.total_runs} runs · avg score{" "}
                              {((summary!.avg_score || 0) * 10).toFixed(1)}/10
                            </div>
                          </div>
                        </div>
                        <div className={`flex items-center gap-2 ${tone}`}>
                          <TrendingUp className="w-4 h-4" />
                          <span className="text-xl font-bold">{passPct}%</span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {showUploadModal && (
        <DatasetUploadModal
          // No agentId — dataset is unbound; can be run against any agent later.
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
            // Refetch in case the user just watched a running run flip to completed
            refetchRuns();
          }}
        />
      )}
    </div>
  );
}
