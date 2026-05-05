import { apiClient } from "./client";

export interface OrchestrationSchedule {
  id: string;
  user_id: string;
  goal?: string;
  template_id?: string;
  template_name?: string;
  parameters?: Record<string, any>;
  notebook_id?: string;
  schedule_type: "once" | "recurring";
  schedule_config: {
    datetime?: string;
    cron?: string;
  };
  next_run?: string;
  last_run?: string;
  status: "active" | "paused" | "completed" | "failed";
  execution_count: number;
  created_at: string;
  updated_at: string;
}

export interface ScheduleCreateRequest {
  // Mode 1: Goal-based
  goal?: string;

  // Mode 2: Template-based
  template_id?: string;
  parameters?: Record<string, any>;

  // Common fields
  notebook_id?: string;
  resources?: Record<string, any>;
  config?: Record<string, any>;

  // Schedule configuration
  schedule_type: "once" | "recurring";
  schedule_config: {
    datetime?: string;
    cron?: string;
  };
}

export interface ScheduleUpdateRequest {
  goal?: string;
  template_id?: string;
  parameters?: Record<string, any>;
  notebook_id?: string;
  resources?: Record<string, any>;
  config?: Record<string, any>;
  schedule_type?: "once" | "recurring";
  schedule_config?: {
    datetime?: string;
    cron?: string;
  };
  status?: "active" | "paused" | "completed" | "failed";
}

export interface ScheduleExecution {
  orchestration_id: string;
  workspace_instance_id?: string;
  workspace_name?: string;
  template_id?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export const schedulesApi = {
  // List schedules
  list: async (params?: {
    status?: string;
    template_id?: string;
    limit?: number;
  }): Promise<OrchestrationSchedule[]> => {
    const { data } = await apiClient.get("/orchestration-schedules", { params });
    return data;
  },

  // Get schedule details
  get: async (id: string): Promise<OrchestrationSchedule> => {
    const { data } = await apiClient.get(`/orchestration-schedules/${id}`);
    return data;
  },

  // Create schedule
  create: async (request: ScheduleCreateRequest): Promise<OrchestrationSchedule> => {
    const { data } = await apiClient.post("/orchestration-schedules", request);
    return data;
  },

  // Update schedule
  update: async (id: string, request: ScheduleUpdateRequest): Promise<OrchestrationSchedule> => {
    const { data } = await apiClient.put(`/orchestration-schedules/${id}`, request);
    return data;
  },

  // Delete schedule
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/orchestration-schedules/${id}`);
  },

  // Pause schedule
  pause: async (id: string): Promise<OrchestrationSchedule> => {
    const { data } = await apiClient.post(`/orchestration-schedules/${id}/pause`);
    return data;
  },

  // Resume schedule
  resume: async (id: string): Promise<OrchestrationSchedule> => {
    const { data } = await apiClient.post(`/orchestration-schedules/${id}/resume`);
    return data;
  },

  // Get execution history
  getExecutions: async (id: string, limit?: number): Promise<ScheduleExecution[]> => {
    const { data } = await apiClient.get(`/orchestration-schedules/${id}/executions`, {
      params: { limit },
    });
    return data;
  },
};
