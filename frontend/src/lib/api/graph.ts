/**
 * Graph API Client
 *
 * Provides API methods and TanStack Query hooks for the relational graph visualization.
 * Backend endpoints are mounted at /api/graph/*.
 */

import { apiClient } from './client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { SourceType } from '@/lib/types';

// ============================================================================
// Types (matching backend Pydantic models in api/models.py)
// ============================================================================

export type EdgeType =
  | 'semantic'
  | 'notebook'
  | 'topic'
  | 'note_link'
  | 'hana_schema'
  | 'api_relation';

export interface GraphNodeData {
  title: string;
  description?: string;
  source_type: SourceType;
  created: string;
  updated: string;
  chunk_count: number;
  topics: string[];
  connection_count: number;
  notebooks: Array<{ id: string; name: string }>;
  hana_metadata?: Record<string, any>;
  api_metadata?: Record<string, any>;
  youtube_metadata?: Record<string, any>;
  file_metadata?: Record<string, any>;
}

export interface GraphNode {
  id: string;
  type: SourceType;
  label: string;
  data: GraphNodeData;
  position?: { x: number; y: number };
}

export interface GraphEdgeData {
  strength: number; // 0.0-1.0
  metadata: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: EdgeType;
  label?: string;
  data: GraphEdgeData;
}

export interface GraphMetadata {
  total_sources: number;
  date_range?: { min: string; max: string };
  source_type_counts: Record<string, number>;
  edge_type_counts: Record<string, number>;
}

export interface GraphSettings {
  similarity_count: number;
  sources_with_embeddings: number;
  total_sources: number;
  defaults: {
    semantic_threshold: number;
    top_k: number;
    min_topic_overlap: number;
  };
}

export interface BulkRecomputeJob {
  id: string;
  status: 'running' | 'completed' | 'failed';
  total: number;
  completed: number;
  threshold: number;
  top_k: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: GraphMetadata;
}

export interface GraphFilters {
  source_types?: SourceType[];
  notebook_ids?: string[];
  tags?: string[];
  date_from?: string;
  date_to?: string;
  semantic_threshold?: number;
  min_topic_overlap?: number;
  show_isolated?: boolean;
  edge_types?: EdgeType[];
}

export interface LayoutSaveRequest {
  name: string;
  description?: string;
  scope: 'global' | 'notebook';
  scope_id?: string;
  layout_data: Record<string, { x: number; y: number }>;
}

export interface LayoutResponse {
  id: string;
  name: string;
  description?: string;
  scope: string;
  scope_id?: string;
  layout_data?: Record<string, { x: number; y: number }>;
  created: string;
  updated: string;
}

export interface LayoutListResponse {
  layouts: LayoutResponse[];
  total: number;
}

// ============================================================================
// API Methods
// ============================================================================

function buildFilterParams(filters?: GraphFilters): Record<string, any> {
  if (!filters) return {};
  const params: Record<string, any> = {};

  if (filters.source_types?.length) params.source_types = filters.source_types;
  if (filters.notebook_ids?.length) params.notebook_ids = filters.notebook_ids;
  if (filters.tags?.length) params.tags = filters.tags;
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;
  if (filters.semantic_threshold !== undefined) params.semantic_threshold = filters.semantic_threshold;
  if (filters.min_topic_overlap !== undefined) params.min_topic_overlap = filters.min_topic_overlap;
  if (filters.show_isolated !== undefined) params.show_isolated = filters.show_isolated;
  if (filters.edge_types?.length) params.edge_types = filters.edge_types;

  return params;
}

export const graphApi = {
  /** Get global graph data for all sources */
  async getGlobalGraph(filters?: GraphFilters): Promise<GraphResponse> {
    const { data } = await apiClient.get('/graph/sources', {
      params: buildFilterParams(filters),
    });
    return data;
  },

  /** Get notebook-scoped graph data */
  async getNotebookGraph(notebookId: string, filters?: GraphFilters): Promise<GraphResponse> {
    const { data } = await apiClient.get(`/graph/sources/notebook/${notebookId}`, {
      params: buildFilterParams(filters),
    });
    return data;
  },

  /** Get neighborhood of a source up to specified depth */
  async getNeighborhood(
    sourceId: string,
    depth: number = 1,
    filters?: Partial<GraphFilters>
  ): Promise<GraphResponse> {
    const params: Record<string, any> = { depth };
    if (filters?.source_types?.length) params.source_types = filters.source_types;
    if (filters?.semantic_threshold !== undefined) params.semantic_threshold = filters.semantic_threshold;
    if (filters?.edge_types?.length) params.edge_types = filters.edge_types;

    const { data } = await apiClient.get(`/graph/sources/${sourceId}/neighbors`, { params });
    return data;
  },

  /** Recompute semantic similarities */
  async recomputeSimilarities(
    sourceIds?: string[],
    threshold: number = 0.7,
    topK: number = 20
  ): Promise<{ message: string; count: number; threshold: number; top_k: number }> {
    const { data } = await apiClient.post('/graph/sources/similarities', sourceIds || null, {
      params: { threshold, top_k: topK },
    });
    return data;
  },

  /** List saved layouts for a scope */
  async listLayouts(scope: 'global' | 'notebook', scopeId?: string): Promise<LayoutListResponse> {
    const params: Record<string, any> = { scope };
    if (scopeId) params.scope_id = scopeId;

    const { data } = await apiClient.get('/graph/layouts', { params });
    return data;
  },

  /** Get a saved layout by ID */
  async getLayout(layoutId: string): Promise<LayoutResponse> {
    const { data } = await apiClient.get(`/graph/layouts/${layoutId}`);
    return data;
  },

  /** Save a custom node layout */
  async saveLayout(request: LayoutSaveRequest): Promise<LayoutResponse> {
    const { data } = await apiClient.post('/graph/layouts', request);
    return data;
  },

  /** Update node positions for an existing layout */
  async updateLayout(
    layoutId: string,
    layoutData: Record<string, { x: number; y: number }>
  ): Promise<LayoutResponse> {
    const { data } = await apiClient.put(`/graph/layouts/${layoutId}`, layoutData);
    return data;
  },

  /** Delete a saved layout */
  async deleteLayout(layoutId: string): Promise<{ message: string; id: string }> {
    const { data } = await apiClient.delete(`/graph/layouts/${layoutId}`);
    return data;
  },

  /** Get graph computation settings */
  async getSettings(): Promise<GraphSettings> {
    const { data } = await apiClient.get('/graph/settings');
    return data;
  },

  /** Start bulk recompute of similarities */
  async startBulkRecompute(
    threshold: number = 0.7,
    topK: number = 20
  ): Promise<{ job_id: string; status: string }> {
    const { data } = await apiClient.post('/graph/similarities/bulk', null, {
      params: { threshold, top_k: topK },
    });
    return data;
  },

  /** Get bulk recompute job status */
  async getBulkRecomputeStatus(jobId: string): Promise<BulkRecomputeJob> {
    const { data } = await apiClient.get(`/graph/similarities/bulk/${jobId}`);
    return data;
  },

  /** List all bulk recompute jobs */
  async listBulkRecomputeJobs(): Promise<{ jobs: BulkRecomputeJob[] }> {
    const { data } = await apiClient.get('/graph/similarities/bulk');
    return data;
  },
};

// ============================================================================
// Query Keys
// ============================================================================

export const graphKeys = {
  all: ['graph'] as const,
  global: (filters?: GraphFilters) => ['graph', 'global', filters] as const,
  notebook: (id: string, filters?: GraphFilters) => ['graph', 'notebook', id, filters] as const,
  neighborhood: (sourceId: string, depth: number) => ['graph', 'neighborhood', sourceId, depth] as const,
  layouts: (scope: string, scopeId?: string) => ['graph', 'layouts', scope, scopeId] as const,
  layout: (id: string) => ['graph', 'layout', id] as const,
  settings: () => ['graph', 'settings'] as const,
  bulkJobs: () => ['graph', 'bulk-jobs'] as const,
  bulkJob: (id: string) => ['graph', 'bulk-job', id] as const,
};

// ============================================================================
// TanStack Query Hooks
// ============================================================================

/** Fetch graph data (global or notebook-scoped) */
export function useGraphData(
  scope: 'global' | 'notebook',
  id?: string,
  filters?: GraphFilters
) {
  return useQuery({
    queryKey: scope === 'notebook' && id
      ? graphKeys.notebook(id, filters)
      : graphKeys.global(filters),
    queryFn: () =>
      scope === 'notebook' && id
        ? graphApi.getNotebookGraph(id, filters)
        : graphApi.getGlobalGraph(filters),
    staleTime: 30_000,
  });
}

/** Fetch neighborhood of a source */
export function useNeighborhood(sourceId: string, depth: number = 1) {
  return useQuery({
    queryKey: graphKeys.neighborhood(sourceId, depth),
    queryFn: () => graphApi.getNeighborhood(sourceId, depth),
    enabled: !!sourceId,
    staleTime: 30_000,
  });
}

/** List saved layouts for a scope */
export function useGraphLayouts(scope: 'global' | 'notebook', scopeId?: string) {
  return useQuery({
    queryKey: graphKeys.layouts(scope, scopeId),
    queryFn: () => graphApi.listLayouts(scope, scopeId),
    staleTime: 60_000,
  });
}

/** Save a new layout */
export function useSaveLayout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: LayoutSaveRequest) => graphApi.saveLayout(request),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: graphKeys.layouts(data.scope, data.scope_id ?? undefined) });
    },
  });
}

/** Update an existing layout's positions */
export function useUpdateLayout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ layoutId, layoutData }: {
      layoutId: string;
      layoutData: Record<string, { x: number; y: number }>;
    }) => graphApi.updateLayout(layoutId, layoutData),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: graphKeys.layout(data.id) });
      queryClient.invalidateQueries({ queryKey: graphKeys.layouts(data.scope, data.scope_id ?? undefined) });
    },
  });
}

/** Delete a saved layout */
export function useDeleteLayout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (layoutId: string) => graphApi.deleteLayout(layoutId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
}

/** Recompute semantic similarities */
export function useRecomputeSimilarities() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sourceIds, threshold, topK }: {
      sourceIds?: string[];
      threshold?: number;
      topK?: number;
    }) => graphApi.recomputeSimilarities(sourceIds, threshold, topK),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
}

/** Fetch graph computation settings */
export function useGraphSettings() {
  return useQuery({
    queryKey: graphKeys.settings(),
    queryFn: () => graphApi.getSettings(),
    staleTime: 10_000,
  });
}

/** Start bulk recompute job */
export function useStartBulkRecompute() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ threshold, topK }: { threshold: number; topK: number }) =>
      graphApi.startBulkRecompute(threshold, topK),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.bulkJobs() });
    },
  });
}

/** Fetch bulk recompute job status (with polling) */
export function useBulkRecomputeStatus(jobId: string | null) {
  return useQuery({
    queryKey: graphKeys.bulkJob(jobId ?? ''),
    queryFn: () => graphApi.getBulkRecomputeStatus(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'completed' || data.status === 'failed')) {
        return false;
      }
      return 1000; // Poll every second while running
    },
  });
}

/** List bulk recompute jobs */
export function useBulkRecomputeJobs() {
  return useQuery({
    queryKey: graphKeys.bulkJobs(),
    queryFn: () => graphApi.listBulkRecomputeJobs().then((r) => r.jobs),
    staleTime: 5_000,
  });
}

// ============================================================================
// Classification API (NEW)
// ============================================================================

/** Classify sources */
export async function classifySources(sourceIds: string[], force = false) {
  return apiClient.post('/graph/classifications/classify', { source_ids: sourceIds, force });
}

/** Classify all sources (background job) */
export async function classifyAllSources() {
  return apiClient.post('/graph/classifications/classify-all');
}

/** Get all classifications */
export async function getClassifications(classificationType?: string, level?: number) {
  const params = new URLSearchParams();
  if (classificationType) params.append('classification_type', classificationType);
  if (level !== undefined) params.append('level', level.toString());
  return apiClient.get(`/graph/classifications?${params}`);
}

/** Get sources for a classification */
export async function getClassificationSources(
  classificationId: string,
  status: 'pending' | 'approved' | 'rejected' = 'approved'
) {
  return apiClient.get(`/graph/classifications/${classificationId}/sources?status=${status}`);
}

/** Get classification graph (mixed sources + classifications) */
export async function getClassificationGraph(options?: {
  notebookId?: string;
  classificationLevels?: number[];
  showApproved?: boolean;
  showPending?: boolean;
  showHierarchy?: boolean;
}) {
  const params = new URLSearchParams();
  if (options?.notebookId) params.append('notebook_id', options.notebookId);
  if (options?.classificationLevels) {
    options.classificationLevels.forEach((level) => params.append('classification_levels', level.toString()));
  }
  if (options?.showApproved !== undefined) params.append('show_approved', options.showApproved.toString());
  if (options?.showPending !== undefined) params.append('show_pending', options.showPending.toString());
  if (options?.showHierarchy !== undefined) params.append('show_hierarchy', options.showHierarchy.toString());

  return apiClient.get(`/graph/classifications/graph?${params}`);
}

/** Approve or reject a classification */
export async function approveClassification(
  classificationLinkId: string,
  action: 'approve' | 'reject',
  userId = 'default-user'
) {
  return apiClient.put(
    `/graph/classifications/approve/${classificationLinkId}?action=${action}&user_id=${userId}`
  );
}

/** Batch approve/reject classifications */
export async function approveClassificationsBatch(
  classificationLinkIds: string[],
  action: 'approve' | 'reject',
  userId = 'default-user'
) {
  return apiClient.put(
    `/graph/classifications/approve-batch?action=${action}&user_id=${userId}`,
    { classification_link_ids: classificationLinkIds }
  );
}

/** Get pending classifications */
export async function getPendingClassifications(sourceId?: string, minConfidence = 0.0) {
  const params = new URLSearchParams();
  if (sourceId) params.append('source_id', sourceId);
  params.append('min_confidence', minConfidence.toString());
  return apiClient.get(`/graph/classifications/pending?${params}`);
}

/** React Query hooks for classifications */
export function useClassifications(classificationType?: string, level?: number) {
  return useQuery({
    queryKey: ['classifications', classificationType, level],
    queryFn: () => getClassifications(classificationType, level),
  });
}

export function usePendingClassifications(sourceId?: string) {
  return useQuery({
    queryKey: ['pending-classifications', sourceId],
    queryFn: () => getPendingClassifications(sourceId),
  });
}

export function useClassifySources() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceIds, force }: { sourceIds: string[]; force?: boolean }) =>
      classifySources(sourceIds, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-classifications'] });
    },
  });
}

export function useApproveClassification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: string; action: 'approve' | 'reject' }) =>
      approveClassification(id, action),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pending-classifications'] });
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
}

