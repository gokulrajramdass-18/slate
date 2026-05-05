/**
 * Actions API Client
 *
 * Provides type-safe API client for actions management
 */

import { apiClient } from './client';

// Types
export interface ActionCreate {
  name: string;
  description?: string;
  action_type: 'webhook' | 'email' | 'hana_operation' | 'workflow_trigger';
  endpoint?: string;
  method?: string;
  auth_type?: 'none' | 'basic' | 'bearer' | 'api_key' | 'oauth2_client';
  auth_config?: Record<string, any>;
  headers?: Record<string, string>;
  query_params?: Record<string, any>;
  body_template?: Record<string, any>;
  condition_expression?: string;
  retry_policy?: {
    max_retries?: number;
    backoff?: 'exponential' | 'linear';
    initial_delay?: number;
  };
}

export interface ActionUpdate extends Partial<ActionCreate> {
  is_active?: boolean;
}

export interface ActionResponse {
  id: string;
  name: string;
  description?: string;
  action_type: string;
  endpoint?: string;
  method: string;
  auth_type?: string;
  headers: Record<string, string>;
  query_params: Record<string, any>;
  body_template?: Record<string, any>;
  condition_expression?: string;
  retry_policy?: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_executed_at?: string;
  execution_count: number;
}

export interface ActionTestResponse {
  success: boolean;
  message: string;
  execution_time_ms?: number;
  output_data?: Record<string, any>;
  error_message?: string;
  condition_met?: boolean;
  condition_details?: Record<string, any>;
}

export interface ActionExecutionRequest {
  context: Record<string, any>;
  user_id: string;
  orchestration_id?: string;
  chat_session_id?: string;
  trigger_event?: string;
}

export interface ActionExecutionResponse {
  execution_id: string;
  action_id: string;
  status: string;
  condition_met?: boolean;
  output_data?: Record<string, any>;
  error_message?: string;
  execution_time_ms?: number;
  created_at: string;
  completed_at?: string;
}

export interface ActionExecutionDetail {
  id: string;
  action_id: string;
  action_name: string;
  orchestration_id?: string;
  chat_session_id?: string;
  user_id: string;
  status: string;
  trigger_event: string;
  input_data?: Record<string, any>;
  output_data?: Record<string, any>;
  error_message?: string;
  condition_met?: boolean;
  condition_details?: Record<string, any>;
  execution_time_ms?: number;
  retry_count: number;
  created_at: string;
  completed_at?: string;
}

export interface ActionStats {
  action_id: string;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  skipped_executions: number;
  success_rate: number;
  average_execution_time_ms?: number;
  last_execution?: string;
  last_execution_status?: string;
}

// API Client
export const actionsApi = {
  /**
   * List all actions
   */
  async list(params?: {
    action_type?: string;
    is_active?: boolean;
  }): Promise<ActionResponse[]> {
    const queryParams = new URLSearchParams();
    if (params?.action_type) queryParams.append('action_type', params.action_type);
    if (params?.is_active !== undefined) queryParams.append('is_active', String(params.is_active));

    const query = queryParams.toString();
    const { data } = await apiClient.get(`/actions${query ? `?${query}` : ''}`);
    return data;
  },

  /**
   * Get a specific action
   */
  async get(id: string): Promise<ActionResponse> {
    const { data } = await apiClient.get(`/actions/${id}`);
    return data;
  },

  /**
   * Create a new action
   */
  async create(data: ActionCreate): Promise<ActionResponse> {
    const { data: response } = await apiClient.post('/actions', data);
    return response;
  },

  /**
   * Update an action
   */
  async update(id: string, data: ActionUpdate): Promise<ActionResponse> {
    const { data: response } = await apiClient.put(`/actions/${id}`, data);
    return response;
  },

  /**
   * Delete an action
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/actions/${id}`);
  },

  /**
   * Test an action configuration without saving
   */
  async testConfig(data: ActionCreate, userId: string): Promise<ActionTestResponse> {
    const { data: response } = await apiClient.post('/actions/test', data, {
      headers: { 'X-User-ID': userId },
    });
    return response;
  },

  /**
   * Test a saved action
   */
  async test(id: string, userId: string = 'test-user'): Promise<ActionTestResponse> {
    const { data } = await apiClient.post(`/actions/${id}/test`, {}, {
      headers: { 'X-User-ID': userId },
    });
    return data;
  },

  /**
   * Execute an action manually
   */
  async execute(id: string, request: ActionExecutionRequest): Promise<ActionExecutionResponse> {
    const { data } = await apiClient.post(`/actions/${id}/execute`, request);
    return data;
  },

  /**
   * Get execution history for an action
   */
  async getExecutions(
    id: string,
    params?: {
      limit?: number;
      offset?: number;
      status_filter?: string;
    }
  ): Promise<ActionExecutionDetail[]> {
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.append('limit', String(params.limit));
    if (params?.offset) queryParams.append('offset', String(params.offset));
    if (params?.status_filter) queryParams.append('status_filter', params.status_filter);

    const query = queryParams.toString();
    const { data } = await apiClient.get(`/actions/${id}/executions${query ? `?${query}` : ''}`);
    return data;
  },

  /**
   * Get a specific execution
   */
  async getExecution(actionId: string, executionId: string): Promise<ActionExecutionDetail> {
    const { data } = await apiClient.get(`/actions/${actionId}/executions/${executionId}`);
    return data;
  },

  /**
   * Get execution statistics for an action
   */
  async getStats(id: string): Promise<ActionStats> {
    const { data } = await apiClient.get(`/actions/${id}/stats`);
    return data;
  },
};

// Orchestration Actions API
export interface ActionBindingCreate {
  action_id: string;
  trigger_condition: 'on_start' | 'on_completion' | 'on_failure' | 'on_phase_change' | 'always';
  phase_filter?: string[];
  execution_order?: number;
}

export interface ActionBindingUpdate {
  trigger_condition?: string;
  phase_filter?: string[];
  execution_order?: number;
  is_active?: boolean;
}

export interface ActionBindingResponse {
  id: string;
  schedule_id?: string;
  orchestration_id?: string;
  action_id: string;
  action_name: string;
  action_type: string;
  trigger_condition: string;
  phase_filter?: string[];
  execution_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export const orchestrationActionsApi = {
  /**
   * Bind an action to a schedule
   */
  async bindToSchedule(
    scheduleId: string,
    binding: ActionBindingCreate
  ): Promise<ActionBindingResponse> {
    const { data } = await apiClient.post(`/orchestration/schedules/${scheduleId}/actions`, binding);
    return data;
  },

  /**
   * List actions bound to a schedule
   */
  async listScheduleActions(
    scheduleId: string,
    isActive?: boolean
  ): Promise<ActionBindingResponse[]> {
    const query = isActive !== undefined ? `?is_active=${isActive}` : '';
    const { data } = await apiClient.get(`/orchestration/schedules/${scheduleId}/actions${query}`);
    return data;
  },

  /**
   * Get a specific binding
   */
  async getScheduleAction(
    scheduleId: string,
    bindingId: string
  ): Promise<ActionBindingResponse> {
    const { data } = await apiClient.get(`/orchestration/schedules/${scheduleId}/actions/${bindingId}`);
    return data;
  },

  /**
   * Update a binding
   */
  async updateScheduleAction(
    scheduleId: string,
    bindingId: string,
    data: ActionBindingUpdate
  ): Promise<ActionBindingResponse> {
    const { data: response } = await apiClient.put(`/orchestration/schedules/${scheduleId}/actions/${bindingId}`, data);
    return response;
  },

  /**
   * Delete a binding
   */
  async deleteScheduleAction(scheduleId: string, bindingId: string): Promise<void> {
    await apiClient.delete(`/orchestration/schedules/${scheduleId}/actions/${bindingId}`);
  },

  /**
   * Bind an action to an orchestration
   */
  async bindToOrchestration(
    orchestrationId: string,
    binding: ActionBindingCreate
  ): Promise<ActionBindingResponse> {
    const { data } = await apiClient.post(`/orchestration/orchestrations/${orchestrationId}/actions`, binding);
    return data;
  },

  /**
   * List actions bound to an orchestration
   */
  async listOrchestrationActions(
    orchestrationId: string,
    isActive?: boolean
  ): Promise<ActionBindingResponse[]> {
    const query = isActive !== undefined ? `?is_active=${isActive}` : '';
    const { data } = await apiClient.get(`/orchestration/orchestrations/${orchestrationId}/actions${query}`);
    return data;
  },

  /**
   * List all bindings with filters
   */
  async listAllBindings(params?: {
    action_id?: string;
    trigger_condition?: string;
    is_active?: boolean;
  }): Promise<ActionBindingResponse[]> {
    const queryParams = new URLSearchParams();
    if (params?.action_id) queryParams.append('action_id', params.action_id);
    if (params?.trigger_condition) queryParams.append('trigger_condition', params.trigger_condition);
    if (params?.is_active !== undefined) queryParams.append('is_active', String(params.is_active));

    const query = queryParams.toString();
    const { data } = await apiClient.get(`/orchestration/actions/bindings${query ? `?${query}` : ''}`);
    return data;
  },
};
