import { apiClient } from "./client";
import type { Model, Credential } from "@/lib/types";

export const modelsApi = {
  // List all configured models
  list: async (type?: "language" | "embedding" | "speech_to_text" | "text_to_speech"): Promise<Model[]> => {
    const params = type ? { type } : undefined;
    const { data } = await apiClient.get("/models", { params });
    return data;
  },

  // List available models (configured and active)
  listAvailable: async (): Promise<{ models: Model[] }> => {
    const { data } = await apiClient.get("/models");
    // Filter to only active models
    const activeModels = Array.isArray(data) ? data.filter((m: any) => m.is_active) : [];
    return { models: activeModels };
  },

  // Get available models (from providers)
  available: async (): Promise<
    Array<{
      provider: string;
      models: Array<{
        name: string;
        type: string;
        description?: string;
      }>;
    }>
  > => {
    const { data } = await apiClient.get("/models/available");
    return data;
  },

  // Test model
  test: async (modelId: string): Promise<{
    success: boolean;
    message: string;
    latency_ms?: number;
  }> => {
    const { data } = await apiClient.post(`/models/${modelId}/test`);
    return data;
  },

  // Get/update defaults
  getDefaults: async (): Promise<{
    language_model_id?: string;
    embedding_model_id?: string;
    tts_model_id?: string;
    stt_model_id?: string;
  }> => {
    const { data } = await apiClient.get("/models/defaults");
    return data;
  },

  updateDefaults: async (defaults: {
    language_model_id?: string;
    embedding_model_id?: string;
    tts_model_id?: string;
    stt_model_id?: string;
  }): Promise<void> => {
    await apiClient.put("/models/defaults", defaults);
  },

  // Get usage stats
  getUsage: async (): Promise<{
    total_requests: number;
    total_tokens: number;
    by_model: Record<string, { requests: number; tokens: number }>;
  }> => {
    const { data } = await apiClient.get("/models/usage");
    return data;
  },
};

export const credentialsApi = {
  // List credentials
  list: async (): Promise<Credential[]> => {
    const { data } = await apiClient.get("/credentials");
    return data;
  },

  // Create credential
  create: async (credential: Omit<Credential, "id" | "created" | "updated">): Promise<Credential> => {
    const { data } = await apiClient.post("/credentials", credential);
    return data;
  },

  // Update credential
  update: async (id: string, credential: Partial<Credential>): Promise<Credential> => {
    const { data } = await apiClient.put(`/credentials/${id}`, credential);
    return data;
  },

  // Delete credential
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/credentials/${id}`);
  },

  // Test credential
  test: async (id: string): Promise<{
    success: boolean;
    message: string;
  }> => {
    const { data } = await apiClient.post(`/credentials/${id}/test`);
    return data;
  },

  // Test connection before saving
  testConnection: async (params: {
    provider: string;
    model_name: string;
    model_type: string;
    api_key: string;
    base_url?: string;
  }): Promise<{
    success: boolean;
    message: string;
    latency_ms?: number;
  }> => {
    const { data } = await apiClient.post("/credentials/test-connection", params);
    return data;
  },

  // Get models from LiteLLM endpoint
  getLiteLLMModels: async (baseUrl?: string, apiKey?: string): Promise<{
    success: boolean;
    base_url: string;
    models: Array<{
      id: string;
      name: string;
      type: string;
      provider: string;
    }>;
    count: number;
    error?: string;
  }> => {
    const params: any = {};
    if (baseUrl) params.base_url = baseUrl;
    if (apiKey) params.api_key = apiKey;
    // Use public endpoint in models router (no auth required)
    const { data } = await apiClient.get("/models/litellm/models", { params });
    return data;
  },

  // Test SAP AI Core connection
  testSAPAICore: async (params: {
    auth_url: string;
    api_url: string;
    client_id: string;
    client_secret: string;
    resource_group?: string;
    identity_zone?: string;
    identityzoneid?: string;
  }): Promise<{
    success: boolean;
    message: string;
    resource_group?: string;
  }> => {
    const { data } = await apiClient.post("/models/sap-ai-core/test-connection", params);
    return data;
  },

  // Get models from SAP AI Core
  getSAPAICoreModels: async (params: {
    auth_url: string;
    api_url: string;
    client_id: string;
    client_secret: string;
    resource_group?: string;
    identity_zone?: string;
    identityzoneid?: string;
  }): Promise<{
    success: boolean;
    resource_group?: string;
    models: Array<{
      id: string;
      name: string;
      deployment_id: string;
      scenario_id: string;
      status: string;
      model_name: string;
      model_version?: string;
      type: string;
      capabilities: string[];
      created_at?: string;
      provider: string;
    }>;
    count: number;
  }> => {
    const { data } = await apiClient.post("/models/sap-ai-core/discover", params);
    return data;
  },

  // Bulk import all SAP AI Core models as credentials
  importSAPAICoreModels: async (params: {
    auth_url: string;
    api_url: string;
    client_id: string;
    client_secret: string;
    resource_group?: string;
    identity_zone?: string;
    identityzoneid?: string;
  }): Promise<{
    success: boolean;
    message: string;
    imported_count: number;
    models: Array<any>;
    errors: Array<any>;
  }> => {
    const { data } = await apiClient.post("/credentials/import-sap-ai-core", params);
    return data;
  },

  // Auto-import SAP AI Core models (no credentials needed - uses standalone API)
  importSAPAICoreModelsAuto: async (): Promise<{
    success: boolean;
    message: string;
    imported_count: number;
    models: Array<any>;
    errors: Array<any>;
  }> => {
    const { data } = await apiClient.post("/credentials/import-sap-ai-core-auto");
    return data;
  },
};

export const embeddingApi = {
  // Get embedding configuration
  getConfig: async (): Promise<{
    model_id: string;
    chunk_size: number;
    chunk_overlap: number;
    batch_size: number;
  }> => {
    const { data } = await apiClient.get("/embedding/config");
    return data;
  },

  // Update embedding configuration
  updateConfig: async (config: {
    model_id?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    batch_size?: number;
  }): Promise<void> => {
    await apiClient.put("/embedding/config", config);
  },

  // Rebuild all embeddings
  rebuild: async (): Promise<{
    task_id: string;
    message: string;
  }> => {
    const { data } = await apiClient.post("/embedding/rebuild");
    return data;
  },
};
