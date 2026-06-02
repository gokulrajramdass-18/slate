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

  /**
   * OAuth scope mode (only meaningful when `auth_type === 'oauth'`).
   *  - 'user'   (default): each user authenticates separately and has
   *                       their own token (`current_user_status` is
   *                       per-caller).
   *  - 'system': one admin authenticates once and that token is shared
   *                       across all users (`current_user_status` reflects
   *                       the shared token's existence, identical for
   *                       everyone).
   * Locked at server creation; cannot be changed by edits.
   */
  oauth_mode?: 'user' | 'system';

  // Status
  status: 'untested' | 'connected' | 'error' | 'disconnected' | 'needs_auth';

  /**
   * Per-user OAuth status from the calling user's perspective.
   * - 'connected'  → this user has a valid token for this server
   * - 'needs_auth' → this user has not authenticated yet (regardless of
   *                  whether other users have)
   * - undefined    → non-OAuth server (use `status` instead)
   */
  current_user_status?: 'connected' | 'needs_auth' | string;

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

  /**
   * OAuth scope mode. 'user' (default) or 'system'. Only sent on create
   * — the backend rejects oauth_mode in update payloads (locked at
   * creation).  Creating with `'system'` requires the caller to be a
   * superadmin.
   */
  oauth_mode?: 'user' | 'system';
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

/**
 * One authenticated user's session against an MCP server.
 *
 * Non-admins only see their own row. Admins see every row in
 * `mcp_oauth_tokens`, including the shared `__system__` row that backs
 * system-mode servers (`is_system === true`, no local user joined).
 */
export interface MCPServerSession {
  server_id: string;
  /** Token row's user_id. Real UUID for user-mode, `__system__` for system-mode. */
  user_id: string;
  username?: string | null;
  email?: string | null;
  full_name?: string | null;
  is_system: boolean;
  /** Identity reported by the OAuth provider at sign-in time (e.g. Outreach email). */
  provider_email?: string | null;
  provider_name?: string | null;
  expires_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  /** True iff this row belongs to the calling user. */
  is_current_user: boolean;
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
   * Begin a per-user OAuth flow.
   *
   * The backend uses the caller's JWT to bake the user_id into a signed
   * OAuth `state` parameter, so the public OAuth callback can later route
   * the resulting tokens to the correct user.
   */
  startOAuth: async (id: string): Promise<{ authorization_url: string }> => {
    const response = await apiClient.post(`/mcp-servers/${id}/oauth/start`);
    return response.data;
  },

  /**
   * Logout from OAuth-authenticated MCP server.
   * Clears the *calling user's* tokens only. Other users sharing this
   * server keep their sessions intact.
   */
  logout: async (id: string): Promise<void> => {
    await apiClient.post(`/mcp-servers/${id}/logout`);
  },

  /**
   * List authenticated user sessions for this server.
   *
   * Non-admins get only their own session (zero or one row). Admins get
   * every row in `mcp_oauth_tokens`, including the shared `__system__`
   * row for system-mode servers.
   */
  listSessions: async (id: string): Promise<MCPServerSession[]> => {
    const response = await apiClient.get(`/mcp-servers/${id}/sessions`);
    return response.data;
  },

  /**
   * Revoke an authenticated session. A non-admin may only revoke their
   * own session; an admin may revoke any session (including `__system__`,
   * which signs every user out of a system-mode server).
   */
  revokeSession: async (serverId: string, userId: string): Promise<void> => {
    await apiClient.delete(
      `/mcp-servers/${serverId}/sessions/${encodeURIComponent(userId)}`,
    );
  },
};
