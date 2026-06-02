/**
 * API client for the agentic memory layers (Episodic, Semantic, Procedural).
 *
 * The legacy notebook-scoped endpoints continue to live under /memory/{notebook}
 * and are not consumed here. These functions speak the agent-scoped routes
 * exposed by backend/api/routers/agent_memory.py.
 */

import { apiClient } from "./client";

// ----------------------------------------------------------------------------
// Types
// ----------------------------------------------------------------------------

export interface MemoryConfig {
  short_term_enabled: boolean;
  episodic_enabled: boolean;
  episodic_retention_days: number;
  episodic_max_entries: number;
  semantic_enabled: boolean;
  semantic_max_facts: number;
  procedural_enabled: boolean;
  procedural_min_attempts: number;
  procedural_min_success_rate: number;
}

export interface MemoryStats {
  agent_id: string;
  episodic: number;
  semantic: number;
  procedural: number;
}

export interface EpisodicEntry {
  id: string;
  agent_id?: string | null;
  notebook_id: string;
  content: string;
  metadata?: Record<string, any>;
  tags?: string[];
  importance: number;
  source_message_id?: string | null;
  expires_at?: string | null;
  created?: string | null;
  updated?: string | null;
}

export interface SemanticEntry {
  id: string;
  agent_id?: string | null;
  notebook_id: string;
  content: string;
  metadata?: Record<string, any>;
  tags?: string[];
  importance: number;
  access_count: number;
  last_accessed?: string | null;
  has_embedding: boolean;
  similarity?: number | null;
  created?: string | null;
  updated?: string | null;
}

export interface ProceduralEntry {
  id: string;
  agent_id: string;
  task_pattern: string;
  tool_sequence: string[];
  success_count: number;
  failure_count: number;
  success_rate: number;
  total_attempts: number;
  avg_duration_ms?: number | null;
  example_inputs: any[];
  last_used?: string | null;
  has_embedding: boolean;
  similarity?: number | null;
  created?: string | null;
  updated?: string | null;
}

export interface RecallBundle {
  short_term: Record<string, any>;
  episodic: EpisodicEntry[];
  semantic: SemanticEntry[];
  procedural: ProceduralEntry[];
  formatted_prompt: string;
}

// ----------------------------------------------------------------------------
// Config
// ----------------------------------------------------------------------------

export async function getMemoryConfig(agentId: string): Promise<MemoryConfig> {
  const r = await apiClient.get(`/memory/agents/${agentId}/config`);
  return r.data;
}

export async function updateMemoryConfig(
  agentId: string,
  config: MemoryConfig,
): Promise<MemoryConfig> {
  const r = await apiClient.put(`/memory/agents/${agentId}/config`, config);
  return r.data;
}

// ----------------------------------------------------------------------------
// Stats / recall (debug)
// ----------------------------------------------------------------------------

export async function getMemoryStats(agentId: string): Promise<MemoryStats> {
  const r = await apiClient.get(`/memory/agents/${agentId}/stats`);
  return r.data;
}

export async function recallForAgent(
  agentId: string,
  query: string,
  k = { episodic: 5, semantic: 5, procedural: 3 },
): Promise<RecallBundle> {
  const r = await apiClient.get(`/memory/agents/${agentId}/recall`, {
    params: {
      query,
      k_episodic: k.episodic,
      k_semantic: k.semantic,
      k_procedural: k.procedural,
    },
  });
  return r.data;
}

// ----------------------------------------------------------------------------
// Episodic CRUD
// ----------------------------------------------------------------------------

export async function listEpisodic(
  agentId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<{ entries: EpisodicEntry[]; total: number }> {
  const r = await apiClient.get(`/memory/agents/${agentId}/episodic`, { params });
  return r.data;
}

export async function createEpisodic(
  agentId: string,
  body: {
    notebook_id: string;
    content: string;
    metadata?: Record<string, any>;
    tags?: string[];
    importance?: number;
    source_message_id?: string;
  },
): Promise<EpisodicEntry> {
  const r = await apiClient.post(`/memory/agents/${agentId}/episodic`, body);
  return r.data;
}

export async function deleteEpisodic(agentId: string, entryId: string): Promise<void> {
  await apiClient.delete(`/memory/agents/${agentId}/episodic/${entryId}`);
}

// ----------------------------------------------------------------------------
// Semantic CRUD
// ----------------------------------------------------------------------------

export async function listSemantic(
  agentId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<{ entries: SemanticEntry[]; total: number }> {
  const r = await apiClient.get(`/memory/agents/${agentId}/semantic`, { params });
  return r.data;
}

export async function createSemantic(
  agentId: string,
  body: {
    notebook_id: string;
    content: string;
    metadata?: Record<string, any>;
    tags?: string[];
    importance?: number;
  },
): Promise<SemanticEntry> {
  const r = await apiClient.post(`/memory/agents/${agentId}/semantic`, body);
  return r.data;
}

export async function deleteSemantic(agentId: string, entryId: string): Promise<void> {
  await apiClient.delete(`/memory/agents/${agentId}/semantic/${entryId}`);
}

// ----------------------------------------------------------------------------
// Procedural (read + delete only)
// ----------------------------------------------------------------------------

export async function listProcedural(
  agentId: string,
  params: { limit?: number; offset?: number } = {},
): Promise<{ entries: ProceduralEntry[]; total: number }> {
  const r = await apiClient.get(`/memory/agents/${agentId}/procedural`, { params });
  return r.data;
}

export async function deleteProcedural(agentId: string, entryId: string): Promise<void> {
  await apiClient.delete(`/memory/agents/${agentId}/procedural/${entryId}`);
}

export async function pruneExpired(agentId: string): Promise<{ message: string }> {
  const r = await apiClient.post(`/memory/agents/${agentId}/procedural/prune-expired`);
  return r.data;
}
