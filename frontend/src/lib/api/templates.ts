import { apiClient } from "./client";

export interface WorkspaceTemplate {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  category?: string;
  source_workspace_id?: string;
  phase_count: number;
  task_count: number;
  parameter_count: number;
  version: number;
  is_public: boolean;
  tags: string[];
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface TemplateDetail extends WorkspaceTemplate {
  phases: TemplatePhase[];
  collaboration_graph: any;
  default_resources: any;
  parameters: TemplateParameter[];
}

export interface TemplatePhase {
  name: string;
  phase?: string;
  tasks: TemplateTask[];
}

export interface TemplateTask {
  name: string;
  description: string;
  assigned_agent_id?: string;
  estimated_duration?: number;
  dependencies?: string[];
  required_tools?: string[];
  required_sources?: string[];
}

export interface TemplateParameter {
  name: string;
  type: "string" | "number" | "date" | "boolean" | "select";
  description: string;
  default_value?: any;
  required: boolean;
  options?: string[];
}

export interface TemplateCreateRequest {
  workspace_id: string;
  name: string;
  description?: string;
  category?: string;
  parameters?: TemplateParameter[];
  is_public?: boolean;
  tags?: string[];
}

export interface TemplateUpdateRequest {
  name?: string;
  description?: string;
  category?: string;
  parameters?: TemplateParameter[];
  is_public?: boolean;
  tags?: string[];
}

export interface TemplateInstantiateRequest {
  parameters: Record<string, any>;
  workspace_name?: string;
}

export interface TemplateExecuteRequest {
  parameters: Record<string, any>;
  target_workspace_id?: string;
}

export interface TemplateExecuteResponse {
  execution_id: string;
  result_note_id: string;
  folder_id: string;
  target_workspace_id: string;
  note_title: string;
  message: string;
}

export interface TemplateExecution {
  execution_id: string;
  orchestration_id: string;  // Backward compatibility
  target_workspace_id: string;
  workspace_id: string;  // Backward compatibility
  workspace_name?: string;  // Enriched from workspace
  folder_id: string;
  parameters: Record<string, any>;
  result_note_id?: string;
  status: string;
  error?: string;
  current_phase?: string;
  progress: number;
  started_at?: string;
  executed_at?: string;  // For display (either completed_at or started_at)
  completed_at?: string;
  duration_ms?: number;
  duration_seconds?: number;  // Computed from duration_ms
  schedule_id?: string;
  user_id?: string;
}

export const templatesApi = {
  // List templates accessible to user
  list: async (params?: {
    category?: string;
    is_public?: boolean;
    limit?: number;
  }): Promise<WorkspaceTemplate[]> => {
    const { data } = await apiClient.get("/workspace-templates", { params });
    return data;
  },

  // List public templates (no auth required)
  listPublic: async (params?: {
    category?: string;
    limit?: number;
  }): Promise<WorkspaceTemplate[]> => {
    const { data } = await apiClient.get("/workspace-templates/public", { params });
    return data;
  },

  // Get template details
  get: async (id: string): Promise<TemplateDetail> => {
    const { data } = await apiClient.get(`/workspace-templates/${id}`);
    return data;
  },

  // Create template from workspace
  create: async (request: TemplateCreateRequest): Promise<WorkspaceTemplate> => {
    const { data } = await apiClient.post("/workspace-templates", request);
    return data;
  },

  // Update template
  update: async (id: string, request: TemplateUpdateRequest): Promise<WorkspaceTemplate> => {
    const { data } = await apiClient.put(`/workspace-templates/${id}`, request);
    return data;
  },

  // Delete template
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/workspace-templates/${id}`);
  },

  // Instantiate template manually (creates new workspace)
  instantiate: async (
    id: string,
    request: TemplateInstantiateRequest
  ): Promise<{ workspace_id: string; template_id: string; message: string }> => {
    const { data } = await apiClient.post(`/workspace-templates/${id}/clone`, request);
    return data;
  },

  // Execute template (stores results in workspace folder)
  execute: async (
    id: string,
    request: TemplateExecuteRequest
  ): Promise<TemplateExecuteResponse> => {
    const { data } = await apiClient.post(`/workspace-templates/${id}/execute`, request);
    return data;
  },

  // Get execution history for template
  getExecutions: async (id: string, limit?: number, status?: string): Promise<TemplateExecution[]> => {
    const { data } = await apiClient.get(`/workspace-templates/${id}/executions`, {
      params: { limit, status },
    });
    return data;
  },

  // Delete an execution (removes execution record, folder, and associated notes)
  deleteExecution: async (templateId: string, executionId: string): Promise<void> => {
    await apiClient.delete(`/workspace-templates/${templateId}/executions/${executionId}`);
  },
};
