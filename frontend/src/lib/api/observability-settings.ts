import { apiClient } from './client';

export interface LangfuseConfig {
  enabled: boolean;
  public_key: string;
  secret_key: string;
  host: string;
}

export interface MLFlowConfig {
  enabled: boolean;
  tracking_uri: string;
  experiment_name: string;
  username: string;
  password: string;
}

export interface ObservabilityOptions {
  trace_level: 'debug' | 'info' | 'warn' | 'error';
  log_llm_calls: boolean;
  log_tool_calls: boolean;
  log_agent_steps: boolean;
}

export interface ObservabilityConfig {
  provider: 'none' | 'langfuse' | 'mlflow' | 'both';
  langfuse: LangfuseConfig;
  mlflow: MLFlowConfig;
  options: ObservabilityOptions;
}

export interface ConnectionTestRequest {
  provider: 'langfuse' | 'mlflow';
}

export interface ConnectionTestResponse {
  success: boolean;
  message: string;
  details?: Record<string, any>;
}

export interface ProviderStatus {
  enabled: boolean;
  connected: boolean;
  tracking_uri?: string;
  experiment_name?: string;
  last_trace_at?: string;
  last_run_at?: string;
  total_traces?: number;
  total_runs?: number;
  storage_size_mb?: number;
  error?: string;
}

export interface ObservabilityStatusResponse {
  langfuse: ProviderStatus;
  mlflow: ProviderStatus;
}

export const observabilitySettingsApi = {
  async get(): Promise<ObservabilityConfig> {
    const response = await apiClient.get('/admin/observability/settings');
    return response.data;
  },

  async update(config: Partial<ObservabilityConfig>): Promise<ObservabilityConfig> {
    const response = await apiClient.put('/admin/observability/settings', config);
    return response.data;
  },

  async testConnection(provider: 'langfuse' | 'mlflow'): Promise<ConnectionTestResponse> {
    const response = await apiClient.post('/admin/observability/test-connection', { provider });
    return response.data;
  },

  async getStatus(): Promise<ObservabilityStatusResponse> {
    const response = await apiClient.get('/admin/observability/status');
    return response.data;
  },
};
