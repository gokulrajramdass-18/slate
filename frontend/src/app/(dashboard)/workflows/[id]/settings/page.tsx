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
import { ArrowLeft, Plus, Calendar, Clock, Zap, GitBranch, MoreVertical, Trash2, Edit, Play } from 'lucide-react';
import { workflowsApi, schedulesApi, schedulerApi } from '@/lib/api/workflows';
import type { WorkflowSchedule } from '@/lib/api/workflows';
import { useToast } from '@/hooks/use-toast';
import { ScheduleDialog } from '@/components/workflows/ScheduleDialog';
import { JobStatusMonitor } from '@/components/workflows/JobStatusMonitor';
import { format } from 'date-fns';

// ============================================================================
// Schedule Card Component
// ============================================================================

function ScheduleCard({ schedule, workflowId }: { schedule: WorkflowSchedule; workflowId: string }) {
  const { toast } = useToast();
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
      toast({
        title: 'Success',
        description: `Schedule ${schedule.enabled ? 'disabled' : 'enabled'}`,
      });
      queryClient.invalidateQueries({ queryKey: ['schedules', workflowId] });
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to update schedule',
        variant: 'destructive',
      });
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: () => schedulesApi.delete(workflowId, schedule.id),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Schedule deleted',
      });
      queryClient.invalidateQueries({ queryKey: ['schedules', workflowId] });
      setShowDeleteDialog(false);
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to delete schedule',
        variant: 'destructive',
      });
    },
  });

  // Trigger manually mutation
  const triggerMutation = useMutation({
    mutationFn: () => workflowsApi.execute(workflowId),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Workflow execution started',
      });
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to execute workflow',
        variant: 'destructive',
      });
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
