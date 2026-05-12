import { apiClient } from "./client";

export interface EvaluationDataset {
  id: string;
  name: string;
  description?: string;
  agent_id?: string;
  test_case_count: number;
  file_name?: string;
  file_format?: string;
  criteria: string[];
  scoring_method: string;
  created: string;
  updated: string;
  created_by?: string;
}

export interface EvaluationRun {
  id: string;
  dataset_id: string;
  agent_id: string;
  dataset_name?: string;
  agent_name?: string;
  run_name?: string;
  model_override?: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  avg_score?: number;
  avg_latency_ms?: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created: string;
  created_by?: string;
}

export interface EvaluationResult {
  id: string;
  run_id: string;
  test_case_id: string;
  input_prompt: string;
  expected_output?: string;
  agent_output: string;
  execution_time_ms: number;
  passed: boolean;
  overall_score?: number;
  criteria_scores?: Record<string, number>;
  similarity_score?: number;
  exact_match?: boolean;
  feedback?: string;
  judge_reasoning?: string;
  error_occurred: boolean;
  error_message?: string;
  category?: string;
  tags?: string[];
  created: string;
}

export interface EvaluationSummary {
  agent_id: string;
  total_runs: number;
  avg_pass_rate: number;
  avg_score: number;
  recent_runs: EvaluationRun[];
}

export const evaluationApi = {
  // Datasets
  listDatasets: async (agentId?: string): Promise<EvaluationDataset[]> => {
    const params = agentId ? { agent_id: agentId } : {};
    const { data } = await apiClient.get("/agent-evaluations/datasets", { params });
    return data;
  },

  getDataset: async (datasetId: string): Promise<EvaluationDataset> => {
    const { data } = await apiClient.get(`/agent-evaluations/datasets/${datasetId}`);
    return data;
  },

  createDataset: async (dataset: {
    name: string;
    description?: string;
    agent_id?: string;
    criteria?: string[];
    scoring_method?: string;
  }): Promise<EvaluationDataset> => {
    const { data } = await apiClient.post("/agent-evaluations/datasets", dataset);
    return data;
  },

  uploadDataset: async (
    formData: FormData
  ): Promise<EvaluationDataset> => {
    const { data } = await apiClient.post("/agent-evaluations/datasets/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },

  deleteDataset: async (datasetId: string): Promise<void> => {
    await apiClient.delete(`/agent-evaluations/datasets/${datasetId}`);
  },

  getTestCases: async (datasetId: string, category?: string) => {
    const params = category ? { category } : {};
    const { data } = await apiClient.get(
      `/agent-evaluations/datasets/${datasetId}/test-cases`,
      { params }
    );
    return data;
  },

  // Evaluation Runs
  createRun: async (run: {
    dataset_id: string;
    agent_id: string;
    run_name?: string;
    model_override?: string;
    config_override?: Record<string, any>;
  }): Promise<EvaluationRun> => {
    const { data } = await apiClient.post("/agent-evaluations/runs", run);
    return data;
  },

  listRuns: async (agentId?: string, datasetId?: string): Promise<EvaluationRun[]> => {
    const params: any = {};
    if (agentId) params.agent_id = agentId;
    if (datasetId) params.dataset_id = datasetId;
    const { data } = await apiClient.get("/agent-evaluations/runs", { params });
    return data.runs;
  },

  getRun: async (runId: string): Promise<EvaluationRun> => {
    const { data } = await apiClient.get(`/agent-evaluations/runs/${runId}`);
    return data;
  },

  getResults: async (
    runId: string,
    passedOnly?: boolean,
    failedOnly?: boolean
  ): Promise<EvaluationResult[]> => {
    const params: any = {};
    if (passedOnly) params.passed_only = true;
    if (failedOnly) params.failed_only = true;
    const { data } = await apiClient.get(`/agent-evaluations/runs/${runId}/results`, { params });
    return data;
  },

  deleteRun: async (runId: string): Promise<void> => {
    await apiClient.delete(`/agent-evaluations/runs/${runId}`);
  },

  // Analytics
  getAgentSummary: async (agentId: string): Promise<EvaluationSummary> => {
    const { data } = await apiClient.get(`/agent-evaluations/agents/${agentId}/evaluation-summary`);
    return data;
  },
};
