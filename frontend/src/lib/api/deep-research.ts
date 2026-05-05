/**
 * Deep Research API Client
 *
 * Handles all API calls for deep research mode
 */

import { apiClient } from './client';

export type ResearchPhase =
  | 'initializing'
  | 'analyzing_query'
  | 'decomposing'
  | 'searching'
  | 'synthesizing'
  | 'finalizing'
  | 'complete'
  | 'error';

export interface DeepResearchRequest {
  message: string;
  max_iterations?: number;
  search_strategies?: string[];
}

export interface DeepResearchJobResponse {
  job_id: string;
  status: string;
  estimated_time: number;
  message: string;
}

export interface KeyFinding {
  finding: string;
  supporting_evidence: string;
  citations: number[];
}

export interface Citation {
  number: number;
  source: string;
}

export interface DeepResearchResult {
  job_id: string;
  status: string;
  phase: ResearchPhase;
  final_report: string;
  key_findings: KeyFinding[];
  citations: Citation[];
  search_results_count: number;
  sub_questions_count: number;
  duration_seconds: number;
  created_at: string;
}

export interface DeepResearchStatusResponse {
  job_id: string;
  status: string;
  phase?: ResearchPhase;
  progress: number;
  message?: string;
  result?: DeepResearchResult;
  error?: string;
}

export const deepResearchApi = {
  /**
   * Start a deep research job
   */
  start: async (
    sessionId: string,
    request: DeepResearchRequest
  ): Promise<DeepResearchJobResponse> => {
    const response = await apiClient.post(
      `/chat/deep-research/sessions/${sessionId}/start`,
      request
    );
    return response.data;
  },

  /**
   * Get research job status
   */
  getStatus: async (jobId: string): Promise<DeepResearchStatusResponse> => {
    const response = await apiClient.get(`/chat/deep-research/jobs/${jobId}`);
    return response.data;
  },

  /**
   * Cancel a running research job
   */
  cancel: async (jobId: string): Promise<void> => {
    await apiClient.delete(`/chat/deep-research/jobs/${jobId}`);
  },

  /**
   * Create EventSource for streaming progress updates
   */
  streamProgress: (jobId: string): EventSource => {
    return new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5055/api'}/chat/deep-research/jobs/${jobId}/stream`
    );
  },
};
