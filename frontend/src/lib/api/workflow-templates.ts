/**
 * Workflow Template API Client
 */

import { apiClient } from './client';

export interface TemplateParameter {
  name: string;
  type: string;
  description?: string;
  default_value?: any;
  required: boolean;
  options?: string[];
}

export interface WorkflowTemplate {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  category?: string;
  source_workflow_id?: string;
  graph_json: string;
  parameters?: TemplateParameter[];
  version: number;
  is_public: boolean;
  tags?: string[];
  usage_count: number;
  created: string;
  updated: string;
}

export interface CreateTemplateRequest {
  workflow_id: string;
  name: string;
  description?: string;
  parameters: TemplateParameter[];
  category?: string;
  is_public: boolean;
  tags?: string[];
}

export interface InstantiateTemplateRequest {
  parameters: Record<string, any>;
  name?: string;
}

export interface ExecuteTemplateRequest {
  parameters: Record<string, any>;
  input_data?: Record<string, any>;
}

export interface TemplateExecutionResult {
  workflow_id: string;
  execution_id: string;
  status: string;
  final_output?: any;
  error?: string;
}

export const workflowTemplatesApi = {
  /**
   * Create a template from a workflow
   */
  async create(data: CreateTemplateRequest): Promise<WorkflowTemplate> {
    const response = await apiClient.post('/workflow-templates', data);
    return response.data;
  },

  /**
   * Get user's templates
   */
  async list(): Promise<WorkflowTemplate[]> {
    const response = await apiClient.get('/workflow-templates');
    return response.data;
  },

  /**
   * Get public templates
   */
  async listPublic(category?: string): Promise<WorkflowTemplate[]> {
    const response = await apiClient.get('/workflow-templates/public', {
      params: category ? { category } : undefined
    });
    return response.data;
  },

  /**
   * Get template by ID
   */
  async get(id: string): Promise<WorkflowTemplate> {
    const response = await apiClient.get(`/workflow-templates/${id}`);
    return response.data;
  },

  /**
   * Update template
   */
  async update(id: string, data: Partial<CreateTemplateRequest>): Promise<WorkflowTemplate> {
    const response = await apiClient.put(`/workflow-templates/${id}`, data);
    return response.data;
  },

  /**
   * Delete template
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/workflow-templates/${id}`);
  },

  /**
   * Instantiate a template (create workflow from template)
   */
  async instantiate(id: string, data: InstantiateTemplateRequest): Promise<{ workflow_id: string }> {
    const response = await apiClient.post(`/workflow-templates/${id}/instantiate`, data);
    return response.data;
  },

  /**
   * Execute a template (instantiate and execute)
   */
  async execute(id: string, data: ExecuteTemplateRequest): Promise<TemplateExecutionResult> {
    const response = await apiClient.post(`/workflow-templates/${id}/execute`, data);
    return response.data;
  },

  /**
   * Get template execution history
   */
  async getExecutions(id: string): Promise<any[]> {
    const response = await apiClient.get(`/workflow-templates/${id}/executions`);
    return response.data;
  },
};
