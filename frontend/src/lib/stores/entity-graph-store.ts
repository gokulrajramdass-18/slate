/**
 * Entity Graph Store
 *
 * Zustand store for managing entity graph state, filters, and interactions.
 */

import { create } from 'zustand'
import { Node, Edge } from 'reactflow'

export interface EntityNode extends Node {
  data: {
    name: string
    entity_type: string
    description?: string
    source_id: string
    mentions?: number
    confidence?: number
    is_center?: boolean
    is_source?: boolean
    is_target?: boolean
    on_path?: boolean
  }
}

export type EntityEdge = Edge<{
  relationship_type: string
  strength: number
  context?: string
  co_occurrence_count?: number
  source_name?: string
  target_name?: string
  on_path?: boolean
}>

export interface EntityGraphFilters {
  entity_types: string[]
  relationship_types: string[]
  min_strength: number
  community_id?: string
}

export interface Community {
  id: string
  name: string
  description?: string
  entity_count: number
  level: number
}

interface EntityGraphState {
  // Data
  nodes: EntityNode[]
  edges: EntityEdge[]
  communities: Community[]
  metadata: Record<string, any>

  // UI State
  selectedNodeId: string | null
  selectedEdgeId: string | null
  hoveredNodeId: string | null
  filters: EntityGraphFilters
  layoutType: 'force' | 'hierarchical' | 'circular' | 'manual'
  isLoading: boolean
  error: string | null

  // Scope
  sourceId: string | null
  notebookId: string | null

  // Actions
  setNodes: (nodes: EntityNode[]) => void
  setEdges: (edges: EntityEdge[]) => void
  setCommunities: (communities: Community[]) => void
  setMetadata: (metadata: Record<string, any>) => void
  selectNode: (nodeId: string | null) => void
  selectEdge: (edgeId: string | null) => void
  hoverNode: (nodeId: string | null) => void
  setFilters: (filters: Partial<EntityGraphFilters>) => void
  setLayoutType: (layout: 'force' | 'hierarchical' | 'circular' | 'manual') => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setScope: (sourceId: string | null, notebookId: string | null) => void

  // Graph operations
  loadGraph: (params: {
    sourceId?: string
    notebookId?: string
    entityTypes?: string[]
    relationshipTypes?: string[]
    communityId?: string
    minStrength?: number
  }) => Promise<void>
  expandNode: (nodeId: string, depth?: number) => Promise<void>
  findPath: (sourceId: string, targetId: string) => Promise<void>
  highlightCommunity: (communityId: string) => void
  reset: () => void
}

const DEFAULT_FILTERS: EntityGraphFilters = {
  entity_types: [],
  relationship_types: [],
  min_strength: 0.3,
}

export const useEntityGraphStore = create<EntityGraphState>((set, get) => ({
  // Initial state
  nodes: [],
  edges: [],
  communities: [],
  metadata: {},
  selectedNodeId: null,
  selectedEdgeId: null,
  hoveredNodeId: null,
  filters: DEFAULT_FILTERS,
  layoutType: 'force',
  isLoading: false,
  error: null,
  sourceId: null,
  notebookId: null,

  // Basic setters
  setNodes: (nodes) => set({ nodes }),
  setEdges: (edges) => set({ edges }),
  setCommunities: (communities) => set({ communities }),
  setMetadata: (metadata) => set({ metadata }),
  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),
  selectEdge: (edgeId) => set({ selectedEdgeId: edgeId }),
  hoverNode: (nodeId) => set({ hoveredNodeId: nodeId }),
  setLayoutType: (layout) => set({ layoutType: layout }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setScope: (sourceId, notebookId) => set({ sourceId, notebookId }),

  setFilters: (newFilters) => {
    const { filters } = get()
    set({ filters: { ...filters, ...newFilters } })
  },

  // Load entity graph
  loadGraph: async (params) => {
    set({ isLoading: true, error: null })

    try {
      const queryParams = new URLSearchParams()

      if (params.sourceId) queryParams.append('source_id', params.sourceId)
      if (params.notebookId) queryParams.append('notebook_id', params.notebookId)
      if (params.communityId) queryParams.append('community_id', params.communityId)
      if (params.minStrength !== undefined) {
        queryParams.append('min_strength', params.minStrength.toString())
      }
      if (params.entityTypes?.length) {
        params.entityTypes.forEach((type) => queryParams.append('entity_types', type))
      }
      if (params.relationshipTypes?.length) {
        params.relationshipTypes.forEach((type) =>
          queryParams.append('relationship_types', type)
        )
      }

      const response = await fetch(`/api/entity-graph?${queryParams}`)

      if (!response.ok) {
        throw new Error(`Failed to load entity graph: ${response.statusText}`)
      }

      const data = await response.json()

      set({
        nodes: data.nodes || [],
        edges: data.edges || [],
        metadata: data.metadata || {},
        isLoading: false,
        sourceId: params.sourceId || null,
        notebookId: params.notebookId || null,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Unknown error',
        isLoading: false,
      })
    }
  },

  // Expand node neighborhood
  expandNode: async (nodeId, depth = 1) => {
    set({ isLoading: true, error: null })

    try {
      const response = await fetch(
        `/api/entities/${nodeId}/neighbors?depth=${depth}`
      )

      if (!response.ok) {
        throw new Error(`Failed to expand node: ${response.statusText}`)
      }

      const data = await response.json()

      // Merge new nodes and edges with existing
      const { nodes, edges } = get()

      const existingNodeIds = new Set(nodes.map((n) => n.id))
      const existingEdgeIds = new Set(edges.map((e) => e.id))

      const newNodes = data.nodes.filter((n: EntityNode) => !existingNodeIds.has(n.id))
      const newEdges = data.edges.filter((e: EntityEdge) => !existingEdgeIds.has(e.id))

      set({
        nodes: [...nodes, ...newNodes],
        edges: [...edges, ...newEdges],
        isLoading: false,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Unknown error',
        isLoading: false,
      })
    }
  },

  // Find path between entities
  findPath: async (sourceId, targetId) => {
    set({ isLoading: true, error: null })

    try {
      const response = await fetch(
        `/api/entity-relationships/path/find?source_entity_id=${sourceId}&target_entity_id=${targetId}`
      )

      if (!response.ok) {
        if (response.status === 404) {
          set({ error: 'No path found between entities', isLoading: false })
          return
        }
        throw new Error(`Failed to find path: ${response.statusText}`)
      }

      const data = await response.json()

      // Replace graph with path
      set({
        nodes: data.nodes || [],
        edges: data.edges || [],
        metadata: data.metadata || {},
        isLoading: false,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Unknown error',
        isLoading: false,
      })
    }
  },

  // Highlight community
  highlightCommunity: (communityId) => {
    const { nodes, communities } = get()

    const community = communities.find((c) => c.id === communityId)
    if (!community) return

    // Mark nodes in community
    const updatedNodes = nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        in_community: true, // TODO: Check if entity is in community
      },
    }))

    set({ nodes: updatedNodes, filters: { ...get().filters, community_id: communityId } })
  },

  // Reset to initial state
  reset: () =>
    set({
      nodes: [],
      edges: [],
      communities: [],
      metadata: {},
      selectedNodeId: null,
      selectedEdgeId: null,
      hoveredNodeId: null,
      filters: DEFAULT_FILTERS,
      isLoading: false,
      error: null,
      sourceId: null,
      notebookId: null,
    }),
}))
