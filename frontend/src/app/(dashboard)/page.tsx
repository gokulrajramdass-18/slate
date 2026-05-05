"use client";

import { useDashboardStats } from "@/lib/hooks/use-dashboard-stats";
import { HeroStatCard } from "@/components/dashboard/HeroStatCard";
import { SectionCard } from "@/components/dashboard/SectionCard";
import { MiniChart } from "@/components/dashboard/MiniChart";
import { RecentItemList } from "@/components/dashboard/RecentItemList";
import { NextScheduleList } from "@/components/dashboard/NextScheduleList";
import { ActivityTimeline } from "@/components/dashboard/ActivityTimeline";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertCircle,
  Users,
  Calendar,
  Sparkles,
  Workflow,
  CheckCircle,
  Clock,
  BookOpen,
  FileText,
  Globe,
  Zap,
  Activity,
} from "lucide-react";
import {
  BarChart as RechartsBar,
  Bar,
  PieChart as RechartsPie,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

export default function DashboardPage() {
  const { data: stats, isLoading, error, isConnectedLive } = useDashboardStats();

  if (isLoading) {
    return (
      <div className="space-y-8 p-6 md:p-8">
        <div className="flex items-center justify-between">
          <Skeleton className="h-10 w-48" />
          <Skeleton className="h-6 w-24" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-96" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex items-center justify-center h-96 p-6 md:p-8">
        <div className="text-center">
          <p className="text-lg font-semibold text-red-600">Failed to load dashboard</p>
          <p className="text-sm text-muted-foreground mt-2">
            {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      </div>
    );
  }

  // Prepare chart data
  const triggerData = Object.entries(stats.workflows.by_trigger).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value,
  }));

  const roleData = Object.entries(stats.agents.agents_by_role).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value,
  }));

  const sourceData = Object.entries(stats.workspaces.sources_by_type).map(([key, value]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    value,
  }));

  const COLORS = ["#3b82f6", "#8b5cf6", "#ec4899", "#f59e0b", "#10b981", "#06b6d4"];

  // Generate mock activity events (in real app, these would come from backend)
  const activityEvents = [
    ...stats.workflows.recent_executions.slice(0, 3).map((exec: any) => ({
      id: exec.id,
      type: "workflow" as const,
      title: `Workflow "${exec.workflow_name}" ${exec.status}`,
      description: `Execution ${exec.status}`,
      timestamp: exec.started_at || new Date().toISOString(),
      status: exec.status === "completed" ? "success" as const : exec.status === "failed" ? "failed" as const : "pending" as const,
    })),
    ...stats.approvals.pending_items.slice(0, 2).map((approval: any) => ({
      id: approval.id,
      type: "approval" as const,
      title: `Approval needed for "${approval.workflow_name}"`,
      description: approval.approval_prompt,
      timestamp: approval.created || new Date().toISOString(),
      status: "pending" as const,
    })),
  ].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  return (
    <div className="space-y-8 pb-12 p-6 md:p-8">
      {/* Header with Live Indicator */}
      <div className="animate-fade-in-up">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
              Analytics Dashboard
            </h1>
            <p className="text-gray-500 dark:text-gray-400 mt-1">
              Real-time platform insights and analytics
            </p>
          </div>
          {isConnectedLive && (
            <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300 flex items-center gap-2">
              <div className="w-2 h-2 bg-green-600 rounded-full animate-pulse" />
              Live
            </Badge>
          )}
        </div>
      </div>

      {/* Hero Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="animate-fade-in-up" style={{ animationDelay: "0ms" }}>
          <HeroStatCard
            title="Pending Approvals"
            value={stats.hero_metrics.pending_approvals}
            icon={AlertCircle}
            color="text-orange-600"
            bgColor="bg-orange-100 dark:bg-orange-900"
            href="/approvals"
            highlight={true}
          />
        </div>
        <div className="animate-fade-in-up" style={{ animationDelay: "100ms" }}>
          <HeroStatCard
            title="Active Agents"
            value={stats.hero_metrics.active_agents}
            icon={Users}
            color="text-purple-600"
            bgColor="bg-purple-100 dark:bg-purple-900"
            href="/agents"
          />
        </div>
        <div className="animate-fade-in-up" style={{ animationDelay: "200ms" }}>
          <HeroStatCard
            title="Scheduled Runs Today"
            value={stats.hero_metrics.scheduled_runs_today}
            icon={Calendar}
            color="text-green-600"
            bgColor="bg-green-100 dark:bg-green-900"
            href="/orchestration"
          />
        </div>
        <div className="animate-fade-in-up" style={{ animationDelay: "300ms" }}>
          <HeroStatCard
            title="AI Usage Today"
            value={stats.hero_metrics.ai_usage_today}
            icon={Sparkles}
            color="text-pink-600"
            bgColor="bg-pink-100 dark:bg-pink-900"
            href="/tools"
          />
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Workflow Health */}
        <div className="animate-fade-in-up" style={{ animationDelay: "400ms" }}>
          <SectionCard title="Workflow Health" icon={Workflow} href="/workflows">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Total Workflows</span>
                <span className="text-2xl font-bold">{stats.workflows.total}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Active</span>
                <span className="text-lg font-semibold text-blue-600">{stats.workflows.active}</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Success Rate</span>
                  <span className="text-sm font-semibold">{stats.workflows.success_rate}%</span>
                </div>
                <Progress value={stats.workflows.success_rate} className="h-2" />
              </div>
              {triggerData.length > 0 && (
                <MiniChart title="Executions by Trigger (7 days)">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsBar data={triggerData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#3b82f6" />
                    </RechartsBar>
                  </ResponsiveContainer>
                </MiniChart>
              )}
            </div>
          </SectionCard>
        </div>

        {/* Agent Activity */}
        <div className="animate-fade-in-up" style={{ animationDelay: "500ms" }}>
          <SectionCard title="Agent Activity" icon={Users} href="/agents">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Active Teams</span>
                <span className="text-2xl font-bold">{stats.agents.active_teams}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Total Agents</span>
                <span className="text-lg font-semibold text-purple-600">{stats.agents.total_agents}</span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Task Completion</span>
                  <span className="text-sm font-semibold">{stats.agents.task_completion_rate}%</span>
                </div>
                <Progress value={stats.agents.task_completion_rate} className="h-2" />
              </div>
              {roleData.length > 0 && (
                <MiniChart title="Agents by Role">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsPie>
                      <Pie
                        data={roleData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={(entry) => entry.name}
                        outerRadius={60}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {roleData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </RechartsPie>
                  </ResponsiveContainer>
                </MiniChart>
              )}
            </div>
          </SectionCard>
        </div>

        {/* Approvals - Highlighted if pending */}
        <div className="animate-fade-in-up" style={{ animationDelay: "600ms" }}>
          <SectionCard
            title="Pending Approvals"
            icon={AlertCircle}
            href="/approvals"
          >
            <div className="space-y-4">
              {stats.approvals.pending_count > 0 ? (
                <>
                  <div className="text-center py-4">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-orange-100 dark:bg-orange-900 mb-2">
                      <span className="text-3xl font-bold text-orange-600 dark:text-orange-400">
                        {stats.approvals.pending_count}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {stats.approvals.pending_count === 1 ? "approval" : "approvals"} waiting
                    </p>
                  </div>
                  <RecentItemList
                    items={stats.approvals.pending_items.map((item: any) => ({
                      id: item.id,
                      title: item.workflow_name || "Unnamed Workflow",
                      status: "pending",
                      created_at: item.created,
                      href: `/approvals`,
                    }))}
                  />
                </>
              ) : (
                <div className="text-center py-8">
                  <CheckCircle className="w-12 h-12 text-green-600 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    All caught up! No pending approvals.
                  </p>
                </div>
              )}
              <div className="flex justify-between items-center pt-2 border-t">
                <span className="text-xs text-muted-foreground">Avg Response Time</span>
                <span className="text-xs font-semibold">
                  {Math.round(stats.approvals.avg_response_time_minutes)} min
                </span>
              </div>
            </div>
          </SectionCard>
        </div>

        {/* Schedules */}
        <div className="animate-fade-in-up" style={{ animationDelay: "700ms" }}>
          <SectionCard
            title="Schedule Overview"
            icon={Calendar}
            href="/orchestration"
          >
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Enabled</p>
                  <p className="text-2xl font-bold text-green-600">{stats.schedules.enabled}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Runs Today</p>
                  <p className="text-2xl font-bold text-blue-600">{stats.schedules.runs_today}</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-muted-foreground">Success Rate Today</span>
                  <span className="text-sm font-semibold">
                    {stats.schedules.runs_today > 0
                      ? Math.round((stats.schedules.successful_runs_today / stats.schedules.runs_today) * 100)
                      : 0}
                    %
                  </span>
                </div>
                <Progress
                  value={
                    stats.schedules.runs_today > 0
                      ? (stats.schedules.successful_runs_today / stats.schedules.runs_today) * 100
                      : 0
                  }
                  className="h-2"
                />
              </div>
              <div className="pt-2 border-t">
                <p className="text-sm font-medium mb-2">Next Scheduled Runs</p>
                <NextScheduleList schedules={stats.schedules.next_runs} />
              </div>
            </div>
          </SectionCard>
        </div>

        {/* Workspaces & Sources */}
        <div className="animate-fade-in-up" style={{ animationDelay: "800ms" }}>
          <SectionCard title="Data & Sources" icon={BookOpen} href="/workspaces">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Workspaces</p>
                  <p className="text-2xl font-bold">{stats.workspaces.total}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Sources</p>
                  <p className="text-2xl font-bold text-teal-600">{stats.workspaces.total_sources}</p>
                </div>
              </div>
              {sourceData.length > 0 && (
                <MiniChart title="Sources by Type">
                  <ResponsiveContainer width="100%" height="100%">
                    <RechartsPie>
                      <Pie
                        data={sourceData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={(entry) => `${entry.name}: ${entry.value}`}
                        outerRadius={60}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {sourceData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </RechartsPie>
                  </ResponsiveContainer>
                </MiniChart>
              )}
            </div>
          </SectionCard>
        </div>

        {/* AI Usage */}
        <div className="animate-fade-in-up" style={{ animationDelay: "900ms" }}>
          <SectionCard title="AI Usage Insights" icon={Sparkles} href="/tools">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Tool Calls</p>
                  <p className="text-2xl font-bold text-pink-600">{stats.ai_usage.tool_calls_today}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Chat Messages</p>
                  <p className="text-2xl font-bold text-purple-600">{stats.ai_usage.chat_messages_today}</p>
                </div>
              </div>
              <div className="pt-2 border-t">
                <p className="text-sm font-medium mb-2">Top Tools (Last 7 Days)</p>
                <div className="space-y-2">
                  {stats.ai_usage.top_tools.slice(0, 5).map((tool: any) => (
                    <div key={tool.tool_id} className="flex justify-between items-center">
                      <span className="text-sm truncate">{tool.tool_id}</span>
                      <Badge variant="secondary" className="text-xs">
                        {tool.count}
                      </Badge>
                    </div>
                  ))}
                  {stats.ai_usage.top_tools.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No tool usage yet
                    </p>
                  )}
                </div>
              </div>
              <div className="flex justify-between items-center pt-2 border-t">
                <span className="text-xs text-muted-foreground">Avg Execution Time</span>
                <span className="text-xs font-semibold">
                  {Math.round(stats.ai_usage.avg_execution_time_ms)} ms
                </span>
              </div>
            </div>
          </SectionCard>
        </div>
      </div>

      {/* Recent Activity Timeline - Full Width */}
      <div className="animate-fade-in-up" style={{ animationDelay: "1000ms" }}>
        <SectionCard title="Recent Activity" icon={Activity}>
          <ActivityTimeline events={activityEvents} maxItems={10} />
        </SectionCard>
      </div>

      {/* System Stats Footer */}
      <div className="animate-fade-in-up" style={{ animationDelay: "1100ms" }}>
        <div className="flex items-center justify-between text-sm text-muted-foreground border-t pt-4">
          <div className="flex items-center gap-4">
            <span>Database: {stats.system.db_type.toUpperCase()}</span>
            <span>Records: {stats.system.total_records.toLocaleString()}</span>
            <span>Uptime: {stats.system.uptime_hours.toFixed(1)}h</span>
          </div>
          <span className="text-xs">
            Last updated: {new Date().toLocaleTimeString()}
          </span>
        </div>
      </div>
    </div>
  );
}
