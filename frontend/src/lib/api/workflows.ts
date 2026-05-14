/**
 * Workflows API Client
 *
 * Provides API methods for managing visual workflow graphs.
 */

import { apiClient } from './client';

// ============================================================================
// Types
// ============================================================================

export interface Position {
  x: number;
  y: number;
}

export interface NodeConfig {
  // LLM Node
  model_name?: string;
  system_prompt?: string;
  temperature?: number;

  // Tool Node
  tool_name?: string;
  tool_args?: Record<string, any>;

  // Conditional Node
  condition_type?: 'equals' | 'contains' | 'greater_than' | 'less_than';
  field_path?: string;
  comparison_value?: any;
  true_edge_id?: string;
  false_edge_id?: string;

  // Agent Node
  agent_type?: 'standalone' | 'team';
  agent_id?: string;
  agent_name?: string;
  prompt?: string;  // NEW: Prompt template with {{variable}} substitution
}

export interface WorkflowNode {
  id: string;
  type: 'input' | 'llm' | 'tool' | 'conditional' | 'output';
  label: string;
  position: Position;
  config: NodeConfig;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  condition_result?: boolean;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  entry_node_id: string;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  graph: WorkflowGraph;
  created_by: string;
  is_active: boolean;
  tags: string[];
  created_at?: string;
  updated_at?: string;
}

export interface WorkflowCreate {
  name: string;
  description?: string;
  graph: WorkflowGraph;
  created_by: string;
  tags?: string[];
}

export interface WorkflowUpdate {
  name?: string;
  description?: string;
  graph?: WorkflowGraph;
  is_active?: boolean;
  tags?: string[];
}

export interface NodeExecutionState {
  node_id: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  input_data?: any;
  output_data?: any;
  error?: string;
}

export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  started_at: string;
  completed_at?: string;
  node_states: Record<string, NodeExecutionState>;
  final_output?: any;
  error?: string;
  triggered_by: 'manual' | 'cron' | 'event' | 'dependency';
}

export interface EventTrigger {
  event_type: string;
  filters?: Record<string, any>;
}

export type ScheduleType = 'cron' | 'event' | 'dependency' | 'manual';

export interface WorkflowSchedule {
  id: string;
  workflow_id: string;
  schedule_type: ScheduleType;
  cron_expression?: string;
  event_trigger?: EventTrigger;
  upstream_workflow_id?: string;
  enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ScheduleCreate {
  schedule_type: ScheduleType;
  cron_expression?: string;
  event_trigger?: EventTrigger;
  upstream_workflow_id?: string;
  enabled?: boolean;
}

export interface ScheduleUpdate {
  cron_expression?: string;
  event_trigger?: EventTrigger;
  upstream_workflow_id?: string;
  enabled?: boolean;
}

export interface SchedulerJob {
  id: string;
  name: string;
  next_run_time?: string;
  last_run_time?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'paused';
  trigger?: string;
  execution_count?: number;
}

// ============================================================================
// API Methods
// ============================================================================

/**
 * Workflow CRUD operations
 */
export const workflowsApi = {
  /**
   * List all workflows
   */
  async list(limit = 50, offset = 0): Promise<Workflow[]> {
    const response = await apiClient.get('/workflows', {
      params: { limit, offset },
    });
    return response.data.workflows || response.data;
  },

  /**
   * Get workflow by ID
   */
  async get(id: string): Promise<Workflow> {
    const response = await apiClient.get(`/workflows/${id}`);
    return response.data.workflow || response.data;
  },

  /**
   * Create new workflow
   */
  async create(data: WorkflowCreate): Promise<any> {
    const response = await apiClient.post('/workflows', data);
    return response.data;
  },

  /**
   * Update workflow
   */
  async update(id: string, data: WorkflowUpdate): Promise<Workflow> {
    const response = await apiClient.put(`/workflows/${id}`, data);
    return response.data;
  },

  /**
   * Delete workflow
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/workflows/${id}`);
  },

  /**
   * Execute workflow
   */
  async execute(id: string, inputData?: any): Promise<WorkflowExecution> {
    const response = await apiClient.post(`/workflows/${id}/execute`, {
      input_data: inputData,
    });

    // Backend returns execution data directly in the response
    // Convert from backend format if needed
    const data = response.data;

    // If the response has success/execution_id format, convert it
    if (data.execution_id && data.node_states) {
      return {
        id: data.execution_id,
        workflow_id: data.workflow_id,
        status: data.status,
        started_at: data.started_at,
        completed_at: data.completed_at,
        node_states: data.node_states,
        final_output: data.final_output,
        error: data.error,
        triggered_by: 'manual',
      };
    }

    return data;
  },

  /**
   * Execute workflow with streaming (SSE)
   */
  executeStreaming(id: string, inputData?: any): EventSource {
    const params = new URLSearchParams();
    if (inputData) {
      params.append('input_data', JSON.stringify(inputData));
    }

    const url = `${import.meta.env.VITE_API_URL}/workflows/${id}/execute?stream=true&${params.toString()}`;
    return new EventSource(url);
  },

  /**
   * Get execution history
   */
  async getExecutions(workflowId: string, limit = 50): Promise<WorkflowExecution[]> {
    const response = await apiClient.get(`/workflows/${workflowId}/executions`, {
      params: { limit },
    });
    return response.data.executions || response.data;
  },

  /**
   * Get specific execution
   */
  async getExecution(workflowId: string, executionId: string): Promise<WorkflowExecution> {
    const response = await apiClient.get(`/workflows/${workflowId}/executions/${executionId}`);
    return response.data.execution || response.data;
  },

  /**
   * Manually trigger workflow
   */
  async trigger(id: string, inputData?: any): Promise<WorkflowExecution> {
    const response = await apiClient.post(`/workflows/${id}/trigger`, {
      input_data: inputData,
    });
    return response.data;
  },

  /**
   * Get schedules for workflow
   */
  async getSchedules(workflowId: string): Promise<WorkflowSchedule[]> {
    const response = await apiClient.get(`/workflows/${workflowId}/schedules`);
    return response.data.schedules || response.data;
  },

  /**
   * Create schedule
   */
  async createSchedule(workflowId: string, data: ScheduleCreate): Promise<WorkflowSchedule> {
    const response = await apiClient.post(`/workflows/${workflowId}/schedules`, data);
    return response.data.schedule || response.data;
  },

  /**
   * Update schedule
   */
  async updateSchedule(
    workflowId: string,
    scheduleId: string,
    data: ScheduleUpdate | { enabled: boolean }
  ): Promise<WorkflowSchedule> {
    const response = await apiClient.put(
      `/workflows/${workflowId}/schedules/${scheduleId}`,
      data
    );
    return response.data.schedule || response.data;
  },

  /**
   * Delete schedule
   */
  async deleteSchedule(workflowId: string, scheduleId: string): Promise<void> {
    await apiClient.delete(`/workflows/${workflowId}/schedules/${scheduleId}`);
  },
};

/**
 * Schedule operations
 */
export const schedulesApi = {
  /**
   * List schedules for workflow
   */
  async list(workflowId: string): Promise<WorkflowSchedule[]> {
    const response = await apiClient.get(`/workflows/${workflowId}/schedules`);
    return response.data;
  },

  /**
   * Get schedule by ID
   */
  async get(workflowId: string, scheduleId: string): Promise<WorkflowSchedule> {
    const response = await apiClient.get(`/workflows/${workflowId}/schedules/${scheduleId}`);
    return response.data;
  },

  /**
   * Create schedule
   */
  async create(workflowId: string, data: ScheduleCreate): Promise<WorkflowSchedule> {
    const response = await apiClient.post(`/workflows/${workflowId}/schedules`, data);
    return response.data;
  },

  /**
   * Update schedule
   */
  async update(
    workflowId: string,
    scheduleId: string,
    data: ScheduleUpdate
  ): Promise<WorkflowSchedule> {
    const response = await apiClient.put(
      `/workflows/${workflowId}/schedules/${scheduleId}`,
      data
    );
    return response.data;
  },

  /**
   * Delete schedule
   */
  async delete(workflowId: string, scheduleId: string): Promise<void> {
    await apiClient.delete(`/workflows/${workflowId}/schedules/${scheduleId}`);
  },
};

/**
 * Scheduler operations
 */
export const schedulerApi = {
  /**
   * List all scheduler jobs
   */
  async listJobs(): Promise<SchedulerJob[]> {
    const response = await apiClient.get('/workflows/scheduler/jobs');
    return response.data.jobs || response.data || [];
  },

  /**
   * Get job status
   */
  async getJobStatus(scheduleId: string): Promise<SchedulerJob> {
    const response = await apiClient.get(`/workflows/scheduler/jobs/${scheduleId}`);
    return response.data;
  },

  /**
   * Publish event to trigger workflows
   */
  async publishEvent(eventType: string, eventData?: any): Promise<void> {
    await apiClient.post(`/workflows/events/${eventType}`, {
      event_data: eventData,
    });
  },
};

/**
 * Tool schema discovery operations
 */
export interface InputFieldDefinition {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  default_value?: any;
  description?: string;
}

export interface ToolSchema {
  tool_name: string;
  tool_description: string;
  fields: InputFieldDefinition[];
  raw_schema: any;
}

export interface ToolInfo {
  tool_name: string;
  description: string;
  has_schema: boolean;
}

export const toolSchemaApi = {
  /**
   * List all available tools
   */
  async listTools(): Promise<{ tools: ToolInfo[] }> {
    const response = await apiClient.get('/workflows/tools');
    return response.data;
  },

  /**
   * Get schema for a specific tool
   */
  async getToolSchema(toolName: string): Promise<ToolSchema> {
    const response = await apiClient.get(`/workflows/tools/${toolName}/schema`);
    return response.data;
  },
};
