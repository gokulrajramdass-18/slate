import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useDashboardWebSocket } from "./use-dashboard-websocket";
import { useAuthStore } from "@/lib/stores/auth-store";
import { apiClient } from "@/lib/api/client";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:5055/api";

export interface DashboardStats {
  hero_metrics: {
    pending_approvals: number;
    active_agents: number;
    scheduled_runs_today: number;
    ai_usage_today: number;
  };
  workflows: {
    total: number;
    active: number;
    executions_last_7_days: number;
    success_rate: number;
    by_trigger: Record<string, number>;
    recent_executions: any[];
  };
  agents: {
    total_teams: number;
    active_teams: number;
    total_agents: number;
    agents_by_role: Record<string, number>;
    task_completion_rate: number;
    active_tasks: number;
    completed_tasks_today: number;
  };
  approvals: {
    pending_count: number;
    pending_items: any[];
    avg_response_time_minutes: number;
    approval_rate: number;
  };
  schedules: {
    total_schedules: number;
    enabled: number;
    disabled: number;
    next_runs: any[];
    runs_today: number;
    successful_runs_today: number;
  };
  workspaces: {
    total: number;
    active: number;
    archived: number;
    total_sources: number;
    sources_by_type: Record<string, number>;
  };
  microsites: {
    total: number;
    active: number;
    total_views: number;
    unique_users: number;
    most_viewed: any[];
  };
  ai_usage: {
    tool_calls_today: number;
    chat_messages_today: number;
    top_tools: any[];
    avg_execution_time_ms: number;
  };
  notifications: {
    unread_count: number;
    by_type: Record<string, number>;
  };
  system: {
    db_type: string;
    total_records: number;
    last_backup: string | null;
    uptime_hours: number;
  };
}

async function fetchDashboardStats(): Promise<DashboardStats> {
  const response = await apiClient.get('/dashboard/stats');
  return response.data;
}

export function useDashboardStats() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);

  // Initial fetch with polling fallback (30 seconds)
  const query = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: fetchDashboardStats,
    refetchInterval: 30000, // Fallback polling every 30 seconds
    staleTime: 25000, // Consider data stale after 25 seconds
    retry: 3,
  });

  // WebSocket for real-time updates
  const { isConnected } = useDashboardWebSocket({
    userId: user?.id || "",
    enabled: !!user?.id,
    onUpdate: (stats: DashboardStats) => {
      // Update React Query cache with fresh stats from WebSocket
      queryClient.setQueryData(["dashboard", "stats"], stats);
    },
  });

  return {
    ...query,
    isConnectedLive: isConnected,
  };
}
