/**
 * Graph Interactions Hook
 *
 * Advanced interaction logic for the GraphCanvas:
 * - Search / highlighting
 * - Neighborhood expansion
 * - Dijkstra shortest-path finding
 */

import { useCallback, useState } from 'react';
import type { Node, Edge } from '@xyflow/react';
import { graphApi } from '@/lib/api/graph';
import { useSourceGraphStore } from '@/lib/stores/source-graph-store';

export type { RelationshipType as GraphEdgeType } from '@/components/graph/RelationshipEdge';

// ============================================================================
// Types
// ============================================================================

export interface SearchState {
  query: string;
  matchedNodeIds: Set<string>;
  isActive: boolean;
}

export interface PathState {
  /** Currently in path-finding mode */
  isActive: boolean;
  /** First node selected (source) */
  startNodeId: string | null;
  /** Second node selected (target) */
  endNodeId: string | null;
  /** Ordered list of node IDs in the shortest path */
  pathNodeIds: string[];
  /** Edge IDs that form the path */
  pathEdgeIds: string[];
  /** Total weight (sum of 1/strength for each edge) */
  totalWeight: number;
  /** Number of hops */
  hops: number;
  /** Error if no path exists */
  error: string | null;
}

export interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  nodeId: string | null;
}

export interface ExpandState {
  expandingNodeId: string | null;
  isExpanding: boolean;
}

// ============================================================================
// Dijkstra shortest path (client-side)
// ============================================================================

interface DijkstraResult {
  path: string[];
  edgeIds: string[];
  totalWeight: number;
}

function dijkstra(
  nodes: Node[],
  edges: Edge[],
  startId: string,
  endId: string
): DijkstraResult | null {
  // Build adjacency list: nodeId -> [{neighbor, edgeId, weight}]
  const adj = new Map<string, Array<{ neighbor: string; edgeId: string; weight: number }>>();

  for (const node of nodes) {
    adj.set(node.id, []);
  }

  for (const edge of edges) {
    const strength = (edge.data as any)?.strength ?? 0.5;
    // Lower strength = higher weight (harder to traverse)
    const weight = strength > 0 ? 1 / strength : 100;

    adj.get(edge.source)?.push({ neighbor: edge.target, edgeId: edge.id, weight });
    adj.get(edge.target)?.push({ neighbor: edge.source, edgeId: edge.id, weight });
  }

  if (!adj.has(startId) || !adj.has(endId)) return null;

  // Standard Dijkstra
  const dist = new Map<string, number>();
  const prev = new Map<string, { nodeId: string; edgeId: string } | null>();
  const visited = new Set<string>();

  for (const node of nodes) {
    dist.set(node.id, Infinity);
    prev.set(node.id, null);
  }
  dist.set(startId, 0);

  while (true) {
    // Find unvisited node with smallest distance
    let minDist = Infinity;
    let current: string | null = null;
    for (const [id, d] of dist) {
      if (!visited.has(id) && d < minDist) {
        minDist = d;
        current = id;
      }
    }

    if (current === null || current === endId) break;
    visited.add(current);

    const neighbors = adj.get(current) || [];
    for (const { neighbor, edgeId, weight } of neighbors) {
      if (visited.has(neighbor)) continue;
      const alt = (dist.get(current) ?? Infinity) + weight;
      if (alt < (dist.get(neighbor) ?? Infinity)) {
        dist.set(neighbor, alt);
        prev.set(neighbor, { nodeId: current, edgeId });
      }
    }
  }

  // Reconstruct path
  if (dist.get(endId) === Infinity) return null;

  const path: string[] = [];
  const edgeIds: string[] = [];
  let cur: string | null = endId;

  while (cur !== null) {
    path.unshift(cur);
    const p = prev.get(cur);
    if (p) {
      edgeIds.unshift(p.edgeId);
      cur = p.nodeId;
    } else {
      cur = null;
    }
  }

  return {
    path,
    edgeIds,
    totalWeight: dist.get(endId) ?? 0,
  };
}

// ============================================================================
// Hook: useGraphSearch
// ============================================================================

export function useGraphSearch(nodes: Node[]) {
  const [search, setSearch] = useState<SearchState>({
    query: '',
    matchedNodeIds: new Set(),
    isActive: false,
  });

  const updateSearch = useCallback(
    (query: string) => {
      if (!query.trim()) {
        setSearch({ query: '', matchedNodeIds: new Set(), isActive: false });
        return;
      }

      const lower = query.toLowerCase();
      const matched = new Set<string>();

      for (const node of nodes) {
        const data = node.data as any;
        const searchableText = [
          data.label,
          data.title,
          data.source_type,
          ...(data.topics || []),
          data.table_name,
          data.schema_name,
          data.endpoint,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();

        if (searchableText.includes(lower)) {
          matched.add(node.id);
        }
      }

      setSearch({ query, matchedNodeIds: matched, isActive: true });
    },
    [nodes]
  );

  const clearSearch = useCallback(() => {
    setSearch({ query: '', matchedNodeIds: new Set(), isActive: false });
  }, []);

  return { search, updateSearch, clearSearch };
}

// ============================================================================
// Hook: useContextMenu
// ============================================================================

export function useContextMenu() {
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false,
    x: 0,
    y: 0,
    nodeId: null,
  });

  const showContextMenu = useCallback(
    (event: React.MouseEvent | MouseEvent, nodeId: string) => {
      event.preventDefault();
      event.stopPropagation();
      setContextMenu({
        visible: true,
        x: event.clientX,
        y: event.clientY,
        nodeId,
      });
    },
    []
  );

  const hideContextMenu = useCallback(() => {
    setContextMenu((prev) => ({ ...prev, visible: false, nodeId: null }));
  }, []);

  return { contextMenu, showContextMenu, hideContextMenu };
}

// ============================================================================
// Hook: useNeighborhoodExpansion
// ============================================================================

export function useNeighborhoodExpansion() {
  const [expandState, setExpandState] = useState<ExpandState>({
    expandingNodeId: null,
    isExpanding: false,
  });

  const expandNeighbors = useCallback(
    async (nodeId: string, depth: number = 1) => {
      setExpandState({ expandingNodeId: nodeId, isExpanding: true });

      try {
        const response = await graphApi.getNeighborhood(nodeId, depth);
        const store = useSourceGraphStore.getState();
        const existingNodeIds = new Set(store.nodes.map((n) => n.id));
        const existingEdgeIds = new Set(store.edges.map((e) => e.id));

        // Find the anchor node to position new nodes around it
        const anchorNode = store.nodes.find((n) => n.id === nodeId);
        const anchorX = anchorNode?.position.x ?? 0;
        const anchorY = anchorNode?.position.y ?? 0;

        // Convert new nodes with positions radiating from anchor
        const newNodes: Node[] = [];
        const totalNew = response.nodes.filter((n) => !existingNodeIds.has(n.id)).length;
        let idx = 0;

        for (const apiNode of response.nodes) {
          if (existingNodeIds.has(apiNode.id)) continue;

          const angle = (2 * Math.PI * idx) / Math.max(totalNew, 1);
          const radius = 200 + Math.random() * 100;

          newNodes.push({
            id: apiNode.id,
            type: 'source',
            position: {
              x: anchorX + Math.cos(angle) * radius,
              y: anchorY + Math.sin(angle) * radius,
            },
            data: {
              label: apiNode.label,
              ...apiNode.data,
            },
          });
          idx++;
        }

        // Convert new edges
        const newEdges: Edge[] = [];
        for (const apiEdge of response.edges) {
          if (existingEdgeIds.has(apiEdge.id)) continue;

          newEdges.push({
            id: apiEdge.id,
            source: apiEdge.source,
            target: apiEdge.target,
            type: 'relationship',
            label: apiEdge.label,
            data: {
              edgeType: apiEdge.type,
              strength: apiEdge.data.strength,
              ...apiEdge.data.metadata,
            },
          });
        }

        // Merge into store
        store.setNodes([...store.nodes, ...newNodes]);
        store.setEdges([...store.edges, ...newEdges]);

        setExpandState({ expandingNodeId: null, isExpanding: false });
        return { addedNodes: newNodes.length, addedEdges: newEdges.length };
      } catch (err) {
        setExpandState({ expandingNodeId: null, isExpanding: false });
        throw err;
      }
    },
    []
  );

  return { expandState, expandNeighbors };
}

// ============================================================================
// Hook: usePathFinding
// ============================================================================

export function usePathFinding(nodes: Node[], edges: Edge[]) {
  const [pathState, setPathState] = useState<PathState>({
    isActive: false,
    startNodeId: null,
    endNodeId: null,
    pathNodeIds: [],
    pathEdgeIds: [],
    totalWeight: 0,
    hops: 0,
    error: null,
  });

  const startPathFinding = useCallback(() => {
    setPathState({
      isActive: true,
      startNodeId: null,
      endNodeId: null,
      pathNodeIds: [],
      pathEdgeIds: [],
      totalWeight: 0,
      hops: 0,
      error: null,
    });
  }, []);

  const selectPathNode = useCallback(
    (nodeId: string) => {
      setPathState((prev) => {
        if (!prev.isActive) return prev;

        // First pick: set start
        if (!prev.startNodeId) {
          return { ...prev, startNodeId: nodeId, error: null };
        }

        // Same node clicked: ignore
        if (prev.startNodeId === nodeId) return prev;

        // Second pick: set end and compute path
        const result = dijkstra(nodes, edges, prev.startNodeId, nodeId);

        if (!result) {
          return {
            ...prev,
            endNodeId: nodeId,
            pathNodeIds: [],
            pathEdgeIds: [],
            totalWeight: 0,
            hops: 0,
            error: 'No path exists between these sources.',
          };
        }

        return {
          ...prev,
          endNodeId: nodeId,
          pathNodeIds: result.path,
          pathEdgeIds: result.edgeIds,
          totalWeight: result.totalWeight,
          hops: result.path.length - 1,
          error: null,
        };
      });
    },
    [nodes, edges]
  );

  const cancelPathFinding = useCallback(() => {
    setPathState({
      isActive: false,
      startNodeId: null,
      endNodeId: null,
      pathNodeIds: [],
      pathEdgeIds: [],
      totalWeight: 0,
      hops: 0,
      error: null,
    });
  }, []);

  const resetPath = useCallback(() => {
    setPathState((prev) => ({
      ...prev,
      startNodeId: null,
      endNodeId: null,
      pathNodeIds: [],
      pathEdgeIds: [],
      totalWeight: 0,
      hops: 0,
      error: null,
    }));
  }, []);

  return { pathState, startPathFinding, selectPathNode, cancelPathFinding, resetPath };
}
