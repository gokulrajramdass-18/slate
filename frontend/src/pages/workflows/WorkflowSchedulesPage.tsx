/**
 * Workflow Schedules Page
 *
 * Manage cron schedules, event triggers, and dependency chains for workflows.
 */

import React, { useState } from 'react';
import { useParams, useRouter } from '@/lib/routing/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  ArrowLeft,
  Plus,
  Clock,
  Zap,
  GitBranch,
  Trash2,
  Edit,
  Loader2,
} from 'lucide-react';
import { workflowsApi } from '@/lib/api/workflows';
import { useToast } from '@/hooks/use-toast';
import { formatDistanceToNow } from 'date-fns';

// ============================================================================
// Types
// ============================================================================

type ScheduleType = 'cron' | 'event' | 'dependency' | 'manual';

interface Schedule {
  id: string;
  workflow_id: string;
  schedule_type: ScheduleType;
  cron_expression?: string;
  event_trigger?: {
    event_type: string;
    filters?: Record<string, any>;
  };
  upstream_workflow_id?: string;
  enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
  created_at?: string;
  updated_at?: string;
}

// ============================================================================
// Schedule Dialog Component
// ============================================================================

interface ScheduleDialogProps {
  workflowId: string;
  schedule?: Schedule;
  onClose: () => void;
}

function ScheduleDialog({ workflowId, schedule, onClose }: ScheduleDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [scheduleType, setScheduleType] = useState<ScheduleType>(
    schedule?.schedule_type || 'cron'
  );
  const [cronExpression, setCronExpression] = useState(schedule?.cron_expression || '');
  const [eventType, setEventType] = useState(schedule?.event_trigger?.event_type || '');
  const [upstreamWorkflowId, setUpstreamWorkflowId] = useState(
    schedule?.upstream_workflow_id || ''
  );
  const [enabled, setEnabled] = useState(schedule?.enabled ?? true);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const data: any = {
        schedule_type: scheduleType,
        enabled,
      };

      if (scheduleType === 'cron') {
        data.cron_expression = cronExpression;
      } else if (scheduleType === 'event') {
        data.event_trigger = {
          event_type: eventType,
          filters: {},
        };
      } else if (scheduleType === 'dependency') {
        data.upstream_workflow_id = upstreamWorkflowId;
      }

      if (schedule) {
        return workflowsApi.updateSchedule(workflowId, schedule.id, data);
      } else {
        return workflowsApi.createSchedule(workflowId, data);
      }
    },
    onSuccess: () => {
      toast({
        title: 'Success',
        description: `Schedule ${schedule ? 'updated' : 'created'} successfully`,
      });
      queryClient.invalidateQueries({ queryKey: ['workflow-schedules', workflowId] });
      onClose();
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to save schedule',
        variant: 'destructive',
      });
    },
  });

  const handleSave = () => {
    // Validate based on schedule type
    if (scheduleType === 'cron' && !cronExpression) {
      toast({
        title: 'Validation Error',
        description: 'Cron expression is required',
        variant: 'destructive',
      });
      return;
    }

    if (scheduleType === 'event' && !eventType) {
      toast({
        title: 'Validation Error',
        description: 'Event type is required',
        variant: 'destructive',
      });
      return;
    }

    if (scheduleType === 'dependency' && !upstreamWorkflowId) {
      toast({
        title: 'Validation Error',
        description: 'Upstream workflow is required',
        variant: 'destructive',
      });
      return;
    }

    saveMutation.mutate();
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{schedule ? 'Edit Schedule' : 'Create Schedule'}</DialogTitle>
          <DialogDescription>
            Configure when and how this workflow should be executed automatically
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label>Schedule Type</Label>
            <Select value={scheduleType} onValueChange={(v) => setScheduleType(v as ScheduleType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cron">Cron (Time-based)</SelectItem>
                <SelectItem value="event">Event-driven</SelectItem>
                <SelectItem value="dependency">Dependency Chain</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {scheduleType === 'cron' && (
            <div>
              <Label>Cron Expression</Label>
              <Input
                placeholder="0 9 * * * (Every day at 9 AM)"
                value={cronExpression}
                onChange={(e) => setCronExpression(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                Examples: <code>0 9 * * *</code> (9 AM daily), <code>0 */6 * * *</code> (every 6 hours)
              </p>
            </div>
          )}

          {scheduleType === 'event' && (
            <div>
              <Label>Event Type</Label>
              <Select value={eventType} onValueChange={setEventType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select event type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="source_updated">Source Updated</SelectItem>
                  <SelectItem value="notebook_created">Notebook Created</SelectItem>
                  <SelectItem value="chat_completed">Chat Completed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {scheduleType === 'dependency' && (
            <div>
              <Label>Upstream Workflow</Label>
              <Input
                placeholder="Workflow ID"
                value={upstreamWorkflowId}
                onChange={(e) => setUpstreamWorkflowId(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                This workflow will execute when the upstream workflow completes
              </p>
            </div>
          )}

          <div className="flex items-center gap-2">
            <Switch checked={enabled} onCheckedChange={setEnabled} />
            <Label>Enabled</Label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Schedule'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============================================================================
// Schedules Page
// ============================================================================

export default function WorkflowSchedulesPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const workflowId = params.id as string;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | undefined>();

  const { data: workflow } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowsApi.get(workflowId),
  });

  const { data: schedules, isLoading } = useQuery({
    queryKey: ['workflow-schedules', workflowId],
    queryFn: () => workflowsApi.getSchedules(workflowId),
  });

  const deleteMutation = useMutation({
    mutationFn: (scheduleId: string) => workflowsApi.deleteSchedule(workflowId, scheduleId),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Schedule deleted successfully',
      });
      queryClient.invalidateQueries({ queryKey: ['workflow-schedules', workflowId] });
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to delete schedule',
        variant: 'destructive',
      });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ scheduleId, enabled }: { scheduleId: string; enabled: boolean }) =>
      workflowsApi.updateSchedule(workflowId, scheduleId, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow-schedules', workflowId] });
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to toggle schedule',
        variant: 'destructive',
      });
    },
  });

  const scheduleTypeConfig = {
    cron: { icon: Clock, label: 'Cron', color: 'text-blue-500' },
    event: { icon: Zap, label: 'Event', color: 'text-yellow-500' },
    dependency: { icon: GitBranch, label: 'Dependency', color: 'text-purple-500' },
    manual: { icon: Clock, label: 'Manual', color: 'text-gray-500' },
  };

  const handleCreate = () => {
    setEditingSchedule(undefined);
    setDialogOpen(true);
  };

  const handleEdit = (schedule: Schedule) => {
    setEditingSchedule(schedule);
    setDialogOpen(true);
  };

  const handleDelete = (scheduleId: string) => {
    if (confirm('Are you sure you want to delete this schedule?')) {
      deleteMutation.mutate(scheduleId);
    }
  };

  const handleToggle = (scheduleId: string, enabled: boolean) => {
    toggleMutation.mutate({ scheduleId, enabled });
  };

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
            <h1 className="text-3xl font-bold">Schedules</h1>
            {workflow && <p className="text-muted-foreground mt-1">{workflow.name}</p>}
          </div>
        </div>

        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          New Schedule
        </Button>
      </div>

      {/* Schedules Table */}
      {isLoading ? (
        <Card>
          <CardContent className="p-12">
            <div className="flex items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
              <span className="ml-3 text-muted-foreground">Loading schedules...</span>
            </div>
          </CardContent>
        </Card>
      ) : schedules && schedules.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Configuration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead>Next Run</TableHead>
                  <TableHead className="w-[150px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedules.map((schedule) => {
                  const config = scheduleTypeConfig[schedule.schedule_type];
                  const Icon = config.icon;

                  return (
                    <TableRow key={schedule.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Icon className={`h-4 w-4 ${config.color}`} />
                          <span className="font-medium">{config.label}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {schedule.schedule_type === 'cron' && (
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            {schedule.cron_expression}
                          </code>
                        )}
                        {schedule.schedule_type === 'event' && (
                          <Badge variant="outline">{schedule.event_trigger?.event_type}</Badge>
                        )}
                        {schedule.schedule_type === 'dependency' && (
                          <span className="text-sm text-muted-foreground">
                            Workflow: {schedule.upstream_workflow_id?.slice(0, 8)}...
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={schedule.enabled}
                          onCheckedChange={(checked) => handleToggle(schedule.id, checked)}
                        />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {schedule.last_run_at
                          ? formatDistanceToNow(new Date(schedule.last_run_at), {
                              addSuffix: true,
                            })
                          : 'Never'}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {schedule.next_run_at
                          ? formatDistanceToNow(new Date(schedule.next_run_at), {
                              addSuffix: true,
                            })
                          : '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(schedule)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(schedule.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <Card className="p-12 text-center">
          <div className="flex flex-col items-center gap-4">
            <div className="rounded-full bg-muted p-4">
              <Clock className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">No schedules configured</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Create a schedule to automate workflow execution
              </p>
            </div>
            <Button onClick={handleCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Create Schedule
            </Button>
          </div>
        </Card>
      )}

      {/* Schedule Dialog */}
      {dialogOpen && (
        <ScheduleDialog
          workflowId={workflowId}
          schedule={editingSchedule}
          onClose={() => setDialogOpen(false)}
        />
      )}
    </div>
  );
}
