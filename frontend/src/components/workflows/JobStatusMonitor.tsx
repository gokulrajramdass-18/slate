/**
 * Job Status Monitor Component
 *
 * Real-time monitoring of scheduled workflow jobs.
 */

'use client';

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2, CheckCircle, XCircle, Clock, Calendar, Activity, RefreshCw } from 'lucide-react';
import { schedulerApi } from '@/lib/api/workflows';
import type { SchedulerJob } from '@/lib/api/workflows';
import { format, formatDistanceToNow } from 'date-fns';

// ============================================================================
// Job Status Card Component
// ============================================================================

function JobStatusCard({ job }: { job: SchedulerJob }) {
  const statusConfig = {
    pending: { icon: Clock, color: 'text-gray-500', bg: 'bg-gray-100' },
    running: { icon: Loader2, color: 'text-blue-500', bg: 'bg-blue-100' },
    completed: { icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-100' },
    failed: { icon: XCircle, color: 'text-red-500', bg: 'bg-red-100' },
    paused: { icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-100' },
  };

  const config = statusConfig[job.status || 'pending'];
  const Icon = config.icon;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-full ${config.bg}`}>
              <Icon
                className={`h-4 w-4 ${config.color} ${
                  job.status === 'running' ? 'animate-spin' : ''
                }`}
              />
            </div>
            <div>
              <CardTitle className="text-base">{job.name}</CardTitle>
              <CardDescription className="text-xs">
                ID: {job.id}
              </CardDescription>
            </div>
          </div>
          <Badge
            variant={
              job.status === 'completed'
                ? 'default'
                : job.status === 'failed'
                ? 'destructive'
                : job.status === 'running'
                ? 'default'
                : 'secondary'
            }
            className={job.status === 'completed' ? 'bg-green-500' : ''}
          >
            {job.status}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-4 text-sm">
          {job.next_run_time && (
            <div>
              <div className="text-muted-foreground text-xs">Next Run</div>
              <div className="font-medium">
                {format(new Date(job.next_run_time), 'PPp')}
              </div>
              <div className="text-xs text-muted-foreground">
                {formatDistanceToNow(new Date(job.next_run_time), { addSuffix: true })}
              </div>
            </div>
          )}

          {job.last_run_time && (
            <div>
              <div className="text-muted-foreground text-xs">Last Run</div>
              <div className="font-medium">
                {format(new Date(job.last_run_time), 'PPp')}
              </div>
              <div className="text-xs text-muted-foreground">
                {formatDistanceToNow(new Date(job.last_run_time), { addSuffix: true })}
              </div>
            </div>
          )}
        </div>

        {job.trigger && (
          <div>
            <div className="text-muted-foreground text-xs mb-1">Trigger</div>
            <div className="text-sm font-mono bg-muted px-2 py-1 rounded">
              {job.trigger}
            </div>
          </div>
        )}

        {job.execution_count !== undefined && (
          <div className="flex items-center gap-2 text-sm">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Executions:</span>
            <span className="font-medium">{job.execution_count}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Job Status Monitor Component
// ============================================================================

interface JobStatusMonitorProps {
  workflowId?: string;
}

export function JobStatusMonitor({ workflowId }: JobStatusMonitorProps) {
  const [activeTab, setActiveTab] = React.useState<'all' | 'active' | 'paused'>('all');

  // List all jobs with auto-refresh
  const { data: jobs, isLoading, refetch } = useQuery({
    queryKey: ['scheduler-jobs'],
    queryFn: schedulerApi.listJobs,
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Filter jobs
  const filteredJobs = React.useMemo(() => {
    if (!jobs || !Array.isArray(jobs)) return [];

    let filtered = jobs;

    // Filter by workflow if specified
    if (workflowId) {
      filtered = filtered.filter((job) => job.name.includes(workflowId));
    }

    // Filter by tab
    if (activeTab === 'active') {
      filtered = filtered.filter((job) => job.status !== 'paused');
    } else if (activeTab === 'paused') {
      filtered = filtered.filter((job) => job.status === 'paused');
    }

    return filtered;
  }, [jobs, workflowId, activeTab]);

  const activeCount = Array.isArray(jobs) ? jobs.filter((j) => j.status !== 'paused').length : 0;
  const pausedCount = Array.isArray(jobs) ? jobs.filter((j) => j.status === 'paused').length : 0;

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
            <p className="text-sm text-muted-foreground">Loading job status...</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Scheduled Jobs</h3>
          <p className="text-sm text-muted-foreground">
            Monitor active and paused scheduled workflow executions
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
        <TabsList>
          <TabsTrigger value="all">
            All
            {jobs && <Badge variant="secondary" className="ml-2">{jobs.length}</Badge>}
          </TabsTrigger>
          <TabsTrigger value="active">
            Active
            <Badge variant="secondary" className="ml-2">{activeCount}</Badge>
          </TabsTrigger>
          <TabsTrigger value="paused">
            Paused
            <Badge variant="secondary" className="ml-2">{pausedCount}</Badge>
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="space-y-4">
          {filteredJobs.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredJobs.map((job) => (
                <JobStatusCard key={job.id} job={job} />
              ))}
            </div>
          ) : (
            <Card className="p-12 text-center">
              <div className="flex flex-col items-center gap-2">
                <Calendar className="h-8 w-8 text-muted-foreground" />
                <p className="text-muted-foreground">
                  {activeTab === 'all' && 'No scheduled jobs found'}
                  {activeTab === 'active' && 'No active jobs'}
                  {activeTab === 'paused' && 'No paused jobs'}
                </p>
              </div>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Summary */}
      {jobs && jobs.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Jobs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{jobs.length}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Active
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-500">{activeCount}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Paused
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-500">{pausedCount}</div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
