"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart } from "@/components/chat/generative-ui/charts/BarChart";
import { PieChart } from "@/components/chat/generative-ui/charts/PieChart";
import { LineChart } from "@/components/chat/generative-ui/charts/LineChart";
import { Loader2 } from "lucide-react";

interface PhaseData {
  phase: string;
  completion: number;
  completed: number;
  in_progress: number;
  pending: number;
  total: number;
}

interface StatusData {
  status: string;
  count: number;
}

interface TimelineData {
  date: string;
  completed: number;
}

interface WorkloadData {
  agent: string;
  tasks: number;
}

interface ChartData {
  workspace_id: string;
  phases: PhaseData[];
  status_distribution: StatusData[];
  timeline: TimelineData[];
  agent_workload: WorkloadData[];
}

interface WorkspaceProgressChartsProps {
  workspaceId: string;
}

export function WorkspaceProgressCharts({ workspaceId }: WorkspaceProgressChartsProps) {
  const [data, setData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchChartData = async () => {
      try {
        setLoading(true);
        const response = await fetch(`http://localhost:5055/api/workspaces/${workspaceId}/charts`);

        if (!response.ok) {
          throw new Error("Failed to fetch chart data");
        }

        const chartData = await response.json();
        setData(chartData);
        setError(null);
      } catch (err) {
        console.error("Error fetching chart data:", err);
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    fetchChartData();

    // Refresh every 10 seconds to show live progress
    const interval = setInterval(fetchChartData, 10000);

    return () => clearInterval(interval);
  }, [workspaceId]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Progress Visualizations</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Progress Visualizations</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-64 text-muted-foreground">
          {error || "No data available"}
        </CardContent>
      </Card>
    );
  }

  const hasPhases = data.phases.length > 0;
  const hasStatus = data.status_distribution.length > 0;
  const hasTimeline = data.timeline.length > 0;
  const hasWorkload = data.agent_workload.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Progress Visualizations</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Phase Completion Bar Chart */}
          {hasPhases && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Phase Completion</h3>
              <BarChart
                data={data.phases as any}
                xKey="phase"
                yKeys={["completion"]}
                title=""
              />
              <div className="text-xs text-muted-foreground text-center">
                Completion percentage by phase
              </div>
            </div>
          )}

          {/* Task Status Pie Chart */}
          {hasStatus && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Task Status Distribution</h3>
              <PieChart
                data={data.status_distribution as any}
                xKey="status"
                yKeys={["count"]}
                title=""
              />
              <div className="text-xs text-muted-foreground text-center">
                Tasks by current status
              </div>
            </div>
          )}

          {/* Progress Timeline Chart */}
          {hasTimeline && data.timeline.length > 1 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Completion Timeline</h3>
              <LineChart
                data={data.timeline as any}
                xKey="date"
                yKeys={["completed"]}
                title=""
              />
              <div className="text-xs text-muted-foreground text-center">
                Tasks completed over time
              </div>
            </div>
          )}

          {/* Agent Workload Distribution */}
          {hasWorkload && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Agent Workload</h3>
              <PieChart
                data={data.agent_workload as any}
                xKey="agent"
                yKeys={["tasks"]}
                title=""
              />
              <div className="text-xs text-muted-foreground text-center">
                Tasks assigned per agent
              </div>
            </div>
          )}
        </div>

        {/* Summary Stats */}
        <div className="mt-6 pt-6 border-t grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold">
              {data.phases.reduce((sum, p) => sum + p.completed, 0)}
            </div>
            <div className="text-xs text-muted-foreground">Completed</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">
              {data.phases.reduce((sum, p) => sum + p.in_progress, 0)}
            </div>
            <div className="text-xs text-muted-foreground">In Progress</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">
              {data.phases.reduce((sum, p) => sum + p.pending, 0)}
            </div>
            <div className="text-xs text-muted-foreground">Pending</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">
              {data.phases.reduce((sum, p) => sum + p.total, 0)}
            </div>
            <div className="text-xs text-muted-foreground">Total Tasks</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
