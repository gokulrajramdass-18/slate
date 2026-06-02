/**
 * Graph Editor Component
 *
 * Main visual workflow editor using React Flow.
 */

'use client';

import React, { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type Edge,
  BackgroundVariant,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';

import { Button } from '@/components/ui/button';
import { Plus, Network } from 'lucide-react';
import { nodeTypes } from './NodeComponents';
import { ExecutionOverlay } from './ExecutionOverlay';
import { useGraphStore } from '@/lib/stores/graph-store';
import type { NodeData } from '@/lib/stores/graph-store';
import type { WorkflowExecution } from '@/lib/api/workflows';

// Module-level storage for current graph state (accessed by save function)
let currentGraphState: {
  nodes: Node[];
  edges: Edge[];
} = {
  nodes: [],
  edges: [],
};

export function getCurrentGraphState() {
  return currentGraphState;
}

// ============================================================================
// Per-type default sizes (used as fallback before xyflow has measured a node)
// ============================================================================

const NODE_DEFAULT_SIZE: Record<string, { width: number; height: number }> = {
  input: { width: 220, height: 70 },
  output: { width: 220, height: 70 },
  llm: { width: 240, height: 130 },
  tool: { width: 220, height: 110 },
  agent: { width: 240, height: 130 },
  conditional: { width: 140, height: 140 },
  notebook_generator: { width: 240, height: 130 },
  microsite_generator: { width: 240, height: 150 },
  human_approval: { width: 220, height: 150 },
  workspace: { width: 220, height: 120 },
  template: { width: 220, height: 120 },
  delay: { width: 220, height: 110 },
  webhook: { width: 220, height: 130 },
  email: { width: 220, height: 130 },
  api: { width: 220, height: 130 },
  hana_table: { width: 220, height: 130 },
  snapshot: { width: 220, height: 130 },
  compare: { width: 220, height: 130 },
  foreach: { width: 240, height: 150 },
  jq: { width: 220, height: 110 },
  notify: { width: 220, height: 130 },
};
const FALLBACK_SIZE = { width: 220, height: 120 };

function getNodeSize(node: Node): { width: number; height: number } {
  const m = (node as any).measured;
  if (m?.width && m?.height) return { width: m.width, height: m.height };
  return NODE_DEFAULT_SIZE[node.type ?? ''] ?? FALLBACK_SIZE;
}

// ============================================================================
// Auto Layout Function using Dagre
// ============================================================================

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  // Tighter spacing for LR (reads as a horizontal chain); a touch more breathing
  // room for TB. Both keep marginx/marginy small so fitView frames the graph well.
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: isHorizontal ? 40 : 80,
    ranksep: isHorizontal ? 90 : 100,
    marginx: 20,
    marginy: 20,
  });

  // Capture the size used per-node so the post-layout position math uses the same
  // dimensions Dagre laid out against. Reading getNodeSize twice would be fine
  // (it's pure), but caching keeps it explicit.
  const sizes = new Map<string, { width: number; height: number }>();
  nodes.forEach((node) => {
    const size = getNodeSize(node);
    sizes.set(node.id, size);
    dagreGraph.setNode(node.id, size);
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    const size = sizes.get(node.id) ?? FALLBACK_SIZE;

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - size.width / 2,
        y: nodeWithPosition.y - size.height / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

// ============================================================================
// Layout helpers — single entry point shared by on-load, on-add, and the manual
// "Auto Layout" button.
// ============================================================================

function layoutGraph(
  nodes: Node[],
  edges: Edge[],
  opts: { direction?: 'LR' | 'TB' } = {},
) {
  return getLayoutedElements(nodes, edges, opts.direction ?? 'LR');
}

// Heuristic: are these node positions worth keeping, or do they look like the
// random-cascade fingerprint we want to overwrite on first load?
function isUntidy(nodes: Node[]): boolean {
  if (nodes.length === 0) return false;

  // Any node missing a position, or pinned at origin → untidy.
  for (const n of nodes) {
    const p = n.position as any;
    if (!p || (p.x === 0 && p.y === 0)) return true;
  }

  // All nodes share the same position → degenerate.
  const first = nodes[0].position;
  if (nodes.every((n) => n.position.x === first.x && n.position.y === first.y)) {
    return true;
  }

  // Random-cascade fingerprint: ≥4 nodes, every position inside the
  // [100,500]×[100,500] box that the old random placement produced.
  if (nodes.length >= 4) {
    const allInRandomBox = nodes.every(
      (n) =>
        n.position.x >= 100 &&
        n.position.x <= 500 &&
        n.position.y >= 100 &&
        n.position.y <= 500,
    );
    if (allInRandomBox) return true;
  }

  return false;
}

// Choose the upstream node a newly-added node should hang off of.
// Order: explicit selection → unique terminal (no outgoing edges) →
// most-recently-added (parsed from the `${type}-${Date.now()}` id) → null.
function pickAnchor(
  nodes: Node[],
  edges: Edge[],
  selectedId: string | null,
): Node | null {
  if (nodes.length === 0) return null;

  if (selectedId) {
    const selected = nodes.find((n) => n.id === selectedId);
    if (selected) return selected;
  }

  const sources = new Set(edges.map((e) => e.source));
  const terminals = nodes.filter((n) => !sources.has(n.id));
  if (terminals.length === 1) return terminals[0];

  // Fall back to most recent by trailing timestamp in id.
  let best: Node | null = null;
  let bestTs = -Infinity;
  for (const n of nodes) {
    const m = /-(\d+)$/.exec(n.id);
    const ts = m ? Number(m[1]) : 0;
    if (ts > bestTs) {
      bestTs = ts;
      best = n;
    }
  }
  return best;
}

// Build a connecting edge from anchor → newNode, picking the right sourceHandle
// for branching node types. Returns null when no edge should be created.
function synthEdge(anchor: Node, newNode: Node): Edge | null {
  // input nodes are always graph entry points — never wire something upstream of them.
  if (newNode.type === 'input') return null;

  let sourceHandle: string | undefined;
  switch (anchor.type) {
    case 'conditional':
      sourceHandle = 'true';
      break;
    case 'human_approval':
      sourceHandle = 'approved';
      break;
    case 'foreach':
      sourceHandle = 'each';
      break;
    default:
      sourceHandle = undefined;
  }

  const edge: Edge = {
    id: `edge-${anchor.id}-${newNode.id}`,
    source: anchor.id,
    target: newNode.id,
  };
  if (sourceHandle) (edge as any).sourceHandle = sourceHandle;
  return edge;
}

// ============================================================================
// Graph Editor Component
// ============================================================================

interface GraphEditorProps {
  workflowId?: string;
  execution?: WorkflowExecution | null;
  showToolbar?: boolean;
  onAddNode?: (type: NodeData['type']) => void;
}

export function GraphEditor({
  workflowId,
  execution,
  showToolbar = true,
  onAddNode,
}: GraphEditorProps) {
  console.log('[GraphEditor] RENDER - workflowId:', workflowId);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);
  const [showExecutionOverlay, setShowExecutionOverlay] = React.useState(true);
  const [reactFlowInstance, setReactFlowInstance] = React.useState<any>(null);

  console.log('[GraphEditor] nodes.length:', nodes.length, 'edges.length:', edges.length);

  // Store setNodes/setEdges in refs to avoid effect dependency issues
  const setNodesRef = React.useRef(setNodes);
  const setEdgesRef = React.useRef(setEdges);

  // Update refs only when they actually change (not on every render)
  React.useEffect(() => {
    setNodesRef.current = setNodes;
    setEdgesRef.current = setEdges;
  }, [setNodes, setEdges]);

  // Update module-level state whenever nodes/edges change (no Zustand, no effects)
  currentGraphState.nodes = nodes;
  currentGraphState.edges = edges;

  // Subscribe to store changes - load nodes/edges when store is updated.
  // We use signatures (not just lengths) so a refetch that returns the same
  // node/edge counts but different IDs still triggers a re-sync.
  const storeNodesSig = useGraphStore((state) =>
    state.nodes.map((n: any) => n.id).join('|'),
  );
  const storeEdgesSig = useGraphStore((state) =>
    state.edges.map((e: any) => `${e.id}:${e.source}->${e.target}`).join('|'),
  );

  React.useEffect(() => {
    const storeState = useGraphStore.getState();

    console.log('[GraphEditor] Store changed - nodes:', storeState.nodes.length, 'edges:', storeState.edges.length);
    console.log('[GraphEditor] Current React Flow - nodes:', nodes.length, 'edges:', edges.length);

    const storeNodesStr = JSON.stringify(storeState.nodes.map((n: any) => n.id).sort());
    const currentNodesStr = JSON.stringify(nodes.map((n: any) => n.id).sort());
    const storeEdgesStr = JSON.stringify(
      storeState.edges.map((e: any) => `${e.id}:${e.source}->${e.target}`).sort(),
    );
    const currentEdgesStr = JSON.stringify(
      edges.map((e: any) => `${e.id}:${e.source}->${e.target}`).sort(),
    );

    if (storeNodesStr !== currentNodesStr || storeEdgesStr !== currentEdgesStr) {
      console.log('[GraphEditor] Loading nodes/edges from store');

      // If the loaded positions look like the old random-cascade pattern
      // (or are otherwise degenerate), tidy them up before painting. We
      // also push the tidied positions back into the store so the next
      // save persists the new layout. A user-arranged graph passes through
      // unchanged because isUntidy() returns false.
      let nextNodes = storeState.nodes;
      let nextEdges = storeState.edges;
      if (isUntidy(storeState.nodes)) {
        console.log('[GraphEditor] Loaded positions look untidy — running auto-layout');
        const laid = layoutGraph(storeState.nodes, storeState.edges);
        nextNodes = laid.nodes;
        nextEdges = laid.edges;
        // Mirror the tidied positions back into the store. The store-sync
        // effect won't re-fire because the id-signature comparator above
        // only watches IDs and edge endpoints, not positions.
        requestAnimationFrame(() => {
          useGraphStore.getState().setNodes(nextNodes);
          useGraphStore.getState().setEdges(nextEdges);
        });
      }

      setNodesRef.current(nextNodes);
      setEdgesRef.current(nextEdges);

      // Fit view after nodes are loaded
      if (reactFlowInstance && nextNodes.length > 0) {
        setTimeout(() => {
          reactFlowInstance.fitView({ padding: 0.2, duration: 200 });
        }, 100);
      }
    }

    // Expose setNodes for PropertyPanel
    (useGraphStore.getState() as any).__setNodesFromReactFlow = setNodesRef.current;
  }, [storeNodesSig, storeEdgesSig, reactFlowInstance]); // Re-run when store content changes

  // Handle connection between nodes
  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => {
        const next = addEdge(connection, eds);
        // Mirror into the store so the save mutation, refetch syncs, and
        // any other consumers see the new edge immediately.
        requestAnimationFrame(() => {
          useGraphStore.getState().setEdges(next);
        });
        return next;
      });
    },
    [setEdges]
  );

  // Handle node selection
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      useGraphStore.getState().setSelectedNode(node.id);
    },
    []
  );

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    useGraphStore.getState().setSelectedNode(null);
  }, []);

  // Add new node — places it downstream of the selected (or last) node, draws
  // an auto-connecting edge with the right sourceHandle for branching anchors,
  // then re-runs layout so the canvas stays tidy. The placeholder position
  // matters only as a safety net; layoutGraph immediately overwrites it.
  const handleAddNode = useCallback(
    (type: NodeData['type']) => {
      const selectedId = useGraphStore.getState().selectedNodeId;
      const anchor = pickAnchor(nodes, edges, selectedId);

      const placeholder = anchor
        ? {
            x: anchor.position.x + getNodeSize(anchor).width + 80,
            y: anchor.position.y,
          }
        : { x: 100, y: 100 };

      const newNode: any = {
        id: `${type}-${Date.now()}`,
        type,
        position: placeholder,
        data: {
          label: `New ${type} node`,
          type,
          config: {},
        },
      };

      const maybeEdge = anchor ? synthEdge(anchor, newNode) : null;
      const nextNodes = [...nodes, newNode];
      const nextEdges = maybeEdge ? [...edges, maybeEdge] : edges;

      const { nodes: laidNodes, edges: laidEdges } = layoutGraph(nextNodes, nextEdges);

      setNodes(laidNodes);
      setEdges(laidEdges);

      // Mirror into the store asynchronously so we don't trigger setState during render.
      requestAnimationFrame(() => {
        useGraphStore.getState().setNodes(laidNodes);
        useGraphStore.getState().setEdges(laidEdges);
      });

      // Fit view so the new node is visible.
      if (reactFlowInstance) {
        setTimeout(() => {
          reactFlowInstance.fitView({ padding: 0.2, duration: 200 });
        }, 50);
      }
    },
    [nodes, edges, setNodes, setEdges, reactFlowInstance]
  );

  // Auto-layout nodes
  const handleAutoLayout = useCallback(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = layoutGraph(
      nodes,
      edges,
      { direction: 'LR' },
    );

    setNodes([...layoutedNodes]);
    setEdges([...layoutedEdges]);

    // Update Zustand store
    requestAnimationFrame(() => {
      useGraphStore.getState().setNodes(layoutedNodes);
      useGraphStore.getState().setEdges(layoutedEdges);
    });

    // Fit view after layout
    if (reactFlowInstance) {
      setTimeout(() => {
        reactFlowInstance.fitView({ padding: 0.2, duration: 300 });
      }, 50);
    }
  }, [nodes, edges, setNodes, setEdges, reactFlowInstance]);

  // Expose handleAddNode via callback prop or window reference
  React.useEffect(() => {
    // Always expose to window for toolbar access
    (window as any).__workflowAddNode = handleAddNode;

    return () => {
      // Cleanup on unmount
      delete (window as any).__workflowAddNode;
    };
  }, [handleAddNode]);

  return (
    <div className="h-full w-full relative">

      {/* Empty State */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-0">
          <div className="text-center max-w-md">
            <div className="p-4 rounded-full bg-muted inline-block mb-4">
              <Plus className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Start Building Your Workflow</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Add nodes from the toolbar on the left to create your workflow.
              Connect nodes together to define the execution flow.
            </p>
            <div className="text-xs text-muted-foreground space-y-1">
              <div>• <strong>Input Node</strong>: Start of the workflow</div>
              <div>• <strong>LLM Node</strong>: Call AI models</div>
              <div>• <strong>Tool Node</strong>: Execute tools</div>
              <div>• <strong>Agent Node</strong>: Execute standalone agents or teams</div>
              <div>• <strong>Conditional Node</strong>: Branch logic</div>
              <div>• <strong>Output Node</strong>: End of the workflow</div>
            </div>
          </div>
        </div>
      )}

      {/* React Flow Canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        onInit={setReactFlowInstance}
        nodeTypes={nodeTypes as any}
        fitView
        className="bg-muted/50"
        defaultEdgeOptions={{
          type: 'smoothstep',
          animated: false,
          style: { strokeWidth: 3, stroke: '#94a3b8' },
        }}
        connectionLineStyle={{ strokeWidth: 3, stroke: '#94a3b8' }}
      >
        <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
        <Controls />

        {/* Auto Layout Button */}
        {nodes.length > 0 && (
          <div className="absolute top-4 right-4 z-10">
            <Button
              onClick={handleAutoLayout}
              variant="outline"
              size="sm"
              className="bg-background shadow-lg hover:bg-accent"
            >
              <Network className="h-4 w-4 mr-2" />
              Auto Layout
            </Button>
          </div>
        )}

        <MiniMap
          nodeColor={(node) => {
            const colors: Record<string, string> = {
              input: '#22c55e',
              output: '#3b82f6',
              llm: '#a855f7',
              tool: '#f97316',
              agent: '#14b8a6',
              conditional: '#eab308',
            };
            return colors[node.type || 'default'] || '#64748b';
          }}
          className="!bg-background !border"
        />
      </ReactFlow>

      {/* Execution Overlay */}
      {execution && showExecutionOverlay && (
        <ExecutionOverlay
          execution={execution}
          onClose={() => setShowExecutionOverlay(false)}
        />
      )}
    </div>
  );
}
