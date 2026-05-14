"use client";

import { useDashboardStats } from "@/lib/hooks/use-dashboard-stats";
import { DailyBriefCard } from "@/components/daily-brief/DailyBriefCard";
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

  console.log("🏠 Dashboard Page Rendering", { stats, isLoading, error });

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
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-8 p-6 md:p-8">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-red-600 mx-auto mb-4" />
            <p className="text-lg font-semibold text-red-600">Failed to load dashboard</p>
            <p className="text-sm text-muted-foreground mt-2">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="space-y-8 p-6 md:p-8">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-yellow-600 mx-auto mb-4" />
            <p className="text-lg font-semibold">No dashboard data available</p>
          </div>
        </div>
      </div>
    );
  }

  // Simple dashboard display without complex components for now
  return (
    <div className="space-y-8 p-6 md:p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">Welcome back! Here's your overview</p>
        </div>
        {isConnectedLive && (
          <Badge variant="outline" className="flex items-center gap-2">
            <Activity className="h-3 w-3 animate-pulse text-green-500" />
            <span>Live</span>
          </Badge>
        )}
      </div>

      {/* Daily Brief */}
      <DailyBriefCard />

      {/* Hero Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <HeroStatCard
          title="Pending Approvals"
          value={stats?.hero_metrics?.pending_approvals || 0}
          icon={AlertCircle}
          trend={null}
          color="red"
        />
        <HeroStatCard
          title="Active Agents"
          value={stats?.hero_metrics?.active_agents || 0}
          icon={Users}
          trend={null}
          color="blue"
        />
        <HeroStatCard
          title="Scheduled Today"
          value={stats?.hero_metrics?.scheduled_runs_today || 0}
          icon={Calendar}
          trend={null}
          color="purple"
        />
        <HeroStatCard
          title="AI Usage Today"
          value={stats?.hero_metrics?.ai_usage_today || 0}
          icon={Sparkles}
          trend={null}
          color="green"
        />
      </div>

      {/* Simple stats grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <SectionCard title="Workflows" icon={Workflow}>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total</span>
              <span className="text-2xl font-bold">{stats?.workflows?.total || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Active</span>
              <span className="text-lg font-semibold">{stats?.workflows?.active || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Success Rate</span>
              <span className="text-lg font-semibold">{stats?.workflows?.success_rate || 0}%</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Workspaces" icon={BookOpen}>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Total</span>
              <span className="text-2xl font-bold">{stats?.workspaces?.total || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Active</span>
              <span className="text-lg font-semibold">{stats?.workspaces?.active || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Sources</span>
              <span className="text-lg font-semibold">{stats?.workspaces?.total_sources || 0}</span>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="System" icon={Zap}>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Database</span>
              <span className="text-sm font-semibold">{stats?.system?.db_type || 'N/A'}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Records</span>
              <span className="text-lg font-semibold">{(stats?.system?.total_records || 0).toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Uptime</span>
              <span className="text-sm font-semibold">{Math.floor(stats?.system?.uptime_hours || 0)}h</span>
            </div>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
