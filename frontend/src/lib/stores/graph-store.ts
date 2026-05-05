/**
 * Workflow Graph Store
 *
 * Manages the state of the workflow graph editor using Zustand.
 */

import { create } from 'zustand';
import type { Node, Edge, Connection } from '@xyflow/react';

// ============================================================================
// Types
// ============================================================================

export interface InputFieldDefinition {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'array' | 'object';
  required: boolean;
  default_value?: any;
  description?: string;
  validation?: Record<string, any>;
}

export interface NodeData {
  label: string;
  type: 'input' | 'llm' | 'tool' | 'conditional' | 'agent' | 'output' | 'notebook_generator' | 'microsite_generator';
  config: {
    // LLM config
    model_name?: string;
    system_prompt?: string;
    temperature?: number;

    // Tool config
    tool_name?: string;
    tool_args?: Record<string, any>;

    // Conditional config
    condition_type?: 'equals' | 'contains' | 'greater_than' | 'less_than';
    field_path?: string;
    comparison_value?: any;
    true_edge_id?: string;
    false_edge_id?: string;

    // Agent config
    agent_type?: 'standalone' | 'team';
    agent_id?: string;
    agent_name?: string;
    prompt?: string;

    // Input node config
    input_fields?: InputFieldDefinition[];
    input_schema_json?: string;

    // Notebook Generator config
    notebook_name?: string;
    notebook_description?: string;
    folder_id?: string;
    tags?: string[];
    source_mode?: 'create_from_content' | 'use_existing' | 'both';
    content_source_node_id?: string;
    content_extraction_mode?: 'full_output' | 'smart_parse' | 'json_path';
    content_extraction_path?: string;
    source_title_template?: string;
    source_type?: 'text' | 'file' | 'url';
    existing_source_ids?: string[];
    output_format?: 'id_only' | 'full_object' | 'summary';

    // Microsite Generator config
    microsite_title?: string;
    microsite_description?: string;
    notebook_id_template?: string;
    template_id?: string;
    microsite_source_mode?: 'from_notebook' | 'explicit_ids' | 'from_node';
    microsite_source_ids?: string[];
    source_node_id?: string;
    user_prompt?: string;
    auto_publish?: boolean;
    microsite_output_format?: 'preview_url' | 'full_response' | 'summary';
    auto_create_notebook?: boolean;
    auto_notebook_description?: string;
    fail_on_moderation_block?: boolean;
  };
  // Execution state
  status?: 'pending' | 'running' | 'completed' | 'failed';
  error?: string;
}

export interface WorkflowMetadata {
  id?: string;
  name: string;
  description?: string;
  created_by: string;
  is_active: boolean;
  tags: string[];
}

interface GraphStore {
  // Graph state
  nodes: any[];
  edges: Edge[];

  // Workflow metadata
  metadata: WorkflowMetadata;

  // Selection state
  selectedNodeId: string | null;

  // Execution state
  isExecuting: boolean;
  executionId: string | null;

  // Actions
  setNodes: (nodes: any[]) => void;
  setEdges: (edges: Edge[]) => void;
  addNode: (node: any) => void;
  updateNode: (id: string, updates: Partial<any>) => void;
  deleteNode: (id: string) => void;
  addEdge: (connection: Connection) => void;
  deleteEdge: (id: string) => void;
  setSelectedNode: (id: string | null) => void;
  setMetadata: (metadata: Partial<WorkflowMetadata>) => void;
  setExecutionState: (isExecuting: boolean, executionId?: string | null) => void;
  updateNodeStatus: (nodeId: string, status: NodeData['status'], error?: string) => void;
  clearGraph: () => void;
  loadWorkflow: (workflow: any) => void;
}

// ============================================================================
// Store
// ============================================================================

export const useGraphStore = create<GraphStore>()(
  (set, get) => ({
    // Initial state
    nodes: [],
    edges: [],
    metadata: {
      name: 'Untitled Workflow',
      description: '',
      created_by: 'user',
      is_active: true,
      tags: [],
    },
    selectedNodeId: null,
    isExecuting: false,
    executionId: null,

      // Actions
      setNodes: (nodes) => set({ nodes }),

      setEdges: (edges) => set({ edges }),

      addNode: (node) =>
        set((state) => ({
          nodes: [...state.nodes, node],
        })),

      updateNode: (id, updates) => {
        // NOTE: This is not used anymore - PropertyPanel updates React Flow directly
        // Kept for backwards compatibility
        set((state) => ({
          nodes: state.nodes.map((node) =>
            node.id === id ? { ...node, ...updates } : node
          ),
        }));
      },

      deleteNode: (id) =>
        set((state) => ({
          nodes: state.nodes.filter((node) => node.id !== id),
          edges: state.edges.filter((edge) => edge.source !== id && edge.target !== id),
          selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
        })),

      addEdge: (connection) => {
        const edge: Edge = {
          id: `edge-${connection.source}-${connection.target}`,
          source: connection.source!,
          target: connection.target!,
          sourceHandle: connection.sourceHandle || undefined,
          targetHandle: connection.targetHandle || undefined,
        };

        set((state) => ({
          edges: [...state.edges, edge],
        }));
      },

      deleteEdge: (id) =>
        set((state) => ({
          edges: state.edges.filter((edge) => edge.id !== id),
        })),

      setSelectedNode: (id) => set({ selectedNodeId: id }),

      setMetadata: (metadata) =>
        set((state) => ({
          metadata: { ...state.metadata, ...metadata },
        })),

      setExecutionState: (isExecuting, executionId = null) =>
        set({ isExecuting, executionId }),

      updateNodeStatus: (nodeId, status, error) =>
        set((state) => ({
          nodes: state.nodes.map((node) =>
            node.id === nodeId
              ? {
                  ...node,
                  data: {
                    ...node.data,
                    status,
                    error,
                  },
                }
              : node
          ),
        })),

      clearGraph: () =>
        set({
          nodes: [],
          edges: [],
          selectedNodeId: null,
          isExecuting: false,
          executionId: null,
          metadata: {
            name: 'Untitled Workflow',
            description: '',
            created_by: 'user',
            is_active: true,
            tags: [],
          },
        }),

      loadWorkflow: (workflow) => {
        console.log('[Store] loadWorkflow called with:', workflow);
        console.log('[Store] - workflow.graph.nodes:', workflow.graph?.nodes?.length);
        console.log('[Store] - workflow.graph.edges:', workflow.graph?.edges?.length);

        // Convert workflow format to React Flow format
        const nodes: any[] = workflow.graph.nodes.map((n: any) => {
          console.log(`[Store] Node ${n.id}: position =`, n.position);
          return {
            id: n.id,
            type: n.type,
            position: n.position || { x: 0, y: 0 }, // Fallback if position is missing
            data: {
              label: n.label,
              type: n.type,
              config: n.config,
            },
          };
        });

        // Check if nodes are overlapping and need repositioning
        const nodeWidth = 320; // Approximate node width with padding
        const nodeHeight = 150; // Approximate node height
        const minSpacing = 100; // Minimum spacing between nodes

        let needsRepositioning = false;
        for (let i = 0; i < nodes.length - 1; i++) {
          for (let j = i + 1; j < nodes.length; j++) {
            const dx = Math.abs(nodes[i].position.x - nodes[j].position.x);
            const dy = Math.abs(nodes[i].position.y - nodes[j].position.y);

            // Check if nodes are too close (overlapping)
            if (dx < nodeWidth && dy < nodeHeight) {
              needsRepositioning = true;
              break;
            }
          }
          if (needsRepositioning) break;
        }

        // If nodes are overlapping, apply horizontal layout
        if (needsRepositioning) {
          console.log('[Store] Nodes are overlapping, applying automatic layout');
          nodes.forEach((node, index) => {
            node.position = {
              x: index * (nodeWidth + minSpacing),
              y: 100,
            };
          });
        }

        const edges: Edge[] = workflow.graph.edges.map((e: any) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
        }));

        console.log('[Store] Setting', nodes.length, 'nodes and', edges.length, 'edges');
        console.log('[Store] First node position:', nodes[0]?.position);

        set({
          nodes,
          edges,
          metadata: {
            id: workflow.id,
            name: workflow.name,
            description: workflow.description || '',
            created_by: workflow.created_by,
            is_active: workflow.is_active,
            tags: workflow.tags || [],
          },
          selectedNodeId: null,
          isExecuting: false,
          executionId: null,
        });

        console.log('[Store] Store updated with', nodes.length, 'nodes');
      },
    })
);

// ============================================================================
// Selectors
// ============================================================================

export const useSelectedNode = () => {
  const selectedNodeId = useGraphStore((state) => state.selectedNodeId);
  const nodes = useGraphStore((state) => state.nodes);
  return nodes.find((n) => n.id === selectedNodeId);
};

export const useWorkflowMetadata = () => useGraphStore((state) => state.metadata);

export const useIsExecuting = () => useGraphStore((state) => state.isExecuting);
