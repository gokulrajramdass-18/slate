/**
 * Source Graph Store
 *
 * Manages the state of the relational graph visualization using Zustand.
 * Handles graph data, view state, filters, and layout management.
 */

import { create } from 'zustand';
import type { Node, Edge, NodeChange, EdgeChange } from '@xyflow/react';
import { applyNodeChanges as xyApplyNodeChanges, applyEdgeChanges as xyApplyEdgeChanges } from '@xyflow/react';
import type { SourceType } from '@/lib/types';
import type {
  EdgeType,
  GraphMetadata,
  GraphFilters,
  GraphResponse,
} from '@/lib/api/graph';
import { graphApi } from '@/lib/api/graph';

// ============================================================================
// Types
// ============================================================================

export type LayoutAlgorithm = 'force' | 'hierarchical' | 'circular' | 'manual';

export interface SourceGraphFilters {
  sourceTypes: SourceType[];
  edgeTypes: EdgeType[];
  notebookIds: string[];
  tags: string[];
  dateRange: { from: Date | null; to: Date | null };
  semanticThreshold: number;
  showIsolated: boolean;
}

export interface SavedLayout {
  id: string;
  name: string;
  description?: string;
  scope: string;
  scopeId?: string;
  createdAt: string;
}

interface SourceGraphState {
  // Data
  nodes: Node[];
  edges: Edge[];
  metadata: GraphMetadata;

  // View state
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  currentLayout: LayoutAlgorithm;
  savedLayoutId: string | null;
  savedLayouts: SavedLayout[];

  // Scope tracking
  currentScope: 'global' | 'notebook';
  currentScopeId: string | undefined;

  // Loading
  isLoading: boolean;
  error: string | null;

  // Filters
  filters: SourceGraphFilters;

  // Actions
  loadGraph: (scope: 'global' | 'notebook', id?: string) => Promise<void>;
  fetchGraph: (notebookId?: string) => Promise<void>;
  applyNodeChanges: (changes: NodeChange[]) => void;
  applyEdgeChanges: (changes: EdgeChange[]) => void;
  applyLayout: (algorithm: LayoutAlgorithm) => void;
  updateFilters: (filters: Partial<SourceGraphFilters>) => void;
  resetFilters: () => void;
  selectNode: (id: string | null) => void;
  hoverNode: (id: string | null) => void;
  saveLayout: (name: string, description: string) => Promise<void>;
  loadLayout: (id: string) => Promise<void>;
  fetchSavedLayouts: () => Promise<void>;
  exportGraph: () => { nodes: Node[]; edges: Edge[]; metadata: GraphMetadata };
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  clearGraph: () => void;
}

// ============================================================================
// Helpers
// ============================================================================

const DEFAULT_METADATA: GraphMetadata = {
  total_sources: 0,
  source_type_counts: {},
  edge_type_counts: {},
};

const DEFAULT_FILTERS: SourceGraphFilters = {
  sourceTypes: [],
  edgeTypes: [],
  notebookIds: [],
  tags: [],
  dateRange: { from: null, to: null },
  semanticThreshold: 0.7,
  showIsolated: true,
};

/** Convert store filters to API query params */
function filtersToApiParams(filters: SourceGraphFilters): GraphFilters {
  const params: GraphFilters = {};

  if (filters.sourceTypes.length) params.source_types = filters.sourceTypes;
  if (filters.edgeTypes.length) params.edge_types = filters.edgeTypes;
  if (filters.notebookIds.length) params.notebook_ids = filters.notebookIds;
  if (filters.tags.length) params.tags = filters.tags;
  if (filters.dateRange.from) params.date_from = filters.dateRange.from.toISOString().split('T')[0];
  if (filters.dateRange.to) params.date_to = filters.dateRange.to.toISOString().split('T')[0];
  params.semantic_threshold = filters.semanticThreshold;
  params.show_isolated = filters.showIsolated;

  return params;
}

/** Convert API graph response to React Flow nodes and edges */
function graphResponseToReactFlow(response: GraphResponse): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = response.nodes.map((n) => ({
    id: n.id,
    type: n.type, // Custom node type mapped to source_type
    position: n.position ?? { x: 0, y: 0 }, // Use nullish coalescing to preserve explicit null
    data: {
      label: n.label,
      ...n.data,
    },
  }));

  const edges: Edge[] = response.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: 'relationship', // Custom edge type for rendering
    label: e.label,
    data: {
      edgeType: e.type,
      strength: e.data.strength,
      ...e.data.metadata,
    },
  }));

  return { nodes, edges };
}

// ============================================================================
// Store
// ============================================================================

export const useSourceGraphStore = create<SourceGraphState>()(
  (set, get) => ({
    // Initial state
    nodes: [],
    edges: [],
    metadata: DEFAULT_METADATA,

    selectedNodeId: null,
    hoveredNodeId: null,
    currentLayout: 'circular',
    savedLayoutId: null,
    savedLayouts: [],

    currentScope: 'global',
    currentScopeId: undefined,

    isLoading: false,
    error: null,

    filters: { ...DEFAULT_FILTERS },

    // Actions
    loadGraph: async (scope, id) => {
      set({ isLoading: true, error: null });

      try {
        const apiFilters = filtersToApiParams(get().filters);
        const response = scope === 'notebook' && id
          ? await graphApi.getNotebookGraph(id, apiFilters)
          : await graphApi.getGlobalGraph(apiFilters);

        // Merge classification nodes and edges with source graph
        const sourceGraph = graphResponseToReactFlow(response);
        let classificationNodes: any[] = [];
        let classificationEdges: any[] = [];

        // Try to fetch classification graph data (optional)
        try {
          const { getClassificationGraph } = await import('@/lib/api/graph');
          const classificationResponse = await getClassificationGraph({
            notebookId: scope === 'notebook' ? id : undefined,
            classificationLevels: [0, 1, 2],
            showApproved: true,
            showPending: true,
            showHierarchy: true,
          });

          classificationNodes = (classificationResponse.data?.nodes || []).map((n: any) => ({
            id: n.id,
            type: n.type || n.data?.classification_type || 'category', // Map classification_type to node type
            position: n.position ?? { x: 0, y: 0 },
            data: {
              // Use data from API response
              label: n.label || n.data?.name || 'Untitled',
              name: n.data?.name || n.label || 'Untitled',
              classification_type: n.data?.classification_type || n.type,
              level: n.data?.level ?? 0,
              color: n.data?.color,
              icon: n.data?.icon,
              sourceCount: n.data?.sourceCount || 0,
              childCount: n.data?.childCount || 0,
              pendingCount: n.data?.pendingCount || 0,
            },
          }));

          classificationEdges = (classificationResponse.data?.edges || []).map((e: any) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            type: 'relationship',
            label: e.label,
            data: {
              relationship_type: e.type,
              status: e.status,
              strength: e.strength,
              ...e.data,
            },
          }));
        } catch (classError) {
          console.warn('Failed to load classification graph (continuing without it):', classError);
        }

        // Deduplicate edges by ID (prefer classification edges over source edges if duplicate)
        const edgeMap = new Map();
        [...sourceGraph.edges, ...classificationEdges].forEach(edge => {
          edgeMap.set(edge.id, edge);
        });

        // Deduplicate nodes by ID (prefer source nodes over classification nodes if duplicate)
        const nodeMap = new Map();
        [...sourceGraph.nodes, ...classificationNodes].forEach(node => {
          if (!nodeMap.has(node.id)) {
            nodeMap.set(node.id, node);
          }
        });

        const allNodes = Array.from(nodeMap.values());
        const allEdges = Array.from(edgeMap.values());

        set({
          nodes: allNodes,
          edges: allEdges,
          metadata: response.metadata,
          isLoading: false,
          selectedNodeId: null,
          hoveredNodeId: null,
          currentScope: scope,
          currentScopeId: id,
        });
      } catch (e) {
        console.error('Failed to load graph:', e);
        const errorMessage = e instanceof Error
          ? `${e.message}${(e as any).response?.status ? ` (status: ${(e as any).response.status})` : ''}`
          : 'Failed to load graph';
        set({
          isLoading: false,
          error: errorMessage,
        });
      }
    },

    fetchGraph: async (notebookId) => {
      const scope = notebookId ? 'notebook' : 'global';
      await get().loadGraph(scope, notebookId);
    },

    applyNodeChanges: (changes) => {
      set((state) => ({
        nodes: xyApplyNodeChanges(changes, state.nodes),
      }));
    },

    applyEdgeChanges: (changes) => {
      set((state) => ({
        edges: xyApplyEdgeChanges(changes, state.edges),
      }));
    },

    applyLayout: (algorithm) => {
      set({ currentLayout: algorithm, savedLayoutId: null });
    },

    updateFilters: (partialFilters) => {
      set((state) => ({
        filters: { ...state.filters, ...partialFilters },
      }));

      // Reload graph with new filters
      const { currentScope, currentScopeId, loadGraph } = get();
      loadGraph(currentScope, currentScopeId);
    },

    resetFilters: () => {
      set({ filters: { ...DEFAULT_FILTERS } });

      // Reload graph with reset filters
      const { currentScope, currentScopeId, loadGraph } = get();
      loadGraph(currentScope, currentScopeId);
    },

    selectNode: (id) => set({ selectedNodeId: id }),

    hoverNode: (id) => set({ hoveredNodeId: id }),

    saveLayout: async (name, description) => {
      const { nodes } = get();
      const layoutData: Record<string, { x: number; y: number }> = {};
      for (const node of nodes) {
        layoutData[node.id] = { x: node.position.x, y: node.position.y };
      }

      try {
        const response = await graphApi.saveLayout({
          name,
          description,
          scope: 'global', // Caller can override via store state
          layout_data: layoutData,
        });
        set({ savedLayoutId: response.id });
      } catch (e) {
        set({ error: e instanceof Error ? e.message : 'Failed to save layout' });
      }
    },

    loadLayout: async (id) => {
      try {
        const layout = await graphApi.getLayout(id);
        if (!layout.layout_data) return;

        set((state) => ({
          nodes: state.nodes.map((node) => {
            const pos = layout.layout_data?.[node.id];
            return pos ? { ...node, position: { x: pos.x, y: pos.y } } : node;
          }),
          savedLayoutId: layout.id,
          currentLayout: 'manual',
        }));
      } catch (e) {
        set({ error: e instanceof Error ? e.message : 'Failed to load layout' });
      }
    },

    fetchSavedLayouts: async () => {
      const { currentScope, currentScopeId } = get();
      try {
        const response = await graphApi.listLayouts(currentScope, currentScopeId);
        set({
          savedLayouts: response.layouts.map((l) => ({
            id: l.id,
            name: l.name,
            description: l.description,
            scope: l.scope,
            scopeId: l.scope_id,
            createdAt: l.created,
          })),
        });
      } catch {
        // Silently fail - layouts are optional
      }
    },

    exportGraph: () => {
      const { nodes, edges, metadata } = get();
      return { nodes, edges, metadata };
    },

    setNodes: (nodes) => set({ nodes }),

    setEdges: (edges) => set({ edges }),

    clearGraph: () =>
      set({
        nodes: [],
        edges: [],
        metadata: DEFAULT_METADATA,
        selectedNodeId: null,
        hoveredNodeId: null,
        isLoading: false,
        error: null,
        savedLayoutId: null,
        savedLayouts: [],
        filters: { ...DEFAULT_FILTERS },
      }),
  })
);

// ============================================================================
// Selectors
// ============================================================================

export const useSelectedGraphNode = () => {
  const selectedNodeId = useSourceGraphStore((state) => state.selectedNodeId);
  const nodes = useSourceGraphStore((state) => state.nodes);
  return nodes.find((n) => n.id === selectedNodeId);
};

export const useGraphMetadata = () => useSourceGraphStore((state) => state.metadata);

export const useGraphFilters = () => useSourceGraphStore((state) => state.filters);

export const useGraphLoading = () => useSourceGraphStore((state) => state.isLoading);
