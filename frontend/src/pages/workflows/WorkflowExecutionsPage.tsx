/**
 * Execution History Page
 *
 * Displays execution history for a workflow in a table with pagination.
 */

import React, { useState } from 'react';
import { useParams, useRouter } from '@/lib/routing/navigation';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ArrowLeft,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  Play,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { workflowsApi } from '@/lib/api/workflows';
import type { WorkflowExecution } from '@/lib/api/workflows';
import { formatDistanceToNow } from 'date-fns';

// ============================================================================
// Execution History Page
// ============================================================================

const ITEMS_PER_PAGE = 10;

export default function WorkflowExecutionsPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const workflowId = params.id as string;
  const [currentPage, setCurrentPage] = useState(1);

  const { data: workflow } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowsApi.get(workflowId),
  });

  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions', workflowId],
    queryFn: () => workflowsApi.getExecutions(workflowId),
    refetchInterval: 5000, // Refetch every 5 seconds for running executions
    refetchOnMount: 'always', // Always refetch when the page is opened
    staleTime: 0, // Treat data as stale immediately so navigating back triggers a refetch
  });

  const statusConfig = {
    pending: { icon: Clock, variant: 'secondary' as const, color: 'text-gray-500' },
    running: { icon: Loader2, variant: 'default' as const, color: 'text-blue-500' },
    paused: { icon: Clock, variant: 'outline' as const, color: 'text-yellow-500' },
    completed: { icon: CheckCircle, variant: 'default' as const, color: 'text-green-500' },
    failed: { icon: XCircle, variant: 'destructive' as const, color: 'text-red-500' },
    cancelled: { icon: XCircle, variant: 'secondary' as const, color: 'text-gray-500' },
  };

  const formatDuration = (started: string, completed?: string) => {
    if (!completed) return 'In progress';
    const ms = new Date(completed).getTime() - new Date(started).getTime();
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  // Pagination
  const totalPages = Math.ceil((executions?.length || 0) / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = startIndex + ITEMS_PER_PAGE;
  const paginatedExecutions = executions?.slice(startIndex, endIndex) || [];

  const goToFirstPage = () => setCurrentPage(1);
  const goToPreviousPage = () => setCurrentPage((prev) => Math.max(1, prev - 1));
  const goToNextPage = () => setCurrentPage((prev) => Math.min(totalPages, prev + 1));
  const goToLastPage = () => setCurrentPage(totalPages);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push(`/workflows/${workflowId}`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">Execution History</h1>
            {workflow && (
              <p className="text-muted-foreground mt-1">{workflow.name}</p>
            )}
          </div>
        </div>

        <Button onClick={() => router.push(`/workflows/${workflowId}`)}>
          <Play className="mr-2 h-4 w-4" />
          Execute Workflow
        </Button>
      </div>

      {/* Executions Table */}
      {isLoading ? (
        <Card>
          <CardContent className="p-12">
            <div className="flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <span className="ml-3 text-muted-foreground">Loading executions...</span>
            </div>
          </CardContent>
        </Card>
      ) : executions && executions.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[100px]">Status</TableHead>
                  <TableHead>Execution ID</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead className="text-center">Nodes</TableHead>
                  <TableHead>Triggered By</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedExecutions.map((execution) => {
                  const config = statusConfig[execution.status];
                  const Icon = config.icon;
                  const nodeStates = Object.values(execution.node_states || {});
                  const completedNodes = nodeStates.filter((n) => n.status === 'completed').length;
                  const failedNodes = nodeStates.filter((n) => n.status === 'failed').length;
                  const totalNodes = nodeStates.length;

                  return (
                    <TableRow
                      key={execution.id}
                      className="cursor-pointer hover:bg-accent/50"
                      onClick={() => router.push(`/workflows/${workflowId}/executions/${execution.id}`)}
                    >
                      <TableCell>
                        <Badge
                          variant={config.variant}
                          className={`flex items-center gap-1 w-fit ${
                            execution.status === 'completed' ? 'bg-green-500 hover:bg-green-600' :
                            execution.status === 'failed' ? 'bg-red-500 hover:bg-red-600' :
                            ''
                          }`}
                        >
                          <Icon className={`h-3 w-3 ${execution.status === 'running' ? 'animate-spin' : ''}`} />
                          {execution.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {execution.id.slice(0, 8)}...
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDistanceToNow(new Date(execution.started_at), { addSuffix: true })}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDuration(execution.started_at, execution.completed_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-center gap-3 text-sm">
                          <span className="flex items-center gap-1">
                            <CheckCircle className="h-3 w-3 text-green-500" />
                            {completedNodes}
                          </span>
                          {failedNodes > 0 && (
                            <span className="flex items-center gap-1">
                              <XCircle className="h-3 w-3 text-red-500" />
                              {failedNodes}
                            </span>
                          )}
                          <span className="text-muted-foreground">/ {totalNodes}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {execution.triggered_by}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/workflows/${workflowId}/executions/${execution.id}`);
                          }}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-4 border-t">
                <div className="text-sm text-muted-foreground">
                  Showing {startIndex + 1} to {Math.min(endIndex, executions.length)} of {executions.length} executions
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goToFirstPage}
                    disabled={currentPage === 1}
                  >
                    <ChevronsLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goToPreviousPage}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <div className="text-sm font-medium px-3">
                    Page {currentPage} of {totalPages}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goToNextPage}
                    disabled={currentPage === totalPages}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={goToLastPage}
                    disabled={currentPage === totalPages}
                  >
                    <ChevronsRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="p-12 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="rounded-full bg-muted p-4">
              <Clock className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">No executions yet</h3>
              <p className="text-sm text-muted-foreground mt-1">
                This workflow hasn't been executed
              </p>
            </div>
            <Button onClick={() => router.push(`/workflows/${workflowId}`)}>
              <Play className="mr-2 h-4 w-4" />
              Execute Workflow
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
