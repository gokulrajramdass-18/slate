/**
 * Workflow Settings Page
 *
 * Manage schedules and workflow settings.
 */

'use client';

import React from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ArrowLeft, Plus, Calendar, Clock, Zap, GitBranch, MoreVertical, Trash2, Edit, Play, Database, Loader2 } from 'lucide-react';
import { workflowsApi, schedulesApi, schedulerApi } from '@/lib/api/workflows';
import type { WorkflowSchedule } from '@/lib/api/workflows';
import { toast } from 'sonner';
import { ScheduleDialog } from '@/components/workflows/ScheduleDialog';
import { JobStatusMonitor } from '@/components/workflows/JobStatusMonitor';
import { format, formatDistanceToNow } from 'date-fns';
import { apiClient } from '@/lib/api/client';

// ============================================================================
// Schedule Card Component
// ============================================================================

function ScheduleCard({ schedule, workflowId }: { schedule: WorkflowSchedule; workflowId: string }) {
  const queryClient = useQueryClient();
  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [showEditDialog, setShowEditDialog] = React.useState(false);

  // Toggle enabled mutation
  const toggleMutation = useMutation({
    mutationFn: () =>
      schedulesApi.update(workflowId, schedule.id, {
        enabled: !schedule.enabled,
      }),
    onSuccess: () => {
      toast.success(`Schedule ${schedule.enabled ? 'disabled' : 'enabled'}`);
      queryClient.invalidateQueries({ queryKey: ['schedules', workflowId] });
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to update schedule');
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => schedulesApi.delete(workflowId, schedule.id),
    onSuccess: () => {
      toast.success('Schedule deleted');
      queryClient.invalidateQueries({ queryKey: ['schedules', workflowId] });
      setShowDeleteDialog(false);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete schedule');
    },
  });

  // Trigger manually mutation
  const triggerMutation = useMutation({
    mutationFn: () => workflowsApi.execute(workflowId),
    onSuccess: () => {
      toast.success('Workflow execution started');
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to execute workflow');
    },
  });

  const typeConfig = {
    cron: { icon: Clock, label: 'Cron', color: 'text-blue-500' },
    event: { icon: Zap, label: 'Event', color: 'text-yellow-500' },
    dependency: { icon: GitBranch, label: 'Dependency', color: 'text-purple-500' },
    manual: { icon: Calendar, label: 'Manual', color: 'text-gray-500' },
  };

  const config = typeConfig[schedule.schedule_type];
  const Icon = config.icon;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-full bg-muted ${config.color}`}>
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <CardTitle className="text-base">{config.label} Schedule</CardTitle>
                <CardDescription className="text-xs">
                  {schedule.schedule_type === 'cron' && `Runs: ${schedule.cron_expression}`}
                  {schedule.schedule_type === 'event' && `Event: ${schedule.event_trigger?.event_type}`}
                  {schedule.schedule_type === 'dependency' && `After: Upstream workflow`}
                  {schedule.schedule_type === 'manual' && `Manual execution only`}
                </CardDescription>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Switch
                checked={schedule.enabled}
                onCheckedChange={() => toggleMutation.mutate()}
                disabled={toggleMutation.isPending}
              />

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => triggerMutation.mutate()}>
                    <Play className="h-4 w-4 mr-2" />
                    Trigger Now
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setShowEditDialog(true)}>
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={() => setShowDeleteDialog(true)}
                    className="text-destructive"
                  >
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            {schedule.last_run_at && (
              <div>
                <div className="text-muted-foreground text-xs">Last Run</div>
                <div className="font-medium">{format(new Date(schedule.last_run_at), 'PPp')}</div>
              </div>
            )}
            {schedule.next_run_at && (
              <div>
                <div className="text-muted-foreground text-xs">Next Run</div>
                <div className="font-medium">{format(new Date(schedule.next_run_at), 'PPp')}</div>
              </div>
            )}
          </div>

          <div>
            <Badge variant={schedule.enabled ? 'default' : 'secondary'}>
              {schedule.enabled ? 'Active' : 'Paused'}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {/* Delete Confirmation */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Schedule</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this schedule? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Edit Dialog */}
      <ScheduleDialog
        workflowId={workflowId}
        schedule={schedule}
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
      />
    </>
  );
}

// ============================================================================
// Snapshots Section Component
// ============================================================================

function SnapshotsSection({ workflowId }: { workflowId: string }) {
  const queryClient = useQueryClient();
  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [snapshotToDelete, setSnapshotToDelete] = React.useState<string | null>(null);

  // Fetch snapshots for this workflow
  const { data: snapshots, isLoading, isFetching } = useQuery({
    queryKey: ['snapshots', workflowId],
    queryFn: async () => {
      const { data } = await apiClient.get('/snapshots/', {
        params: { workflow_id: workflowId }
      });
      return data;
    },
    refetchInterval: 5000, // Auto-refresh every 5 seconds
  });

  // Check if there are any recent executions (within last 30 seconds)
  const hasRecentExecution = React.useMemo(() => {
    if (!snapshots || snapshots.length === 0) return false;
    const latestSnapshot = snapshots[0];
    const snapshotDate = new Date(latestSnapshot.snapshot_date);
    const now = new Date();
    const diffSeconds = (now.getTime() - snapshotDate.getTime()) / 1000;
    return diffSeconds < 30;
  }, [snapshots]);

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (snapshotId: string) => {
      await apiClient.delete(`/snapshots/${snapshotId}`);
    },
    onSuccess: () => {
      toast.success('Snapshot deleted');
      queryClient.invalidateQueries({ queryKey: ['snapshots', workflowId] });
      setShowDeleteDialog(false);
      setSnapshotToDelete(null);
    },
    onError: (error: any) => {
      toast.error(error.message || 'Failed to delete snapshot');
    },
  });

  const handleDelete = (snapshotId: string) => {
    setSnapshotToDelete(snapshotId);
    setShowDeleteDialog(true);
  };

  const confirmDelete = () => {
    if (snapshotToDelete) {
      deleteMutation.mutate(snapshotToDelete);
    }
  };

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['snapshots', workflowId] });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Database className="h-5 w-5" />
            Snapshots
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Data snapshots captured during workflow executions
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={isLoading || isFetching}
          className="flex items-center gap-2"
        >
          {(isLoading || isFetching) ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={isFetching ? 'animate-spin' : ''}
            >
              <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
            </svg>
          )}
          Refresh
        </Button>
      </div>

      {/* Status indicator */}
      {isFetching && !isLoading && (
        <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg text-sm text-blue-900 dark:text-blue-100">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Checking for new snapshots...</span>
        </div>
      )}

      {hasRecentExecution && !isFetching && (
        <div className="flex items-center gap-2 px-3 py-2 bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800 rounded-lg text-sm text-green-900 dark:text-green-100">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-4 w-4"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>New snapshot generated recently</span>
        </div>
      )}

      {isLoading ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center p-8 space-y-3">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Loading snapshots...</p>
          </CardContent>
        </Card>
      ) : snapshots && snapshots.length > 0 ? (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-2 text-sm text-muted-foreground">
            <span>{snapshots.length} snapshot(s) found</span>
          </div>
          <div className="border rounded-lg divide-y">
            {snapshots.map((snapshot: any, index: number) => (
              <div key={snapshot.id} className="p-4 hover:bg-muted/50">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs bg-muted px-2 py-1 rounded">
                        ID: {snapshot.id.substring(0, 12)}...
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {snapshot.storage_type}
                      </Badge>
                      {index === 0 && (
                        <Badge className="text-xs bg-green-500 hover:bg-green-600">
                          Current
                        </Badge>
                      )}
                      {index === 1 && (
                        <Badge variant="secondary" className="text-xs">
                          Previous
                        </Badge>
                      )}
                      {snapshot.snapshot_label && (
                        <Badge variant="secondary" className="text-xs">
                          {snapshot.snapshot_label}
                        </Badge>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-muted-foreground">Node ID:</span>{' '}
                        <span className="font-mono text-xs">{snapshot.node_id}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Rows:</span>{' '}
                        <span className="font-semibold">{snapshot.row_count?.toLocaleString() || 0}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Created:</span>{' '}
                        <span>{formatDistanceToNow(new Date(snapshot.snapshot_date), { addSuffix: true })}</span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Date:</span>{' '}
                        <span className="text-xs">{format(new Date(snapshot.snapshot_date), 'PPp')}</span>
                      </div>
                      {snapshot.execution_id && (
                        <div className="col-span-2">
                          <span className="text-muted-foreground">Execution ID:</span>{' '}
                          <span className="font-mono text-xs">{snapshot.execution_id.substring(0, 12)}...</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(snapshot.id)}
                    disabled={deleteMutation.isPending}
                    className="shrink-0"
                  >
                    {deleteMutation.isPending && snapshotToDelete === snapshot.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4 text-destructive" />
                    )}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <Card className="p-8 text-center">
          <div className="flex flex-col items-center gap-3">
            <Database className="h-8 w-8 text-muted-foreground" />
            <div>
              <h3 className="font-semibold">No snapshots yet</h3>
              <p className="text-sm text-muted-foreground">
                Snapshots will appear here after executing workflows with HANA Table or API nodes that have "Enable Snapshots" checked
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                Enable snapshots on HANA/API nodes to track data changes over time
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Snapshot?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the snapshot data. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// ============================================================================
// Workflow Settings Page
// ============================================================================

export default function WorkflowSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const [showCreateDialog, setShowCreateDialog] = React.useState(false);

  const { data: workflow } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowsApi.get(workflowId),
  });

  const { data: schedules, isLoading } = useQuery({
    queryKey: ['schedules', workflowId],
    queryFn: () => schedulesApi.list(workflowId),
  });

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto" />
          <p className="mt-4 text-muted-foreground">Loading schedules...</p>
        </div>
      </div>
    );
  }

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
            <h1 className="text-3xl font-bold">Workflow Settings</h1>
            {workflow && (
              <p className="text-muted-foreground mt-1">{workflow.name}</p>
            )}
          </div>
        </div>

        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          New Schedule
        </Button>
      </div>

      {/* Schedules Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Schedules</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Configure when and how this workflow should execute automatically
          </p>
        </div>

        {schedules && schedules.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {schedules.map((schedule) => (
              <ScheduleCard
                key={schedule.id}
                schedule={schedule}
                workflowId={workflowId}
              />
            ))}
          </div>
        ) : (
          <Card className="p-12 text-center">
            <div className="flex flex-col items-center gap-4">
              <div className="p-4 rounded-full bg-muted">
                <Calendar className="h-8 w-8 text-muted-foreground" />
              </div>
              <div>
                <h3 className="font-semibold mb-1">No schedules configured</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Create a schedule to automate workflow execution
                </p>
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Schedule
                </Button>
              </div>
            </div>
          </Card>
        )}
      </div>

      {/* Snapshots Section */}
      <SnapshotsSection workflowId={workflowId} />

      {/* Job Status Monitor */}
      <JobStatusMonitor workflowId={workflowId} />

      {/* Create Dialog */}
      <ScheduleDialog
        workflowId={workflowId}
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
      />
    </div>
  );
}
