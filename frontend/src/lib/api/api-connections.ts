/**
 * API Connections API Client
 */
import { apiClient } from "./client";

export interface APIConnection {
  id: string;
  name: string;
  description?: string;
  endpoint: string;
  auth_type: string;
  headers: Record<string, string>;
  method: string;
  query_params: Record<string, any>;
  request_body?: Record<string, any>;
  data_path?: string;
  id_field: string;
  content_fields: string[];
  created_at: string;
  updated_at: string;
  last_tested?: string;
  test_status?: string;
  test_message?: string;
}

export interface APIConnectionCreate {
  name: string;
  description?: string;
  endpoint: string;
  auth_type: string;
  auth_config?: Record<string, any>;
  headers?: Record<string, string>;
  method?: string;
  query_params?: Record<string, any>;
  request_body?: Record<string, any>;
  data_path?: string;
  id_field?: string;
  content_fields?: string[];
}

export interface APIConnectionTestResponse {
  success: boolean;
  message: string;
  preview?: any;
  record_count?: number;
}

export const apiConnectionsApi = {
  /**
   * List all API connections
   */
  list: async (): Promise<APIConnection[]> => {
    const { data } = await apiClient.get("/api-connections");
    return data;
  },

  /**
   * Get a specific API connection
   */
  get: async (connectionId: string): Promise<APIConnection> => {
    const { data } = await apiClient.get(`/api-connections/${connectionId}`);
    return data;
  },

  /**
   * Create a new API connection
   */
  create: async (connection: APIConnectionCreate): Promise<APIConnection> => {
    const { data } = await apiClient.post("/api-connections", connection);
    return data;
  },

  /**
   * Update an API connection
   */
  update: async (connectionId: string, connection: Partial<APIConnectionCreate>): Promise<APIConnection> => {
    const { data } = await apiClient.put(`/api-connections/${connectionId}`, connection);
    return data;
  },

  /**
   * Delete an API connection
   */
  delete: async (connectionId: string): Promise<void> => {
    await apiClient.delete(`/api-connections/${connectionId}`);
  },

  /**
   * Test a saved API connection
   */
  test: async (connectionId: string): Promise<APIConnectionTestResponse> => {
    const { data } = await apiClient.post(`/api-connections/${connectionId}/test`);
    return data;
  },

  /**
   * Test an API connection config without saving
   */
  testConfig: async (config: APIConnectionCreate): Promise<APIConnectionTestResponse> => {
    const { data } = await apiClient.post("/api-connections/test", config);
    return data;
  },

  /**
   * Fetch a preview of data from the API
   */
  fetchPreview: async (connectionId: string): Promise<any> => {
    const { data } = await apiClient.get(`/api-connections/${connectionId}/preview`);
    return data;
  },
};
