/**
 * Schedule Dialog Component
 *
 * Create and edit workflow schedules with cron, event, and dependency triggers.
 */

'use client';

import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Calendar, Clock, Zap, GitBranch, Info } from 'lucide-react';
import { schedulesApi, workflowsApi } from '@/lib/api/workflows';
import type { WorkflowSchedule, ScheduleType, ScheduleCreate } from '@/lib/api/workflows';
import { useToast } from '@/hooks/use-toast';
import { CronBuilder } from './CronBuilder';

// ============================================================================
// Schedule Dialog Component
// ============================================================================

interface ScheduleDialogProps {
  workflowId: string;
  schedule?: WorkflowSchedule | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ScheduleDialog({
  workflowId,
  schedule,
  open,
  onOpenChange,
}: ScheduleDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const [scheduleType, setScheduleType] = React.useState<ScheduleType>(
    schedule?.schedule_type || 'cron'
  );
  const [cronExpression, setCronExpression] = React.useState(
    schedule?.cron_expression || '0 9 * * *'
  );
  const [eventType, setEventType] = React.useState(
    schedule?.event_trigger?.event_type || 'source_updated'
  );
  const [upstreamWorkflowId, setUpstreamWorkflowId] = React.useState(
    schedule?.upstream_workflow_id || ''
  );
  const [enabled, setEnabled] = React.useState(schedule?.enabled ?? true);

  // Load available workflows for dependency selection
  const { data: workflows } = useQuery({
    queryKey: ['workflows'],
    queryFn: () => workflowsApi.list(),
    enabled: scheduleType === 'dependency',
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: ScheduleCreate) => schedulesApi.create(workflowId, data),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Schedule created successfully',
      });
      queryClient.invalidateQueries({ queryKey: ['schedules', workflowId] });
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to create schedule',
        variant: 'destructive',
      });
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (data: Partial<WorkflowSchedule>) =>
      schedulesApi.update(workflowId, schedule!.id, data),
    onSuccess: () => {
      toast({
        title: 'Success',
        description: 'Schedule updated successfully',
      });
      queryClient.invalidateQueries({ queryKey: ['schedules', workflowId] });
      onOpenChange(false);
    },
    onError: (error: any) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to update schedule',
        variant: 'destructive',
      });
    },
  });

  const handleSave = () => {
    const baseData = {
      schedule_type: scheduleType,
      enabled,
    };

    let scheduleData: ScheduleCreate | Partial<WorkflowSchedule>;

    if (scheduleType === 'cron') {
      scheduleData = {
        ...baseData,
        cron_expression: cronExpression,
      };
    } else if (scheduleType === 'event') {
      scheduleData = {
        ...baseData,
        event_trigger: {
          event_type: eventType,
          filters: {},
        },
      };
    } else if (scheduleType === 'dependency') {
      scheduleData = {
        ...baseData,
        upstream_workflow_id: upstreamWorkflowId,
      };
    } else {
      scheduleData = baseData;
    }

    if (schedule) {
      updateMutation.mutate(scheduleData);
    } else {
      createMutation.mutate(scheduleData as ScheduleCreate);
    }
  };

  const scheduleTypeConfig = [
    {
      value: 'cron',
      label: 'Cron (Time-based)',
      description: 'Run on a schedule using cron expressions',
      icon: Clock,
    },
    {
      value: 'event',
      label: 'Event-driven',
      description: 'Trigger when specific events occur',
      icon: Zap,
    },
    {
      value: 'dependency',
      label: 'Dependency Chain',
      description: 'Run after another workflow completes',
      icon: GitBranch,
    },
    {
      value: 'manual',
      label: 'Manual Only',
      description: 'Only run when manually triggered',
      icon: Calendar,
    },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {schedule ? 'Edit Schedule' : 'Create Schedule'}
          </DialogTitle>
          <DialogDescription>
            Configure when and how this workflow should be executed automatically.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Schedule Type Selection */}
          <div className="space-y-3">
            <Label>Schedule Type</Label>
            <div className="grid grid-cols-2 gap-3">
              {scheduleTypeConfig.map((type) => {
                const Icon = type.icon;
                return (
                  <button
                    key={type.value}
                    type="button"
                    onClick={() => setScheduleType(type.value as ScheduleType)}
                    className={`p-4 border rounded-lg text-left transition-all ${
                      scheduleType === type.value
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <Icon className="h-5 w-5 mt-0.5 flex-shrink-0" />
                      <div className="space-y-1">
                        <div className="font-medium">{type.label}</div>
                        <div className="text-xs text-muted-foreground">
                          {type.description}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Cron Configuration */}
          {scheduleType === 'cron' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Cron Expression</Label>
                <CronBuilder
                  value={cronExpression}
                  onChange={setCronExpression}
                />
              </div>

              <div className="bg-muted/50 p-4 rounded-lg space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Info className="h-4 w-4" />
                  Common Examples
                </div>
                <div className="text-xs text-muted-foreground space-y-1">
                  <div><code className="bg-background px-2 py-0.5 rounded">0 9 * * *</code> - Every day at 9:00 AM</div>
                  <div><code className="bg-background px-2 py-0.5 rounded">0 */6 * * *</code> - Every 6 hours</div>
                  <div><code className="bg-background px-2 py-0.5 rounded">*/15 * * * *</code> - Every 15 minutes</div>
                  <div><code className="bg-background px-2 py-0.5 rounded">0 0 * * 1</code> - Every Monday at midnight</div>
                  <div><code className="bg-background px-2 py-0.5 rounded">0 0 1 * *</code> - First day of every month at midnight</div>
                  <div><code className="bg-background px-2 py-0.5 rounded">0 12 * * 1-5</code> - Weekdays at noon</div>
                  <div><code className="bg-background px-2 py-0.5 rounded">0 0,12 * * *</code> - Every day at midnight and noon</div>
                  <div><code className="bg-background px-2 py-0.5 rounded">0 8-18 * * 1-5</code> - Every hour from 8 AM to 6 PM on weekdays</div>
                </div>
              </div>
            </div>
          )}

          {/* Event Configuration */}
          {scheduleType === 'event' && (
            <div className="space-y-3">
              <Label>Event Type</Label>
              <Select value={eventType} onValueChange={setEventType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="source_updated">Source Updated</SelectItem>
                  <SelectItem value="notebook_created">Notebook Created</SelectItem>
                  <SelectItem value="chat_completed">Chat Completed</SelectItem>
                  <SelectItem value="workflow_completed">Workflow Completed</SelectItem>
                  <SelectItem value="api_webhook">API Webhook</SelectItem>
                </SelectContent>
              </Select>

              <div className="bg-muted/50 p-4 rounded-lg">
                <div className="text-sm">
                  <div className="font-medium mb-2">Event Description</div>
                  <div className="text-muted-foreground text-xs">
                    {eventType === 'source_updated' && 'Triggers when any source in a notebook is updated or synced'}
                    {eventType === 'notebook_created' && 'Triggers when a new notebook is created'}
                    {eventType === 'chat_completed' && 'Triggers when a chat session completes'}
                    {eventType === 'workflow_completed' && 'Triggers when any workflow execution completes'}
                    {eventType === 'api_webhook' && 'Triggers when an external webhook is received'}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Dependency Configuration */}
          {scheduleType === 'dependency' && (
            <div className="space-y-3">
              <Label>Upstream Workflow</Label>
              <Select
                value={upstreamWorkflowId}
                onValueChange={setUpstreamWorkflowId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select workflow" />
                </SelectTrigger>
                <SelectContent>
                  {workflows?.filter((w) => w.id !== workflowId).map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <div className="bg-muted/50 p-4 rounded-lg">
                <div className="text-sm">
                  <div className="font-medium mb-2">Dependency Chain</div>
                  <div className="text-muted-foreground text-xs">
                    This workflow will automatically execute after the selected upstream workflow completes successfully.
                    The output from the upstream workflow will be passed as input to this workflow.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Manual Configuration */}
          {scheduleType === 'manual' && (
            <div className="bg-muted/50 p-4 rounded-lg">
              <div className="text-sm">
                <div className="font-medium mb-2">Manual Execution Only</div>
                <div className="text-muted-foreground text-xs">
                  This workflow will only run when manually triggered. No automatic execution will occur.
                </div>
              </div>
            </div>
          )}

          {/* Enable/Disable Toggle */}
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="space-y-1">
              <Label className="text-base">Enable Schedule</Label>
              <div className="text-xs text-muted-foreground">
                {enabled
                  ? 'Schedule is active and will execute as configured'
                  : 'Schedule is paused and will not execute'}
              </div>
            </div>
            <Switch checked={enabled} onCheckedChange={setEnabled} />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={createMutation.isPending || updateMutation.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={
              createMutation.isPending ||
              updateMutation.isPending ||
              (scheduleType === 'dependency' && !upstreamWorkflowId)
            }
          >
            {createMutation.isPending || updateMutation.isPending
              ? 'Saving...'
              : schedule
              ? 'Update Schedule'
              : 'Create Schedule'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
