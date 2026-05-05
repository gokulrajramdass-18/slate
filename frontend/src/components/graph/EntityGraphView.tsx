/**
 * Entity Graph View Component
 *
 * Visualizes entity knowledge graph using React Flow.
 * Reuses existing graph infrastructure from source graph.
 */

'use client'

import { useCallback, useEffect } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  ConnectionMode,
} from 'reactflow'
import 'reactflow/dist/style.css'

import { useEntityGraphStore } from '@/lib/stores/entity-graph-store'

const ENTITY_TYPE_COLORS = {
  person: '#3b82f6',
  organization: '#8b5cf6',
  location: '#10b981',
  event: '#f59e0b',
  concept: '#ec4899',
  other: '#6b7280',
}

export function EntityGraphView() {
  const {
    nodes: storeNodes,
    edges: storeEdges,
    selectNode,
    selectEdge,
    selectedNodeId,
    layoutType,
  } = useEntityGraphStore()

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])

  // Apply layout when nodes/edges change
  useEffect(() => {
    if (!storeNodes.length) {
      setNodes([])
      setEdges([])
      return
    }

    // Apply layout
    const layoutedNodes = storeNodes;

    // Style nodes based on entity type
    const styledNodes = layoutedNodes.map((node) => ({
      ...node,
      style: {
        background: ENTITY_TYPE_COLORS[node.data.entity_type as keyof typeof ENTITY_TYPE_COLORS] || ENTITY_TYPE_COLORS.other,
        color: 'white',
        border: node.id === selectedNodeId ? '3px solid #000' : '1px solid #ddd',
        borderRadius: '50%',
        width: 60,
        height: 60,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '10px',
        fontWeight: 'bold',
        textAlign: 'center' as const,
        padding: '5px',
      },
    }))

    // Style edges
    const styledEdges = storeEdges.map((edge) => ({
      ...edge,
      type: 'smoothstep',
      animated: edge.data?.on_path || false,
      style: {
        stroke: edge.data?.on_path ? '#f59e0b' : '#b1b1b7',
        strokeWidth: edge.data?.strength ? edge.data.strength * 3 : 2,
      },
      label: edge.data?.relationship_type,
      labelStyle: { fill: '#666', fontSize: 10 },
    }))

    setNodes(styledNodes as any)
    setEdges(styledEdges as any)
  }, [storeNodes, storeEdges, layoutType, selectedNodeId, setNodes, setEdges])

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      selectNode(node.id)
    },
    [selectNode]
  )

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      selectEdge(edge.id)
    },
    [selectEdge]
  )

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        connectionMode={ConnectionMode.Loose}
        fitView
        minZoom={0.1}
        maxZoom={4}
      >
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            const data = node.data as any
            return ENTITY_TYPE_COLORS[data.entity_type as keyof typeof ENTITY_TYPE_COLORS] || ENTITY_TYPE_COLORS.other
          }}
          pannable
          zoomable
        />
      </ReactFlow>
    </div>
  )
}
