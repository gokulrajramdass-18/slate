import { apiClient } from './client';

export interface OAuthAppCreate {
  name: string;
  description?: string;
  scopes: string[];
  redirect_uris?: string[];
  grant_types?: string[];
  rate_limit_per_hour?: number;
  rate_limit_per_day?: number;
  token_expiry_seconds?: number;
}

export interface OAuthAppUpdate {
  name?: string;
  description?: string;
  scopes?: string[];
  rate_limit_per_hour?: number;
  rate_limit_per_day?: number;
  token_expiry_seconds?: number;
}

export interface OAuthApp {
  id: string;
  name: string;
  description?: string;
  client_id: string;
  scopes: string[];
  redirect_uris?: string[];
  grant_types?: string[];
  status: string;
  rate_limit_per_hour: number;
  rate_limit_per_day: number;
  token_expiry_seconds: number;
  last_used_at?: string;
  created: string;
  updated: string;
}

export interface OAuthAppWithSecret extends OAuthApp {
  client_secret: string;
}

export interface OAuthScope {
  id: string;
  scope: string;
  resource_type: string;
  action: string;
  description?: string;
  is_system_only: boolean;
}

export interface UsageStats {
  total_requests: number;
  requests_today: number;
  requests_this_hour: number;
  avg_response_time_ms: number;
  error_rate: number;
  last_24h: Array<{
    hour: string;
    requests: number;
    errors: number;
    avg_response_time_ms: number;
  }>;
}

export const oauthAppsApi = {
  /**
   * List all OAuth applications for current user
   */
  list: async (): Promise<OAuthApp[]> => {
    const { data } = await apiClient.get('/oauth/apps');
    return data;
  },

  /**
   * Create new OAuth application
   * Returns app with client_secret (only shown once)
   */
  create: async (body: OAuthAppCreate): Promise<OAuthAppWithSecret> => {
    const { data } = await apiClient.post('/oauth/apps', body);
    return data;
  },

  /**
   * Get OAuth application details
   */
  get: async (id: string): Promise<OAuthApp> => {
    const { data } = await apiClient.get(`/oauth/apps/${id}`);
    return data;
  },

  /**
   * Update OAuth application settings
   */
  update: async (id: string, body: OAuthAppUpdate): Promise<OAuthApp> => {
    const { data } = await apiClient.put(`/oauth/apps/${id}`, body);
    return data;
  },

  /**
   * Delete OAuth application
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/oauth/apps/${id}`);
  },

  /**
   * Regenerate client secret
   * Returns new secret (only shown once)
   */
  regenerateSecret: async (id: string): Promise<{ client_secret: string }> => {
    const { data } = await apiClient.post(`/oauth/apps/${id}/regenerate-secret`);
    return data;
  },

  /**
   * Get usage statistics for application
   */
  getUsage: async (id: string): Promise<UsageStats> => {
    const { data } = await apiClient.get(`/oauth/apps/${id}/usage`);
    return data;
  },

  /**
   * List available OAuth scopes
   */
  listScopes: async (): Promise<OAuthScope[]> => {
    const { data } = await apiClient.get('/oauth/scopes');
    return data;
  },
};
