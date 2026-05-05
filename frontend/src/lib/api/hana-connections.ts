/**
 * HANA Connections API Client
 */

import { apiClient } from "./client";

export interface HANAConnection {
  id: string;
  name: string;
  host: string;
  port: number;
  database: string;
  user: string;
  encrypt: boolean;
  schema?: string;
  description?: string;
  created: string;
  updated: string;
}

export interface HANAConnectionCreate {
  name: string;
  host: string;
  port: number;
  database: string;
  user: string;
  password: string;
  encrypt: boolean;
  schema?: string;
  description?: string;
}

export interface HANAConnectionUpdate {
  name?: string;
  host?: string;
  port?: number;
  database?: string;
  user?: string;
  password?: string;
  encrypt?: boolean;
  schema?: string;
  description?: string;
}

export interface HANATestResponse {
  success: boolean;
  message: string;
  server_version?: string;
  latency_ms?: number;
}

export interface HANATable {
  schema_name: string;
  table_name: string;
  table_type: string;
  record_count: number;
}

export const hanaConnectionsApi = {
  /**
   * List all HANA connections
   */
  list: async (): Promise<HANAConnection[]> => {
    const response = await apiClient.get("/hana-connections");
    return response.data;
  },

  /**
   * Get a specific HANA connection
   */
  get: async (id: string): Promise<HANAConnection> => {
    const response = await apiClient.get(`/hana-connections/${id}`);
    return response.data;
  },

  /**
   * Create a new HANA connection
   */
  create: async (data: HANAConnectionCreate): Promise<HANAConnection> => {
    const response = await apiClient.post("/hana-connections", data);
    return response.data;
  },

  /**
   * Update a HANA connection
   */
  update: async (
    id: string,
    data: HANAConnectionUpdate
  ): Promise<HANAConnection> => {
    const response = await apiClient.put(`/hana-connections/${id}`, data);
    return response.data;
  },

  /**
   * Delete a HANA connection
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/hana-connections/${id}`);
  },

  /**
   * Test a HANA connection
   */
  test: async (connectionId: string): Promise<HANATestResponse> => {
    const response = await apiClient.post("/hana-connections/test", {
      connection_id: connectionId,
    });
    return response.data;
  },

  /**
   * List tables in a HANA connection
   */
  listTables: async (
    connectionId: string,
    schema?: string
  ): Promise<HANATable[]> => {
    const params = schema ? `?schema=${encodeURIComponent(schema)}` : "";
    const response = await apiClient.get(
      `/hana-connections/${connectionId}/tables${params}`
    );
    return response.data;
  },

  /**
   * List columns in a table
   */
  listColumns: async (
    connectionId: string,
    tableName: string,
    schema?: string
  ): Promise<string[]> => {
    const params = schema ? `?schema=${encodeURIComponent(schema)}` : "";
    const response = await apiClient.get(
      `/hana-connections/${connectionId}/tables/${encodeURIComponent(
        tableName
      )}/columns${params}`
    );
    return response.data;
  },
};
