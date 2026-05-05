/**
 * MCP Servers API Client
 *
 * TypeScript client for managing MCP (Model Context Protocol) server connections.
 */

import { apiClient } from './client';

// ============================================================================
// Types
// ============================================================================

export interface MCPServer {
  id: string;
  name: string;
  description?: string;
  protocol: 'stdio' | 'http';

  // stdio fields
  command?: string;
  args?: string[];
  env_vars?: Record<string, string>;

  // HTTP fields
  url?: string;
  headers?: Record<string, string>;
  auth_type?: 'none' | 'bearer' | 'api_key' | 'oauth';
  auth_config?: {
    connected?: boolean;
  };

  // Status
  status: 'untested' | 'connected' | 'error' | 'disconnected' | 'needs_auth';
  last_test_at?: string;
  last_test_message?: string;
  capabilities?: {
    tools: any[];
    resources: any[];
    prompts: any[];
  };

  // Timestamps
  created_at: string;
  updated_at: string;
}

export interface MCPServerCreate {
  name: string;
  description?: string;
  protocol: 'stdio' | 'http';

  // stdio fields
  command?: string;
  args?: string[];
  env_vars?: Record<string, string>;

  // HTTP fields
  url?: string;
  headers?: Record<string, string>;
  auth_type?: 'none' | 'bearer' | 'api_key' | 'oauth';
  auth_config?: {
    token?: string;
    key_name?: string;
    key?: string;
  };
}

export interface MCPServerTestResponse {
  success: boolean;
  message: string;
  capabilities?: {
    tools: any[];
    resources: any[];
    prompts: any[];
  };
}

export interface MCPTool {
  id: string;
  server_id: string;
  tool_name: string;
  description: string;
  input_schema: any;
  discovered_at: string;
}

// ============================================================================
// API Client
// ============================================================================

export const mcpServersApi = {
  /**
   * List all MCP servers
   */
  list: async (): Promise<MCPServer[]> => {
    const response = await apiClient.get('/mcp-servers');
    return response.data;
  },

  /**
   * Get single MCP server by ID
   */
  get: async (id: string): Promise<MCPServer> => {
    const response = await apiClient.get(`/mcp-servers/${id}`);
    return response.data;
  },

  /**
   * Create new MCP server
   */
  create: async (data: MCPServerCreate): Promise<MCPServer> => {
    const response = await apiClient.post('/mcp-servers', data);
    return response.data;
  },

  /**
   * Update existing MCP server
   */
  update: async (id: string, data: Partial<MCPServerCreate>): Promise<MCPServer> => {
    const response = await apiClient.put(`/mcp-servers/${id}`, data);
    return response.data;
  },

  /**
   * Delete MCP server
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/mcp-servers/${id}`);
  },

  /**
   * Test MCP server connection and discover capabilities
   */
  test: async (id: string): Promise<MCPServerTestResponse> => {
    const response = await apiClient.post(`/mcp-servers/${id}/test`);
    return response.data;
  },

  /**
   * List tools from MCP server
   */
  listTools: async (id: string): Promise<MCPTool[]> => {
    const response = await apiClient.get(`/mcp-servers/${id}/tools`);
    return response.data;
  },

  /**
   * List resources from MCP server
   */
  listResources: async (id: string): Promise<{ resources: any[] }> => {
    const response = await apiClient.get(`/mcp-servers/${id}/resources`);
    return response.data;
  },

  /**
   * List prompts from MCP server
   */
  listPrompts: async (id: string): Promise<{ prompts: any[] }> => {
    const response = await apiClient.get(`/mcp-servers/${id}/prompts`);
    return response.data;
  },

  /**
   * Logout from OAuth-authenticated MCP server
   * Clears stored tokens and resets server to needs_auth status
   */
  logout: async (id: string): Promise<void> => {
    await apiClient.post(`/mcp-servers/${id}/logout`);
  },
};
