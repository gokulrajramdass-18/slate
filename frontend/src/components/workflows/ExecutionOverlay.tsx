/**
 * Execution Overlay Component
 *
 * Displays real-time execution status overlaid on the workflow graph.
 */

'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2, CheckCircle, XCircle, Clock, X, Eye, FileText, ExternalLink, BookOpen, Globe, AlertTriangle } from 'lucide-react';
import { useGraphStore } from '@/lib/stores/graph-store';
import type { WorkflowExecution } from '@/lib/api/workflows';
import { cn } from '@/lib/utils';

// ============================================================================
// Execution Overlay Component
// ============================================================================

interface ExecutionOverlayProps {
  execution: WorkflowExecution | null;
  onClose?: () => void;
}

export function ExecutionOverlay({ execution, onClose }: ExecutionOverlayProps) {
  // NOTE: We do NOT update node statuses in the graph store during execution.
  // The execution status is shown in this overlay only. The graph is read-only during execution.

  const [showDetails, setShowDetails] = useState(false);

  if (!execution) return null;

  const statusConfig = {
    pending: { icon: Clock, color: 'text-gray-500', variant: 'secondary' as const },
    running: { icon: Loader2, color: 'text-blue-500', variant: 'default' as const },
    paused: { icon: Clock, color: 'text-yellow-500', variant: 'outline' as const },
    completed: { icon: CheckCircle, color: 'text-green-500', variant: 'default' as const },
    failed: { icon: XCircle, color: 'text-red-500', variant: 'destructive' as const },
    cancelled: { icon: XCircle, color: 'text-gray-500', variant: 'secondary' as const },
  };

  const config = statusConfig[execution.status] || statusConfig.pending;
  const Icon = config.icon;

  const nodeStates = execution.node_states || {};
  const totalNodes = Object.keys(nodeStates).length;
  const completedNodes = Object.values(nodeStates).filter(
    (n) => n.status === 'completed'
  ).length;
  const failedNodes = Object.values(nodeStates).filter(
    (n) => n.status === 'failed'
  ).length;
  const runningNodes = Object.values(nodeStates).filter(
    (n) => n.status === 'running'
  ).length;

  const progress = (completedNodes / totalNodes) * 100;

  return (
    <Card className="absolute bottom-4 right-4 w-96 z-10 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon
              className={`h-5 w-5 ${config.color} ${
                execution.status === 'running' ? 'animate-spin' : ''
              }`}
            />
            <CardTitle className="text-base">Execution Status</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={config.variant}>{execution.status}</Badge>
            {onClose && (
              <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium">{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Node Counts */}
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div className="text-center p-2 bg-muted rounded">
            <div className="font-bold text-lg">{completedNodes}</div>
            <div className="text-xs text-muted-foreground">Completed</div>
          </div>
          <div className="text-center p-2 bg-muted rounded">
            <div className="font-bold text-lg">{runningNodes}</div>
            <div className="text-xs text-muted-foreground">Running</div>
          </div>
          <div className="text-center p-2 bg-muted rounded">
            <div className="font-bold text-lg">{failedNodes}</div>
            <div className="text-xs text-muted-foreground">Failed</div>
          </div>
        </div>

        {/* Current Node */}
        {runningNodes > 0 && (
          <div className="p-3 bg-blue-50 dark:bg-blue-950 rounded">
            <div className="flex items-center gap-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span className="font-medium">Running:</span>
              <span className="text-muted-foreground">
                {Object.entries(nodeStates)
                  .filter(([, state]) => state.status === 'running')
                  .map(([nodeId]) => nodeId)
                  .join(', ')}
              </span>
            </div>
          </div>
        )}

        {/* Error Summary */}
        {failedNodes > 0 && (
          <div className="p-3 bg-destructive/10 rounded">
            <div className="flex items-start gap-2 text-sm">
              <XCircle className="h-4 w-4 text-destructive mt-0.5" />
              <div>
                <div className="font-medium text-destructive">{failedNodes} node(s) failed</div>
                {Object.entries(nodeStates)
                  .filter(([, state]) => state.status === 'failed' && state.error)
                  .map(([nodeId, state]) => (
                    <div key={nodeId} className="text-xs text-muted-foreground mt-1">
                      {nodeId}: {state.error}
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}

        {/* Completion Message */}
        {execution.status === 'completed' && (
          <div className="p-3 bg-green-50 dark:bg-green-950 rounded">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="font-medium text-green-700 dark:text-green-300">
                Workflow completed successfully!
              </span>
            </div>
          </div>
        )}

        {/* Timestamps */}
        <div className="text-xs text-muted-foreground space-y-1">
          <div>Started: {new Date(execution.started_at).toLocaleTimeString()}</div>
          {execution.completed_at && (
            <div>Completed: {new Date(execution.completed_at).toLocaleTimeString()}</div>
          )}
        </div>

        {/* View Details Button */}
        {execution.status === 'completed' && (
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => setShowDetails(true)}
          >
            <Eye className="h-4 w-4 mr-2" />
            View Execution Details
          </Button>
        )}
      </CardContent>

      {/* Detailed Results Dialog */}
      <ExecutionDetailsDialog
        execution={execution}
        open={showDetails}
        onOpenChange={setShowDetails}
      />
    </Card>
  );
}

// ============================================================================
// Artifact Links Component
// ============================================================================

interface ArtifactLinksProps {
  output: any;
}

function ArtifactLinks({ output }: ArtifactLinksProps) {
  if (!output || typeof output !== 'object') return null;

  const hasNotebookId = 'notebook_id' in output && output.notebook_id;
  const hasMicrositeId = 'microsite_id' in output && output.microsite_id;
  const hasPreviewUrl = 'preview_url' in output && output.preview_url;
  const hasModerationStatus = 'moderation_status' in output;

  if (!hasNotebookId && !hasMicrositeId) return null;

  const getModerationColor = (status: string) => {
    if (status === 'passed') return 'text-green-600 dark:text-green-400';
    if (status === 'blocked') return 'text-red-600 dark:text-red-400';
    if (status === 'flagged') return 'text-yellow-600 dark:text-yellow-400';
    return 'text-gray-600 dark:text-gray-400';
  };

  return (
    <div className="mt-2 space-y-2">
      {/* Notebook Link */}
      {hasNotebookId && (
        <a
          href={`/workspaces/${output.notebook_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-xs text-purple-600 hover:text-purple-700 dark:text-purple-400 dark:hover:text-purple-300 transition-colors"
        >
          <BookOpen className="h-3.5 w-3.5" />
          <span className="font-medium">Notebook:</span>
          <span className="font-mono">{output.notebook_id.substring(0, 8)}...</span>
          <ExternalLink className="h-3 w-3" />
        </a>
      )}

      {/* Microsite Preview Link */}
      {hasMicrositeId && hasPreviewUrl && (
        <a
          href={output.preview_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-xs text-pink-600 hover:text-pink-700 dark:text-pink-400 dark:hover:text-pink-300 transition-colors"
        >
          <Globe className="h-3.5 w-3.5" />
          <span className="font-medium">Microsite Preview</span>
          <ExternalLink className="h-3 w-3" />
        </a>
      )}

      {/* Moderation Status */}
      {hasModerationStatus && (
        <div className={`flex items-center gap-2 text-xs ${getModerationColor(output.moderation_status)}`}>
          {output.moderation_status === 'blocked' && <AlertTriangle className="h-3.5 w-3.5" />}
          {output.moderation_status === 'passed' && <CheckCircle className="h-3.5 w-3.5" />}
          <span className="font-medium">Moderation:</span>
          <span className="uppercase font-semibold">{output.moderation_status}</span>
        </div>
      )}

      {/* Auto-Created Notebook Indicator */}
      {output.auto_created_notebook && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <CheckCircle className="h-3.5 w-3.5" />
          <span>Notebook auto-created</span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Execution Details Dialog
// ============================================================================

interface ExecutionDetailsDialogProps {
  execution: WorkflowExecution;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function ExecutionDetailsDialog({
  execution,
  open,
  onOpenChange,
}: ExecutionDetailsDialogProps) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  const nodeStates = execution.node_states || {};
  const nodeEntries = Object.entries(nodeStates);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>Execution Details</DialogTitle>
          <DialogDescription>
            View node outputs and execution details for this workflow run
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="overview" className="w-full">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="nodes">Node Outputs</TabsTrigger>
            <TabsTrigger value="raw">Raw Data</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="text-sm font-medium">Execution ID</div>
                <div className="text-xs text-muted-foreground font-mono">{execution.id}</div>
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium">Status</div>
                <Badge variant={execution.status === 'completed' ? 'default' : 'destructive'}>
                  {execution.status}
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium">Started At</div>
                <div className="text-xs text-muted-foreground">
                  {new Date(execution.started_at).toLocaleString()}
                </div>
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium">Duration</div>
                <div className="text-xs text-muted-foreground">
                  {execution.completed_at
                    ? `${Math.round(
                        (new Date(execution.completed_at).getTime() -
                          new Date(execution.started_at).getTime()) /
                          1000
                      )}s`
                    : 'In progress'}
                </div>
              </div>
            </div>

            {/* Node Summary */}
            <div className="space-y-2">
              <div className="text-sm font-medium">Node Execution Summary</div>
              <ScrollArea className="h-[300px] border rounded-lg p-4">
                <div className="space-y-3">
                  {nodeEntries.map(([nodeId, state]) => (
                    <div
                      key={nodeId}
                      className="p-3 border rounded-lg hover:bg-accent/50 transition-colors cursor-pointer"
                      onClick={() => {
                        setSelectedNode(nodeId);
                      }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-medium text-sm">{nodeId}</div>
                        <Badge
                          variant={
                            state.status === 'completed'
                              ? 'default'
                              : state.status === 'failed'
                              ? 'destructive'
                              : 'secondary'
                          }
                        >
                          {state.status}
                        </Badge>
                      </div>
                      {state.error && (
                        <div className="text-xs text-destructive">{state.error}</div>
                      )}
                      {state.output_data && (
                        <>
                          <ArtifactLinks output={state.output_data} />
                          <div className="text-xs text-muted-foreground mt-2">
                            Click to view output
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </TabsContent>

          {/* Node Outputs Tab */}
          <TabsContent value="nodes" className="space-y-4">
            <div className="grid grid-cols-4 gap-2">
              {nodeEntries.map(([nodeId, nodeState]) => {
                const typeLabel = nodeId.split('-')[0];
                const idSuffix = nodeId.length > 8 ? nodeId.slice(-4) : '';
                const status = nodeState.status;
                const isSelected = selectedNode === nodeId;
                const failed = status === 'failed';
                return (
                  <Button
                    key={nodeId}
                    variant={isSelected ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setSelectedNode(nodeId)}
                    className={cn(
                      'justify-start',
                      !isSelected && failed && 'border-destructive/60 text-destructive hover:text-destructive',
                    )}
                    title={`${nodeId} · ${status}`}
                  >
                    <FileText className="h-3 w-3 mr-2 shrink-0" />
                    <span className="truncate">{typeLabel}</span>
                    {idSuffix && (
                      <span className="ml-1 text-[10px] font-mono opacity-60">…{idSuffix}</span>
                    )}
                  </Button>
                );
              })}
            </div>

            {selectedNode && nodeStates[selectedNode] && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">{selectedNode}</div>
                  <Badge
                    variant={
                      nodeStates[selectedNode].status === 'completed'
                        ? 'default'
                        : 'destructive'
                    }
                  >
                    {nodeStates[selectedNode].status}
                  </Badge>
                </div>

                {nodeStates[selectedNode].error && (
                  <div className="p-3 bg-destructive/10 rounded text-sm text-destructive">
                    {nodeStates[selectedNode].error}
                  </div>
                )}

                {nodeStates[selectedNode].output_data ? (
                  <>
                    <ArtifactLinks output={nodeStates[selectedNode].output_data} />
                    <ScrollArea className="h-[400px] border rounded-lg">
                      <pre className="p-4 text-xs">
                        {JSON.stringify(nodeStates[selectedNode].output_data, null, 2)}
                      </pre>
                    </ScrollArea>
                  </>
                ) : (
                  <div className="p-8 text-center text-muted-foreground text-sm border rounded-lg">
                    No output available for this node
                  </div>
                )}
              </div>
            )}

            {!selectedNode && (
              <div className="p-8 text-center text-muted-foreground text-sm border rounded-lg">
                Select a node to view its output
              </div>
            )}
          </TabsContent>

          {/* Raw Data Tab */}
          <TabsContent value="raw">
            <ScrollArea className="h-[500px] border rounded-lg">
              <pre className="p-4 text-xs">
                {JSON.stringify(execution, null, 2)}
              </pre>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
