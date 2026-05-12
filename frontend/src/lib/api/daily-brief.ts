import { apiClient } from "./client";

// ============================================================================
// Types
// ============================================================================

export interface ExecutionItem {
  id: string;
  workflow_id: string;
  workflow_name: string | null;
  status: string;
  started_at: string;
  completed_at: string | null;
  triggered_by: string;
}

export interface ExecutionsSummary {
  total: number;
  completed: number;
  failed: number;
  success_rate: number;
  recent_items: ExecutionItem[];
}

export interface ApprovalItem {
  id: string;
  workflow_name: string;
  approval_prompt: string;
  created_at: string;
  timeout_at: string | null;
  action_url: string;
}

export interface ScheduleItem {
  id: string;
  workflow_name: string;
  next_run_at: string;
  schedule_type: string;
  cron_expression: string | null;
}

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  message: string;
  category: string;
  priority: string;
  created_at: string;
  action_url: string | null;
}

export interface NotificationsSummary {
  total: number;
  unread: number;
  by_category: Record<string, number>;
  recent_items: NotificationItem[];
}

export interface OrchestrationItem {
  id: string;
  goal: string;
  status: string;
  current_phase: string | null;
  progress: number;
  created_at: string;
  updated_at: string;
}

export interface OrchestrationsSummary {
  total: number;
  completed: number;
  failed: number;
  recent_items: OrchestrationItem[];
}

export interface DailyBriefData {
  user_name: string;
  last_login: string | null;
  current_time: string;
  time_since_login: string;
  executions_since_login?: ExecutionsSummary;
  pending_approvals?: ApprovalItem[];
  upcoming_schedules?: ScheduleItem[];
  notifications?: NotificationsSummary;
  orchestrations?: OrchestrationsSummary;
  ai_summary?: string;
}

export interface DailyBriefConfig {
  enabled: boolean;
  ai_enabled: boolean;
  sources: string[];
  max_items: number;
}

export interface DailyBriefConfigUpdate {
  enabled?: boolean;
  ai_enabled?: boolean;
  sources?: string[];
  max_items?: number;
}

// ============================================================================
// API Client
// ============================================================================

export const dailyBriefApi = {
  /**
   * Get daily brief for current user
   */
  get: async (): Promise<DailyBriefData> => {
    const { data } = await apiClient.get("/daily-brief");
    return data;
  },

  /**
   * Get daily brief configuration (admin only)
   */
  getSettings: async (): Promise<DailyBriefConfig> => {
    const { data } = await apiClient.get("/admin/daily-brief/settings");
    return data;
  },

  /**
   * Update daily brief configuration (admin only)
   */
  updateSettings: async (
    updates: DailyBriefConfigUpdate
  ): Promise<DailyBriefConfig> => {
    const { data } = await apiClient.put("/admin/daily-brief/settings", updates);
    return data;
  },
};
