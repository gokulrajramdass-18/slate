/**
 * Workspace Tasks API Client
 *
 * Handles API calls for workspace task management
 */

import { apiClient } from './client';

// ============================================================================
// Types
// ============================================================================

export interface WorkspaceTask {
  id: string;
  plan_id: string;
  phase_name: string;
  name: string;
  description?: string;
  assigned_agent_id?: string;
  status: 'pending' | 'in_progress' | 'completed' | 'blocked' | 'failed';
  estimated_duration?: number; // minutes
  dependencies: string[];
  required_tools: string[];
  required_sources: string[];
  started_at?: string;
  completed_at?: string;
  error?: string; // Error message if failed
  created: string;
  updated: string;
}

export interface UpdateTaskRequest {
  status?: 'pending' | 'in_progress' | 'completed' | 'blocked';
  assigned_agent_id?: string;
}

export interface PhaseProgress {
  phase_name: string;
  total_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  pending_tasks: number;
  estimated_duration: number; // minutes
  completion_percentage: number;
}

export interface WorkspaceProgress {
  workspace_id: string;
  total_tasks: number;
  completed_tasks: number;
  in_progress_tasks: number;
  pending_tasks: number;
  blocked_tasks: number;
  overall_completion_percentage: number;
  current_phase?: string;
  phases: PhaseProgress[];
  estimated_total_duration: number; // minutes
  estimated_remaining_duration: number; // minutes
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * List all tasks for a workspace
 */
export async function listWorkspaceTasks(
  workspaceId: string,
  filters?: {
    phase?: string;
    status?: string;
  }
): Promise<WorkspaceTask[]> {
  const params: Record<string, string> = {};
  if (filters?.phase) params.phase = filters.phase;
  if (filters?.status) params.status = filters.status;

  const response = await apiClient.get<WorkspaceTask[]>(
    `/workspaces/${workspaceId}/tasks`,
    { params }
  );
  return response.data;
}

/**
 * Get a specific task
 */
export async function getWorkspaceTask(
  workspaceId: string,
  taskId: string
): Promise<WorkspaceTask> {
  const response = await apiClient.get<WorkspaceTask>(
    `/workspaces/${workspaceId}/tasks/${taskId}`
  );
  return response.data;
}

/**
 * Update a task (status, assignment, etc.)
 */
export async function updateWorkspaceTask(
  workspaceId: string,
  taskId: string,
  update: UpdateTaskRequest
): Promise<WorkspaceTask> {
  const response = await apiClient.put<WorkspaceTask>(
    `/workspaces/${workspaceId}/tasks/${taskId}`,
    update
  );
  return response.data;
}

/**
 * Start a task (set status to in_progress)
 */
export async function startTask(
  workspaceId: string,
  taskId: string
): Promise<WorkspaceTask> {
  return updateWorkspaceTask(workspaceId, taskId, { status: 'in_progress' });
}

/**
 * Complete a task (set status to completed)
 */
export async function completeTask(
  workspaceId: string,
  taskId: string
): Promise<WorkspaceTask> {
  return updateWorkspaceTask(workspaceId, taskId, { status: 'completed' });
}

/**
 * Block a task (set status to blocked)
 */
export async function blockTask(
  workspaceId: string,
  taskId: string
): Promise<WorkspaceTask> {
  return updateWorkspaceTask(workspaceId, taskId, { status: 'blocked' });
}

/**
 * Get workspace progress
 */
export async function getWorkspaceProgress(
  workspaceId: string
): Promise<WorkspaceProgress> {
  const response = await apiClient.get<WorkspaceProgress>(
    `/workspaces/${workspaceId}/progress`
  );
  return response.data;
}

/**
 * Regenerate all tasks in a workspace (reset to pending and delete old notes)
 */
export async function regenerateWorkspaceTasks(
  workspaceId: string
): Promise<{
  message: string;
  workspace_id: string;
  tasks_reset: number;
  notes_deleted: number;
}> {
  const response = await apiClient.post(
    `/workspaces/${workspaceId}/tasks/regenerate`
  );
  return response.data;
}

/**
 * Manually start/retry a specific task
 *
 * Resets the task to pending and queues it for execution.
 * Use this when a task is stuck or failed.
 */
export async function startTaskManually(
  workspaceId: string,
  taskId: string
): Promise<{
  message: string;
  task_id: string;
  workspace_id: string;
  previous_status: string;
  new_status: string;
}> {
  const response = await apiClient.post(
    `/workspaces/${workspaceId}/tasks/${taskId}/start`
  );
  return response.data;
}

/**
 * Cleanup stuck tasks (tasks in_progress for too long)
 *
 * Finds and resets tasks that have been stuck in 'in_progress' status
 * for longer than the specified timeout.
 */
export async function cleanupStuckTasks(
  workspaceId: string,
  timeoutMinutes: number = 30
): Promise<{
  message: string;
  tasks_reset: number;
  task_names?: string[];
}> {
  const response = await apiClient.post(
    `/workspaces/${workspaceId}/tasks/cleanup-stuck`,
    null,
    { params: { timeout_minutes: timeoutMinutes } }
  );
  return response.data;
}

/**
 * Finalize workspace and generate summary
 *
 * Manually triggers workspace finalization when all tasks are completed.
 * Generates the AI-powered consolidated summary (final deliverable).
 *
 * Note: This can take 30-60 seconds as it uses AI to analyze all task results.
 */
export async function finalizeWorkspace(
  workspaceId: string
): Promise<{
  message: string;
  workspace_id: string;
  tasks_completed: number;
  tasks_failed: number;
  status: string;
}> {
  const response = await apiClient.post(
    `/workspaces/${workspaceId}/tasks/finalize`,
    {},
    { timeout: 120000 } // 2 minute timeout for AI summary generation
  );
  return response.data;
}

/**
 * Execute workspace plan (manually trigger task execution)
 *
 * Triggers autonomous execution of all workspace plan tasks using the orchestrator.
 * Used for manually created workspaces to start task execution.
 *
 * Note: Execution runs in the background and can take several minutes.
 */
export async function executeWorkspacePlan(
  workspaceId: string
): Promise<{
  message: string;
  workspace_id: string;
  plan_id: string;
  task_count: number;
  status: string;
}> {
  const response = await apiClient.post(
    `/workspaces/${workspaceId}/tasks/execute`,
    {}
  );
  return response.data;
}
