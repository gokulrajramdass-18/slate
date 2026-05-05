/**
 * Guided Workspace Creation API Client
 *
 * Handles all API calls for the guided workspace creation wizard.
 */

import { apiClient } from './client';

// ============================================================================
// Types
// ============================================================================

export interface GuidedSession {
  id: string;
  user_id: string;
  goal: string;
  status: 'draft' | 'completed' | 'abandoned' | 'expired';
  current_step?: string;
  analysis?: any;
  clarification_answers?: any;
  discovered_resources?: any;
  selected_resources?: any;
  plan?: any;
  workspace_id?: string;
  created: string;
  updated: string;
  expires_at?: string;
}

export interface GoalAnalysisRequest {
  goal: string;
  context?: Record<string, any>;
}

export interface GoalAnalysisResponse {
  session_id: string;
  analysis: {
    intent: string;
    domain: string;
    complexity: 'simple' | 'moderate' | 'complex';
    keywords: string[];
    requirements: string[];
  };
  needs_clarification: boolean;
  questions?: Array<{
    question: string;
    type: 'multiple_choice' | 'text' | 'date_range';
    options?: string[];
    help_text?: string;
  }>;
}

export interface ClarificationRequest {
  session_id: string;
  answers: Record<string, any>;
}

export interface ClarificationResponse {
  session_id: string;
  refined_analysis: {
    intent: string;
    domain: string;
    complexity: 'simple' | 'moderate' | 'complex';
    keywords: string[];
    requirements: string[];
  };
}

export interface ResourceDiscoveryRequest {
  session_id: string;
  source_limit?: number;
  tool_limit?: number;
  agent_limit?: number;
  team_limit?: number;
}

export interface ResourceDiscoveryResponse {
  data_sources: Array<{
    id: string;
    name?: string;
    title?: string;
    description?: string;
    source_type?: string;
    relevance_score: number;
    relevance_reason?: string;
  }>;
  tools: Array<{
    id: string;
    name: string;
    description?: string;
    relevance_score: number;
    relevance_reason?: string;
  }>;
  agents: Array<{
    id: string;
    name: string;
    description?: string;
    capabilities?: string[];
    relevance_score: number;
    relevance_reason?: string;
  }>;
  teams: Array<{
    id: string;
    name: string;
    description?: string;
    member_count?: number;
    relevance_score: number;
    relevance_reason?: string;
  }>;
}

export interface PlanGenerationRequest {
  session_id: string;
  selected_resources: {
    source_ids: string[];
    tool_ids: string[];
    agent_ids: string[];
    team_ids: string[];
  };
}

export interface PlanGenerationResponse {
  phases: Array<{
    phase_number?: number;
    name?: string;
    phase?: string;
    description?: string;
    tasks: Array<{
      name: string;
      description?: string;
      type?: string;
      assigned_agent_id?: string;
      estimated_minutes?: number;
      estimated_duration?: number;
      dependencies?: string[];
      required_tools?: string[];
      required_sources?: string[];
    }>;
    estimated_duration?: number;
    dependencies?: number[];
  }>;
  agent_assignments?: Record<string, string>;
  total_duration: number;
  collaboration_graph?: {
    nodes: Array<{
      id: string;
      type: 'agent' | 'team';
      name: string;
    }>;
    edges: Array<{
      from: string;
      to: string;
      relationship: 'depends_on' | 'collaborates_with' | 'shares_data';
    }>;
  };
  recommendations?: string[];
}

export interface WorkspaceCreationRequest {
  session_id: string;
  name: string;
  goal: string;
  selected_resources: {
    data_sources: Array<{ id: string }>;
    tools: Array<{ id: string }>;
    agents: Array<{ id: string }>;
    teams: Array<{ id: string }>;
  };
  plan: {
    phases: any[];
    agent_assignments?: any;
    estimated_total_duration?: number;
  };
  auto_start?: boolean;
}

export interface WorkspaceCreationResponse {
  workspace_id: string;
  status: string;
  initialization_tasks?: string[];
  next_steps?: string[];
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Analyze a goal and create a new guided workspace session
 */
export async function analyzeGoal(
  request: GoalAnalysisRequest
): Promise<GoalAnalysisResponse> {
  const response = await apiClient.post<GoalAnalysisResponse>(
    '/workspaces/guided/analyze-goal',
    request
  );
  return response.data;
}

/**
 * Submit clarification answers and refine the analysis
 */
export async function submitClarification(
  request: ClarificationRequest
): Promise<ClarificationResponse> {
  const response = await apiClient.post<ClarificationResponse>(
    '/workspaces/guided/clarify',
    request
  );
  return response.data;
}

/**
 * Discover relevant resources based on the analysis
 */
export async function discoverResources(
  request: ResourceDiscoveryRequest
): Promise<ResourceDiscoveryResponse> {
  const response = await apiClient.post<ResourceDiscoveryResponse>(
    '/workspaces/guided/discover-resources',
    request
  );
  return response.data;
}

/**
 * Generate a task plan based on selected resources
 */
export async function generatePlan(
  request: PlanGenerationRequest
): Promise<PlanGenerationResponse> {
  const response = await apiClient.post<PlanGenerationResponse>(
    '/workspaces/guided/generate-plan',
    request
  );
  return response.data;
}

/**
 * Create the workspace with all selected resources and plan
 */
export async function createWorkspace(
  request: WorkspaceCreationRequest
): Promise<WorkspaceCreationResponse> {
  const response = await apiClient.post<WorkspaceCreationResponse>(
    '/workspaces/guided/create',
    request
  );
  return response.data;
}

/**
 * Get a guided workspace session by ID
 */
export async function getSession(sessionId: string): Promise<GuidedSession> {
  const response = await apiClient.get<GuidedSession>(
    `/workspaces/guided/sessions/${sessionId}`
  );
  return response.data;
}

/**
 * Update a guided workspace session
 */
export async function updateSession(
  sessionId: string,
  updates: Partial<GuidedSession>
): Promise<GuidedSession> {
  const response = await apiClient.put<GuidedSession>(
    `/workspaces/guided/sessions/${sessionId}`,
    updates
  );
  return response.data;
}

/**
 * Delete a guided workspace session
 */
export async function deleteSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/workspaces/guided/sessions/${sessionId}`);
}

/**
 * List guided workspace sessions for the current user
 */
export async function listSessions(status?: 'draft' | 'completed' | 'abandoned' | 'expired'): Promise<GuidedSession[]> {
  const params = status ? { session_status: status } : {};
  const response = await apiClient.get<GuidedSession[]>('/workspaces/guided/sessions', { params });
  return response.data;
}
