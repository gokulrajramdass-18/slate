import { useState, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGraphSettings,
  useStartBulkRecompute,
  useBulkRecomputeStatus,
  useBulkRecomputeJobs,
  graphKeys,
} from "@/lib/api/graph";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Network,
  RefreshCw,
  Settings2,
  Database,
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { formatRelativeTime } from "@/lib/utils";
import { SettingsHeader } from "@/components/settings/settings-header";

export default function SettingsGraphPage() {
  const queryClient = useQueryClient();

  // Settings data
  const { data: settings, isLoading: settingsLoading } = useGraphSettings();

  // Configuration state
  const [threshold, setThreshold] = useState(0.7);
  const [topK, setTopK] = useState(20);
  const [minTopicOverlap, setMinTopicOverlap] = useState(2);

  // Bulk recompute
  const startBulkMutation = useStartBulkRecompute();
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const { data: activeJob } = useBulkRecomputeStatus(activeJobId);
  const { data: jobs, refetch: refetchJobs } = useBulkRecomputeJobs();

  // Sync local state from server defaults
  useEffect(() => {
    if (settings?.defaults) {
      setThreshold(settings.defaults.semantic_threshold);
      setTopK(settings.defaults.top_k);
      setMinTopicOverlap(settings.defaults.min_topic_overlap);
    }
  }, [settings]);

  // Clear active job tracking when it completes
  useEffect(() => {
    if (activeJob?.status === "completed") {
      toast.success(
        `Recomputed similarities for ${activeJob.total} sources`
      );
      queryClient.invalidateQueries({ queryKey: graphKeys.settings() });
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
      refetchJobs();
    } else if (activeJob?.status === "failed") {
      toast.error(`Recompute failed: ${activeJob.error || "Unknown error"}`);
      refetchJobs();
    }
  }, [activeJob?.status, activeJob?.total, activeJob?.error, queryClient, refetchJobs]);

  const handleStartRecompute = async () => {
    try {
      const result = await startBulkMutation.mutateAsync({
        threshold,
        topK,
      });
      setActiveJobId(result.job_id);
      toast.info("Bulk recompute started...");
    } catch (error: any) {
      toast.error(
        error.response?.data?.detail || "Failed to start recompute"
      );
    }
  };

  const isRunning =
    activeJob?.status === "running" || startBulkMutation.isPending;

  const progressPercent =
    activeJob && activeJob.total > 0
      ? Math.round((activeJob.completed / activeJob.total) * 100)
      : 0;

  return (
    <div className="space-y-6 max-w-4xl">
      <SettingsHeader
        title="Graph Settings"
        description="Configure similarity computation parameters and manage graph relationships"
      />

      {/* Overview Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Network className="w-5 h-5" />
            Graph Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          {settingsLoading ? (
            <div className="grid grid-cols-3 gap-4">
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              <StatCard
                label="Total Sources"
                value={settings?.total_sources ?? 0}
                icon={Database}
              />
              <StatCard
                label="With Embeddings"
                value={settings?.sources_with_embeddings ?? 0}
                icon={Zap}
              />
              <StatCard
                label="Similarities"
                value={settings?.similarity_count ?? 0}
                icon={Network}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Computation Parameters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings2 className="w-5 h-5" />
            Computation Parameters
          </CardTitle>
          <CardDescription>
            Configure thresholds used when computing semantic similarities
            between sources
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Similarity Threshold */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Semantic Similarity Threshold</Label>
              <span className="text-sm font-mono text-muted-foreground tabular-nums">
                {threshold.toFixed(2)}
              </span>
            </div>
            <Slider
              value={[threshold]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={([v]) => setThreshold(v)}
              disabled={isRunning}
            />
            <p className="text-xs text-muted-foreground">
              Minimum cosine similarity score to create a semantic edge. Lower
              values create more connections but may include weaker
              relationships.
            </p>
          </div>

          <Separator />

          {/* Max Similarities Per Source */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Max Similarities Per Source (top_k)</Label>
              <span className="text-sm font-mono text-muted-foreground tabular-nums">
                {topK}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <Slider
                value={[topK]}
                min={1}
                max={100}
                step={1}
                onValueChange={([v]) => setTopK(v)}
                className="flex-1"
                disabled={isRunning}
              />
              <Input
                type="number"
                value={topK}
                min={1}
                max={100}
                onChange={(e) =>
                  setTopK(Math.min(100, Math.max(1, Number(e.target.value))))
                }
                className="w-20 h-8 text-sm"
                disabled={isRunning}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Maximum number of similar sources to keep per source. Higher
              values create denser graphs.
            </p>
          </div>

          <Separator />

          {/* Min Topic Overlap */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Minimum Topic Overlap</Label>
              <span className="text-sm font-mono text-muted-foreground tabular-nums">
                {minTopicOverlap}
              </span>
            </div>
            <div className="flex items-center gap-4">
              <Slider
                value={[minTopicOverlap]}
                min={1}
                max={10}
                step={1}
                onValueChange={([v]) => setMinTopicOverlap(v)}
                className="flex-1"
                disabled={isRunning}
              />
              <Input
                type="number"
                value={minTopicOverlap}
                min={1}
                max={10}
                onChange={(e) =>
                  setMinTopicOverlap(
                    Math.min(10, Math.max(1, Number(e.target.value)))
                  )
                }
                className="w-20 h-8 text-sm"
                disabled={isRunning}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              Minimum number of shared topics to create a topic edge between
              sources.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Recompute */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="w-5 h-5" />
            Bulk Recompute
          </CardTitle>
          <CardDescription>
            Recompute semantic similarity edges for all sources with embeddings
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Progress bar when running */}
          {isRunning && activeJob && (
            <div className="space-y-2 p-4 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  Processing sources...
                </span>
                <span className="font-mono text-muted-foreground">
                  {activeJob.completed} / {activeJob.total}
                </span>
              </div>
              <Progress value={progressPercent} className="h-2" />
              <p className="text-xs text-muted-foreground">
                {progressPercent}% complete
              </p>
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button
              onClick={handleStartRecompute}
              disabled={
                isRunning || (settings?.sources_with_embeddings ?? 0) === 0
              }
            >
              {isRunning ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Computing...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Recompute All Similarities
                </>
              )}
            </Button>
            <p className="text-sm text-muted-foreground">
              Will process{" "}
              <strong>{settings?.sources_with_embeddings ?? 0}</strong> sources
              with threshold <strong>{threshold.toFixed(2)}</strong> and top_k{" "}
              <strong>{topK}</strong>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Computation History */}
      {jobs && jobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              Computation History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-gray-200 dark:border-gray-800 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-800/50">
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">
                      Status
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">
                      Sources
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">
                      Threshold
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">
                      Top K
                    </th>
                    <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground">
                      Started
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr
                      key={job.id}
                      className="border-t border-gray-100 dark:border-gray-800"
                    >
                      <td className="px-4 py-2">
                        <JobStatusBadge status={job.status} />
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">
                        {job.completed} / {job.total}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">
                        {job.threshold.toFixed(2)}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">
                        {job.top_k}
                      </td>
                      <td className="px-4 py-2 text-xs text-muted-foreground">
                        {job.started_at
                          ? formatRelativeTime(job.started_at)
                          : "--"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-800">
      <div className="p-2 rounded-md bg-gray-100 dark:bg-gray-800">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div>
        <p className="text-2xl font-bold tabular-nums">
          {value.toLocaleString()}
        </p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

function JobStatusBadge({
  status,
}: {
  status: "running" | "completed" | "failed";
}) {
  switch (status) {
    case "completed":
      return (
        <Badge
          variant="outline"
          className="text-green-700 border-green-300 dark:text-green-400 dark:border-green-800"
        >
          <CheckCircle className="h-3 w-3 mr-1" />
          Completed
        </Badge>
      );
    case "failed":
      return (
        <Badge
          variant="outline"
          className="text-red-700 border-red-300 dark:text-red-400 dark:border-red-800"
        >
          <XCircle className="h-3 w-3 mr-1" />
          Failed
        </Badge>
      );
    case "running":
      return (
        <Badge
          variant="outline"
          className="text-blue-700 border-blue-300 dark:text-blue-400 dark:border-blue-800"
        >
          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          Running
        </Badge>
      );
  }
}
