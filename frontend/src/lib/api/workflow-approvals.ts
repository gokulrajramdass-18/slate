/**
 * Workflow Approval API Client
 */

import { apiClient } from './client';

export interface WorkflowApproval {
  id: string;
  workflow_id: string;
  execution_id: string;
  node_id: string;
  approval_prompt: string;
  approval_options: string[];
  required_approvers?: string[];
  input_data?: Record<string, any>;
  status: 'pending' | 'approved' | 'rejected' | 'timed_out';
  response?: string;
  comment?: string;
  approved_by?: string;
  timeout_seconds?: number;
  timeout_action?: string;
  timeout_at?: string;
  created: string;
  responded_at?: string;
}

export interface RespondToApprovalRequest {
  response: string;
  comment?: string;
}

export const workflowApprovalsApi = {
  /**
   * Get approval inbox
   */
  async getInbox(status?: string): Promise<WorkflowApproval[]> {
    const response = await apiClient.get('/workflow-approvals/inbox', {
      params: status ? { status_filter: status } : undefined
    });
    return response.data;
  },

  /**
   * Get approval by ID
   */
  async get(id: string): Promise<WorkflowApproval> {
    const response = await apiClient.get(`/workflow-approvals/${id}`);
    return response.data;
  },

  /**
   * Respond to an approval
   */
  async respond(id: string, data: RespondToApprovalRequest): Promise<WorkflowApproval> {
    const response = await apiClient.post(`/workflow-approvals/${id}/respond`, data);
    return response.data;
  },

  /**
   * Get approvals for an execution
   */
  async getByExecution(executionId: string): Promise<WorkflowApproval[]> {
    const response = await apiClient.get(`/workflow-approvals/executions/${executionId}`);
    return response.data;
  },

  /**
   * Get time remaining for approval timeout
   */
  getTimeRemaining(approval: WorkflowApproval): number | null {
    if (!approval.timeout_at) return null;

    const timeoutDate = new Date(approval.timeout_at);
    const now = new Date();
    const remaining = timeoutDate.getTime() - now.getTime();

    return remaining > 0 ? remaining : 0;
  },

  /**
   * Format time remaining as human-readable string
   */
  formatTimeRemaining(milliseconds: number): string {
    if (milliseconds === 0) return 'Expired';

    const seconds = Math.floor(milliseconds / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else {
      return `${seconds}s`;
    }
  },
};
