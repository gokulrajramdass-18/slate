/**
 * Execution Detail Page
 *
 * Shows detailed execution information with node states visualization.
 */

'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, CheckCircle, XCircle, Loader2, Clock, AlertCircle } from 'lucide-react';
import { workflowsApi } from '@/lib/api/workflows';
import type { WorkflowExecution, NodeExecutionState } from '@/lib/api/workflows';
import { format } from 'date-fns';

// ============================================================================
// Node State Card Component
// ============================================================================

function NodeStateCard({ nodeId, state }: { nodeId: string; state: NodeExecutionState }) {
  const statusConfig = {
    pending: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-100' },
    running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-100' },
    paused: { icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-100' },
    completed: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-100' },
    failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-100' },
    cancelled: { icon: XCircle, color: 'text-gray-500', bg: 'bg-gray-100' },
  };

  const config = statusConfig[state.status] || statusConfig.pending;
  const Icon = config.icon;

  const duration = state.started_at && state.completed_at
    ? new Date(state.completed_at).getTime() - new Date(state.started_at).getTime()
    : null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`p-2 rounded-full ${config.bg}`}>
              <Icon className={`h-4 w-4 ${config.color} ${state.status === 'running' ? 'animate-spin' : ''}`} />
            </div>
            <CardTitle className="text-base">{nodeId}</CardTitle>
          </div>
          <Badge variant={
            state.status === 'completed' ? 'default' :
            state.status === 'failed' ? 'destructive' :
            state.status === 'paused' ? 'outline' :
            'secondary'
          }>
            {state.status}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {/* Timestamps */}
        {state.started_at && (
          <div className="text-sm">
            <span className="text-muted-foreground">Started:</span>{' '}
            <span className="font-medium">{format(new Date(state.started_at), 'HH:mm:ss')}</span>
          </div>
        )}

        {state.completed_at && (
          <div className="text-sm">
            <span className="text-muted-foreground">Completed:</span>{' '}
            <span className="font-medium">{format(new Date(state.completed_at), 'HH:mm:ss')}</span>
          </div>
        )}

        {duration !== null && (
          <div className="text-sm">
            <span className="text-muted-foreground">Duration:</span>{' '}
            <span className="font-medium">{duration}ms</span>
          </div>
        )}

        {/* Error */}
        {state.error && (
          <div className="bg-destructive/10 text-destructive p-3 rounded text-sm">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <div>{state.error}</div>
            </div>
          </div>
        )}

        {/* Input Data */}
        {state.input_data && (
          <details className="text-sm">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              Input Data
            </summary>
            <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-x-auto">
              {JSON.stringify(state.input_data, null, 2)}
            </pre>
          </details>
        )}

        {/* Output Data */}
        {state.output_data && (
          <>
            {/* Special handling for approval node output */}
            {state.output_data.status === 'approved' || state.output_data.status === 'rejected' ? (
              <div className="space-y-2">
                <div className={`p-3 rounded ${state.output_data.status === 'approved' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  <div className="flex items-center gap-2">
                    {state.output_data.status === 'approved' ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                    <span className="font-medium">
                      {state.output_data.status === 'approved' ? 'Approved' : 'Rejected'}
                    </span>
                  </div>
                  {state.output_data.approval_response && (
                    <div className="text-sm mt-1">
                      Response: {state.output_data.approval_response}
                    </div>
                  )}
                  {state.output_data.approval_comment && (
                    <div className="text-sm mt-1">
                      Comment: {state.output_data.approval_comment}
                    </div>
                  )}
                  {state.output_data.approved_by && (
                    <div className="text-sm mt-1">
                      By: {state.output_data.approved_by}
                    </div>
                  )}
                </div>
                <details className="text-sm">
                  <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                    Full Output Data
                  </summary>
                  <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-x-auto">
                    {JSON.stringify(state.output_data, null, 2)}
                  </pre>
                </details>
              </div>
            ) : (
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                  Output Data
                </summary>
                <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-x-auto">
                  {JSON.stringify(state.output_data, null, 2)}
                </pre>
              </details>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Execution Detail Page
// ============================================================================

export default function ExecutionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const executionId = params.executionId as string;

  const { data: workflow } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowsApi.get(workflowId),
  });

  const { data: execution, isLoading } = useQuery({
    queryKey: ['execution', workflowId, executionId],
    queryFn: () => workflowsApi.getExecution(workflowId, executionId),
    refetchInterval: (query) => {
      // Refetch every 2 seconds if running or paused, otherwise stop
      const status = query.state.data?.status;
      return (status === 'running' || status === 'paused') ? 2000 : false;
    },
  });

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
          <p className="mt-4 text-muted-foreground">Loading execution details...</p>
        </div>
      </div>
    );
  }

  if (!execution) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto" />
          <p className="mt-4 text-muted-foreground">Execution not found</p>
          <Button className="mt-4" onClick={() => router.push(`/workflows/${workflowId}/executions`)}>
            Back to Executions
          </Button>
        </div>
      </div>
    );
  }

  const statusConfig = {
    pending: { icon: Clock, color: 'text-gray-500' },
    running: { icon: Loader2, color: 'text-blue-500' },
    paused: { icon: Clock, color: 'text-yellow-500' },
    completed: { icon: CheckCircle, color: 'text-green-500' },
    failed: { icon: XCircle, color: 'text-red-500' },
    cancelled: { icon: XCircle, color: 'text-gray-500' },
  };

  const config = statusConfig[execution.status];
  const Icon = config.icon;

  const nodeStates = execution.node_states || {};

  const duration = execution.completed_at
    ? new Date(execution.completed_at).getTime() - new Date(execution.started_at).getTime()
    : null;

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-6 max-w-7xl mx-auto px-4 md:px-6 lg:px-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push(`/workflows/${workflowId}/executions`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <Icon className={`h-6 w-6 ${config.color} ${execution.status === 'running' ? 'animate-spin' : ''}`} />
              <h1 className="text-3xl font-bold">Execution Details</h1>
            </div>
            {workflow && (
              <p className="text-muted-foreground mt-1">{workflow.name}</p>
            )}
          </div>
        </div>

        <Badge variant={
          execution.status === 'completed' ? 'default' :
          execution.status === 'failed' ? 'destructive' :
          execution.status === 'paused' ? 'outline' :
          'secondary'
        }>
          {execution.status}
        </Badge>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Started
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {format(new Date(execution.started_at), 'HH:mm:ss')}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {format(new Date(execution.started_at), 'MMM d, yyyy')}
            </div>
          </CardContent>
        </Card>

        {execution.completed_at && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Completed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {format(new Date(execution.completed_at), 'HH:mm:ss')}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {duration !== null && `${duration}ms`}
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Triggered By
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline">{execution.triggered_by}</Badge>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Nodes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Object.keys(nodeStates).length}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {Object.values(nodeStates).filter((n) => n.status === 'completed').length} completed
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="nodes" className="space-y-4">
        <TabsList>
          <TabsTrigger value="nodes">Node States</TabsTrigger>
          <TabsTrigger value="output">Final Output</TabsTrigger>
        </TabsList>

        {/* Node States Tab */}
        <TabsContent value="nodes" className="space-y-4">
          {Object.entries(nodeStates).map(([nodeId, state]) => (
            <NodeStateCard key={nodeId} nodeId={nodeId} state={state} />
          ))}
        </TabsContent>

        {/* Final Output Tab */}
        <TabsContent value="output">
          {execution.final_output ? (
            <Card>
              <CardHeader>
                <CardTitle>Final Output</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-muted rounded text-sm overflow-x-auto">
                  {JSON.stringify(execution.final_output, null, 2)}
                </pre>
              </CardContent>
            </Card>
          ) : (
            <Card className="p-12 text-center">
              <div className="flex flex-col items-center gap-2">
                <AlertCircle className="h-8 w-8 text-muted-foreground" />
                <p className="text-muted-foreground">No final output available</p>
              </div>
            </Card>
          )}
        </TabsContent>
      </Tabs>
      </div>
    </div>
  );
}
