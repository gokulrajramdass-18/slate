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
// Auto Layout Function using Dagre
// ============================================================================

const getLayoutedElements = (nodes: Node[], edges: Edge[], direction = 'TB') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const nodeWidth = 250;
  const nodeHeight = 150;

  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction, nodesep: 100, ranksep: 150 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);

    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
};

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
      setNodesRef.current(storeState.nodes);
      setEdgesRef.current(storeState.edges);

      // Fit view after nodes are loaded
      if (reactFlowInstance && storeState.nodes.length > 0) {
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

  // Add new node
  const handleAddNode = useCallback(
    (type: NodeData['type']) => {
      const newNode: any = {
        id: `${type}-${Date.now()}`,
        type,
        position: {
          x: Math.random() * 400 + 100,
          y: Math.random() * 400 + 100,
        },
        data: {
          label: `New ${type} node`,
          type,
          config: {},
        },
      };

      // Update React Flow state
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode];
        // Update Zustand store asynchronously to avoid setState during render
        requestAnimationFrame(() => {
          useGraphStore.getState().setNodes(updatedNodes);
        });
        return updatedNodes;
      });
    },
    [setNodes]
  );

  // Auto-layout nodes
  const handleAutoLayout = useCallback(() => {
    const { nodes: layoutedNodes, edges: layoutedEdges } = getLayoutedElements(
      nodes,
      edges,
      'TB' // Top to Bottom layout
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
