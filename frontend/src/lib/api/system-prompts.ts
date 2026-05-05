/**
 * System Prompts API Client
 *
 * Handles all API calls for system prompt template management.
 */

const API_BASE = '/api/system-prompts';

export interface SystemPromptVariable {
  name: string;
  type: string;
  required: boolean;
  description?: string;
  example?: string;
}

export interface SystemPromptMetadata {
  output_format: string;
  composition: string;
  conditions?: string[];
  max_length?: number;
  output_schema?: Record<string, any>;
  note?: string;
}

export interface SystemPromptTemplate {
  id: string;
  category: string;
  template_key: string;
  name: string;
  description?: string;
  template: string;
  variables: SystemPromptVariable[];
  metadata: SystemPromptMetadata;
  is_default: boolean;
  is_active: boolean;
  created: string;
  updated: string;
}

export interface SystemPromptTemplateListResponse {
  templates: SystemPromptTemplate[];
  total: number;
}

export interface SystemPromptTemplateUpdate {
  template: string;
  name?: string;
  description?: string;
}

export interface CacheStats {
  cache_size: number;
  cache_ttl_minutes: number;
  cached_keys: string[];
}

/**
 * List all system prompt templates, optionally filtered by category
 */
export async function listTemplates(category?: string): Promise<SystemPromptTemplateListResponse> {
  const params = category ? `?category=${encodeURIComponent(category)}` : '';
  const response = await fetch(`${API_BASE}/templates${params}`);

  if (!response.ok) {
    throw new Error(`Failed to list templates: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a specific template by key
 */
export async function getTemplate(templateKey: string): Promise<SystemPromptTemplate> {
  const response = await fetch(`${API_BASE}/templates/${encodeURIComponent(templateKey)}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Template not found: ${templateKey}`);
    }
    throw new Error(`Failed to get template: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update a template (marks as non-default)
 */
export async function updateTemplate(
  templateKey: string,
  data: SystemPromptTemplateUpdate
): Promise<SystemPromptTemplate> {
  const response = await fetch(`${API_BASE}/templates/${encodeURIComponent(templateKey)}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Template not found: ${templateKey}`);
    }
    throw new Error(`Failed to update template: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Reset a template to its factory default
 */
export async function resetTemplate(templateKey: string): Promise<SystemPromptTemplate> {
  const response = await fetch(`${API_BASE}/templates/${encodeURIComponent(templateKey)}/reset`, {
    method: 'POST',
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Template not found: ${templateKey}`);
    }
    throw new Error(`Failed to reset template: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Toggle a template between active and inactive
 */
export async function toggleTemplate(templateKey: string): Promise<SystemPromptTemplate> {
  const response = await fetch(`${API_BASE}/templates/${encodeURIComponent(templateKey)}/toggle`, {
    method: 'POST',
  });

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Template not found: ${templateKey}`);
    }
    throw new Error(`Failed to toggle template: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Clear the prompt loader cache
 */
export async function clearCache(): Promise<{ message: string; data: any }> {
  const response = await fetch(`${API_BASE}/cache/clear`, {
    method: 'POST',
  });

  if (!response.ok) {
    throw new Error(`Failed to clear cache: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get cache statistics
 */
export async function getCacheStats(): Promise<CacheStats> {
  const response = await fetch(`${API_BASE}/cache/stats`);

  if (!response.ok) {
    throw new Error(`Failed to get cache stats: ${response.statusText}`);
  }

  return response.json();
}
