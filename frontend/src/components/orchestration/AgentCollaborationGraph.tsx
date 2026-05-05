/**
 * Agent Collaboration Graph
 *
 * Visualizes agent team structure and task flow during orchestration.
 */

'use client';

import React, { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface Agent {
  id: string;
  name: string;
  role: string;
  status: 'idle' | 'working' | 'completed';
}

interface Task {
  id: string;
  description: string;
  agent_id?: string;
  status: 'pending' | 'assigned' | 'in_progress' | 'completed';
  dependencies: string[];
}

interface CollaborationGraphProps {
  agents: Agent[];
  tasks: Task[];
  handovers: Array<{
    from_agent_id: string;
    to_agent_id: string;
    task_id: string;
  }>;
}

const agentRoleColors: Record<string, string> = {
  planner: '#3b82f6', // blue
  researcher: '#10b981', // green
  analyst: '#f59e0b', // amber
  synthesizer: '#8b5cf6', // purple
  reporter: '#ec4899', // pink
  default: '#6b7280', // gray
};

const statusColors = {
  idle: '#94a3b8',
  working: '#3b82f6',
  completed: '#10b981',
  pending: '#94a3b8',
  assigned: '#f59e0b',
  in_progress: '#3b82f6',
};

export function AgentCollaborationGraph({
  agents,
  tasks,
  handovers,
}: CollaborationGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    // Build nodes for agents
    const agentNodes: Node[] = agents.map((agent, index) => ({
      id: agent.id,
      type: 'default',
      position: {
        x: 100 + (index % 3) * 250,
        y: 100 + Math.floor(index / 3) * 200,
      },
      data: {
        label: (
          <div className="px-4 py-2 text-center">
            <div className="font-semibold text-sm">{agent.name}</div>
            <Badge
              variant="secondary"
              className="mt-1 text-xs"
              style={{
                backgroundColor: agentRoleColors[agent.role] || agentRoleColors.default,
                color: 'white',
              }}
            >
              {agent.role}
            </Badge>
            <div className="mt-1 text-xs text-muted-foreground">{agent.status}</div>
          </div>
        ),
      },
      style: {
        background: 'white',
        border: `2px solid ${statusColors[agent.status]}`,
        borderRadius: '8px',
        padding: 0,
      },
    }));

    // Build nodes for tasks
    const taskNodes: Node[] = tasks.map((task, index) => ({
      id: task.id,
      type: 'default',
      position: {
        x: 500,
        y: 100 + index * 100,
      },
      data: {
        label: (
          <div className="px-3 py-2 max-w-[200px]">
            <div className="text-xs font-medium truncate">{task.description}</div>
            <Badge
              variant="outline"
              className="mt-1 text-xs"
              style={{
                borderColor: statusColors[task.status],
                color: statusColors[task.status],
              }}
            >
              {task.status}
            </Badge>
          </div>
        ),
      },
      style: {
        background: 'white',
        border: `1px solid ${statusColors[task.status]}`,
        borderRadius: '6px',
        padding: 0,
      },
    }));

    setNodes([...agentNodes, ...taskNodes]);

    // Build edges for task assignments
    const assignmentEdges: Edge[] = tasks
      .filter((task) => task.agent_id)
      .map((task) => ({
        id: `assignment-${task.agent_id}-${task.id}`,
        source: task.agent_id!,
        target: task.id,
        label: 'assigned',
        type: 'smoothstep',
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
        style: {
          stroke: statusColors[task.status],
          strokeWidth: 2,
        },
        labelStyle: {
          fontSize: 10,
          fill: '#6b7280',
        },
      }));

    // Build edges for task dependencies
    const dependencyEdges: Edge[] = tasks.flatMap((task) =>
      task.dependencies.map((depId) => ({
        id: `dependency-${depId}-${task.id}`,
        source: depId,
        target: task.id,
        label: 'depends on',
        type: 'smoothstep',
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
        style: {
          stroke: '#94a3b8',
          strokeWidth: 1,
          strokeDasharray: '5,5',
        },
        labelStyle: {
          fontSize: 10,
          fill: '#94a3b8',
        },
      }))
    );

    // Build edges for handovers
    const handoverEdges: Edge[] = handovers.map((handover, index) => ({
      id: `handover-${handover.from_agent_id}-${handover.to_agent_id}-${index}`,
      source: handover.from_agent_id,
      target: handover.to_agent_id,
      label: 'handover',
      type: 'smoothstep',
      markerEnd: {
        type: MarkerType.ArrowClosed,
      },
      style: {
        stroke: '#8b5cf6',
        strokeWidth: 3,
      },
      labelStyle: {
        fontSize: 10,
        fill: '#8b5cf6',
        fontWeight: 600,
      },
      animated: true,
    }));

    setEdges([...assignmentEdges, ...dependencyEdges, ...handoverEdges]);
  }, [agents, tasks, handovers, setNodes, setEdges]);

  return (
    <Card className="w-full h-[600px] overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            const agent = agents.find((a) => a.id === node.id);
            if (agent) {
              return statusColors[agent.status];
            }
            return '#e5e7eb';
          }}
          style={{
            background: 'white',
            border: '1px solid #e5e7eb',
          }}
        />
      </ReactFlow>
    </Card>
  );
}
