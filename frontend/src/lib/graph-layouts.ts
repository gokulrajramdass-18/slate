/**
 * Graph Layout Algorithms
 *
 * Provides force-directed, hierarchical, and circular layout algorithms
 * for positioning React Flow nodes.
 */

import type { Node, Edge } from '@xyflow/react';
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force';
import * as dagre from 'dagre';

// ============================================================================
// Types
// ============================================================================

export type LayoutAlgorithm = 'force' | 'hierarchical' | 'circular';

export interface ForceLayoutOptions {
  strength?: number;
  distance?: number;
  charge?: number;
  gravity?: number;
}

export interface HierarchicalLayoutOptions {
  direction?: 'TB' | 'BT' | 'LR' | 'RL';
  nodeSpacing?: number;
  rankSpacing?: number;
}

export interface CircularLayoutOptions {
  radius?: number;
  ordering?: 'type' | 'connections' | 'alphabetical';
}

export type LayoutOptions =
  | { algorithm: 'force'; options?: ForceLayoutOptions }
  | { algorithm: 'hierarchical'; options?: HierarchicalLayoutOptions }
  | { algorithm: 'circular'; options?: CircularLayoutOptions };

// Default node dimensions used for spacing calculations
const DEFAULT_NODE_WIDTH = 200;
const DEFAULT_NODE_HEIGHT = 80;

// ============================================================================
// Force-Directed Layout (d3-force)
// ============================================================================

interface SimNode extends SimulationNodeDatum {
  id: string;
}

export function applyForceLayout(
  nodes: Node[],
  edges: Edge[],
  options?: ForceLayoutOptions
): Node[] {
  if (nodes.length === 0) return [];

  const {
    strength = 0.4,
    distance = 180,
    charge = -500,
    gravity = 0.08,
  } = options ?? {};

  // Single node: center it
  if (nodes.length === 1) {
    return [{ ...nodes[0], position: { x: 0, y: 0 } }];
  }

  // Create simulation nodes with initial positions
  const simNodes: SimNode[] = nodes.map((node, i) => ({
    id: node.id,
    x: node.position?.x ?? Math.cos((2 * Math.PI * i) / nodes.length) * 200,
    y: node.position?.y ?? Math.sin((2 * Math.PI * i) / nodes.length) * 200,
  }));

  const nodeIndexMap = new Map(simNodes.map((n, i) => [n.id, i]));

  // Build links from edges, filtering out edges referencing missing nodes
  const simLinks: SimulationLinkDatum<SimNode>[] = edges
    .filter((e) => nodeIndexMap.has(e.source as string) && nodeIndexMap.has(e.target as string))
    .map((e) => ({
      source: nodeIndexMap.get(e.source as string)!,
      target: nodeIndexMap.get(e.target as string)!,
    }));

  // Run simulation synchronously
  const simulation = forceSimulation<SimNode>(simNodes)
    .force(
      'link',
      forceLink<SimNode, SimulationLinkDatum<SimNode>>(simLinks)
        .distance(distance)
        .strength(strength)
    )
    .force('charge', forceManyBody<SimNode>().strength(charge))
    .force('center', forceCenter(0, 0).strength(gravity))
    .force('collide', forceCollide<SimNode>(80)) // Larger collision radius for better spacing
    .stop();

  // Tick until stabilized or max iterations
  const maxTicks = 300;
  for (let i = 0; i < maxTicks; i++) {
    simulation.tick();
    if (simulation.alpha() < simulation.alphaMin()) break;
  }

  // Map results back to React Flow nodes
  return nodes.map((node, i) => ({
    ...node,
    position: {
      x: Math.round(simNodes[i].x ?? 0),
      y: Math.round(simNodes[i].y ?? 0),
    },
  }));
}

// ============================================================================
// Hierarchical Layout (dagre)
// ============================================================================

export function applyHierarchicalLayout(
  nodes: Node[],
  edges: Edge[],
  options?: HierarchicalLayoutOptions
): Node[] {
  if (nodes.length === 0) return [];

  const {
    direction = 'TB',
    nodeSpacing = 80,
    rankSpacing = 150,
  } = options ?? {};

  // Single node: center it
  if (nodes.length === 1) {
    return [{ ...nodes[0], position: { x: 0, y: 0 } }];
  }

  // Find connected components to handle disconnected graphs
  const components = findConnectedComponents(nodes, edges);

  const allPositioned: Map<string, { x: number; y: number }> = new Map();
  let xOffset = 0;

  for (const component of components) {
    const componentNodeIds = new Set(component.map((n) => n.id));
    const componentEdges = edges.filter(
      (e) =>
        componentNodeIds.has(e.source as string) &&
        componentNodeIds.has(e.target as string)
    );

    // Create dagre graph for this component
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({
      rankdir: direction,
      nodesep: nodeSpacing,
      ranksep: rankSpacing,
      marginx: 20,
      marginy: 20,
    });

    for (const node of component) {
      const width = (node.measured?.width ?? node.width) || DEFAULT_NODE_WIDTH;
      const height = (node.measured?.height ?? node.height) || DEFAULT_NODE_HEIGHT;
      g.setNode(node.id, { width, height });
    }

    for (const edge of componentEdges) {
      g.setEdge(edge.source as string, edge.target as string);
    }

    dagre.layout(g);

    // Read positions from dagre (dagre gives center-based positions)
    for (const node of component) {
      const dagreNode = g.node(node.id);
      if (dagreNode) {
        const width = (node.measured?.width ?? node.width) || DEFAULT_NODE_WIDTH;
        const height = (node.measured?.height ?? node.height) || DEFAULT_NODE_HEIGHT;
        allPositioned.set(node.id, {
          x: Math.round(dagreNode.x - width / 2 + xOffset),
          y: Math.round(dagreNode.y - height / 2),
        });
      }
    }

    // Calculate bounding box width for offset between disconnected components
    const graph = g.graph();
    xOffset += (graph.width ?? 400) + nodeSpacing;
  }

  return nodes.map((node) => ({
    ...node,
    position: allPositioned.get(node.id) ?? node.position,
  }));
}

// ============================================================================
// Circular Layout (custom)
// ============================================================================

export function applyCircularLayout(
  nodes: Node[],
  options?: CircularLayoutOptions
): Node[] {
  if (nodes.length === 0) return [];

  const {
    radius = 300,
    ordering = 'connections',
  } = options ?? {};

  // Single node: center it
  if (nodes.length === 1) {
    return [{ ...nodes[0], position: { x: 0, y: 0 } }];
  }

  // Sort nodes by ordering preference
  const sorted = [...nodes];
  switch (ordering) {
    case 'type':
      sorted.sort((a, b) => (a.type ?? '').localeCompare(b.type ?? ''));
      break;
    case 'alphabetical':
      sorted.sort((a, b) => {
        const labelA = (a.data as Record<string, unknown>)?.label as string ?? a.id;
        const labelB = (b.data as Record<string, unknown>)?.label as string ?? b.id;
        return labelA.localeCompare(labelB);
      });
      break;
    case 'connections':
      // Will be reordered below in concentric circle logic
      break;
  }

  // Build a position map using concentric circles
  const positionMap = new Map<string, { x: number; y: number }>();

  if (ordering === 'connections') {
    // Concentric layout: highly connected nodes in inner ring
    // We need edges for this, but the function signature doesn't include them.
    // Use a single circle with equal spacing as the fallback;
    // the caller can pass edges via applyCircularLayoutWithEdges for concentric.
    layoutSingleCircle(sorted, radius, positionMap);
  } else {
    layoutSingleCircle(sorted, radius, positionMap);
  }

  return nodes.map((node) => ({
    ...node,
    position: positionMap.get(node.id) ?? node.position,
  }));
}

/**
 * Extended circular layout that uses edge information
 * to create concentric circles (hub nodes inner, peripheral outer).
 */
export function applyCircularLayoutWithEdges(
  nodes: Node[],
  edges: Edge[],
  options?: CircularLayoutOptions
): Node[] {
  if (nodes.length === 0) return [];

  const {
    radius = 300,
    ordering = 'connections',
  } = options ?? {};

  if (nodes.length === 1) {
    return [{ ...nodes[0], position: { x: 0, y: 0 } }];
  }

  if (ordering !== 'connections') {
    return applyCircularLayout(nodes, options);
  }

  // Count connections per node
  const connectionCount = new Map<string, number>();
  for (const node of nodes) {
    connectionCount.set(node.id, 0);
  }
  for (const edge of edges) {
    const src = edge.source as string;
    const tgt = edge.target as string;
    if (connectionCount.has(src)) {
      connectionCount.set(src, connectionCount.get(src)! + 1);
    }
    if (connectionCount.has(tgt)) {
      connectionCount.set(tgt, connectionCount.get(tgt)! + 1);
    }
  }

  // Sort by connection count descending
  const sorted = [...nodes].sort(
    (a, b) => (connectionCount.get(b.id) ?? 0) - (connectionCount.get(a.id) ?? 0)
  );

  // Split into concentric rings
  // Inner ring: top 30% (hub nodes), outer ring: rest
  const innerCount = Math.max(1, Math.ceil(sorted.length * 0.3));
  const innerNodes = sorted.slice(0, innerCount);
  const outerNodes = sorted.slice(innerCount);

  const positionMap = new Map<string, { x: number; y: number }>();
  const innerRadius = radius * 0.4;  // Increased from 0.5 to spread more
  const outerRadius = radius;

  layoutSingleCircle(innerNodes, innerRadius, positionMap);
  layoutSingleCircle(outerNodes, outerRadius, positionMap);

  return nodes.map((node) => ({
    ...node,
    position: positionMap.get(node.id) ?? node.position,
  }));
}

// ============================================================================
// Async Web Worker Wrapper
// ============================================================================

/**
 * Runs layout computation asynchronously via setTimeout to avoid blocking
 * the main thread for large graphs.
 */
export function applyLayoutAsync(
  algorithm: LayoutAlgorithm,
  nodes: Node[],
  edges: Edge[],
  options?: ForceLayoutOptions | HierarchicalLayoutOptions | CircularLayoutOptions
): Promise<Node[]> {
  return new Promise((resolve) => {
    // Use setTimeout to yield to the event loop
    setTimeout(() => {
      let result: Node[];
      switch (algorithm) {
        case 'force':
          result = applyForceLayout(nodes, edges, options as ForceLayoutOptions);
          break;
        case 'hierarchical':
          result = applyHierarchicalLayout(nodes, edges, options as HierarchicalLayoutOptions);
          break;
        case 'circular':
          result = applyCircularLayoutWithEdges(nodes, edges, options as CircularLayoutOptions);
          break;
        default:
          result = nodes;
      }
      resolve(result);
    }, 0);
  });
}

// ============================================================================
// Helper Functions
// ============================================================================

function layoutSingleCircle(
  nodes: Node[],
  radius: number,
  positionMap: Map<string, { x: number; y: number }>
): void {
  const count = nodes.length;
  for (let i = 0; i < count; i++) {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2; // Start from top
    positionMap.set(nodes[i].id, {
      x: Math.round(Math.cos(angle) * radius),
      y: Math.round(Math.sin(angle) * radius),
    });
  }
}

/**
 * Find connected components in the graph using union-find.
 */
function findConnectedComponents(nodes: Node[], edges: Edge[]): Node[][] {
  if (nodes.length === 0) return [];

  const parent = new Map<string, string>();

  function find(id: string): string {
    let root = id;
    while (parent.get(root) !== root) {
      root = parent.get(root)!;
    }
    // Path compression
    let current = id;
    while (current !== root) {
      const next = parent.get(current)!;
      parent.set(current, root);
      current = next;
    }
    return root;
  }

  function union(a: string, b: string): void {
    const ra = find(a);
    const rb = find(b);
    if (ra !== rb) {
      parent.set(ra, rb);
    }
  }

  // Initialize each node as its own parent
  for (const node of nodes) {
    parent.set(node.id, node.id);
  }

  // Union nodes connected by edges
  for (const edge of edges) {
    const src = edge.source as string;
    const tgt = edge.target as string;
    if (parent.has(src) && parent.has(tgt)) {
      union(src, tgt);
    }
  }

  // Group nodes by component root
  const components = new Map<string, Node[]>();
  for (const node of nodes) {
    const root = find(node.id);
    if (!components.has(root)) {
      components.set(root, []);
    }
    components.get(root)!.push(node);
  }

  return Array.from(components.values());
}
