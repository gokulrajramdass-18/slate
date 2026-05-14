/**
 * Orchestration Page
 *
 * Main page for triggering and monitoring autonomous agent orchestrations.
 */


import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Play, Loader2, RefreshCw, Trash2, Database, FileText, Search, Filter, Calendar, Clock, Settings, Sparkles } from 'lucide-react';
import { AgentCollaborationGraph } from '@/components/orchestration/AgentCollaborationGraph';
import { OrchestrationProgress } from '@/components/orchestration/OrchestrationProgress';
import { ScheduleActions } from '@/components/orchestration/ScheduleActions';
import { ScheduleTemplateForm } from '@/components/orchestration/ScheduleTemplateForm';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  executeOrchestrationStream,
  getOrchestrationStatus,
  getOrchestrationEvents,
  listOrchestrations,
  deleteOrchestration,
  type OrchestrationEvent,
  type OrchestrationStatus,
  type OrchestrationListItem,
} from '@/lib/api/orchestration';
import { sourcesApi } from '@/lib/api/sources';
import type { Source } from '@/lib/types';
import { useToast } from '@/hooks/use-toast';

export default function OrchestrationPage() {
  const { toast } = useToast();

  // Form state
  const [goal, setGoal] = useState('');
  const [notebookId, setNotebookId] = useState('');
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [activeTab, setActiveTab] = useState<'new' | 'progress' | 'history' | 'scheduled' | 'schedule-template'>('new');

  // Scheduling state
  const [executionMode, setExecutionMode] = useState<'immediate' | 'schedule'>('immediate');
  const [scheduleType, setScheduleType] = useState<'once' | 'recurring'>('once');
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleTime, setScheduleTime] = useState('');
  const [cronExpression, setCronExpression] = useState('0 9 * * *'); // Default: 9 AM daily

  // Sources state
  const [sources, setSources] = useState<Source[]>([]);
  const [isLoadingSources, setIsLoadingSources] = useState(false);
  const [sourceSearchQuery, setSourceSearchQuery] = useState('');
  const [sourceTypeFilter, setSourceTypeFilter] = useState<string>('all');

  // Current orchestration state
  const [currentOrchestrationId, setCurrentOrchestrationId] = useState<string | null>(null);
  const [status, setStatus] = useState<OrchestrationStatus | null>(null);
  const [events, setEvents] = useState<OrchestrationEvent[]>([]);

  // History state
  const [orchestrations, setOrchestrations] = useState<OrchestrationListItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Scheduled orchestrations state
  const [schedules, setSchedules] = useState<any[]>([]);
  const [isLoadingSchedules, setIsLoadingSchedules] = useState(false);
  const [selectedScheduleId, setSelectedScheduleId] = useState<string | null>(null);
  const [isActionsDialogOpen, setIsActionsDialogOpen] = useState(false);

  // Template scheduling state
  const [isScheduleTemplateDialogOpen, setIsScheduleTemplateDialogOpen] = useState(false);

  // Poll for status updates
  useEffect(() => {
    if (!currentOrchestrationId) return;

    const interval = setInterval(async () => {
      try {
        const [statusData, eventsData] = await Promise.all([
          getOrchestrationStatus(currentOrchestrationId),
          getOrchestrationEvents(currentOrchestrationId),
        ]);

        setStatus(statusData);
        setEvents(eventsData);

        // Stop polling if completed
        if (
          statusData.status === 'completed' ||
          statusData.status === 'failed' ||
          statusData.status === 'cancelled'
        ) {
          setIsExecuting(false);
          loadHistory(); // Refresh history
        }
      } catch (error) {
        console.error('Failed to fetch orchestration status:', error);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(interval);
  }, [currentOrchestrationId]);

  // Load orchestration history
  const loadHistory = async () => {
    setIsLoadingHistory(true);
    try {
      const data = await listOrchestrations(20);
      setOrchestrations(data);
    } catch (error) {
      console.error('Failed to load orchestrations:', error);
      toast({
        title: 'Error',
        description: 'Failed to load orchestration history',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
    loadSources();
    loadSchedules();
  }, []);

  // Load scheduled orchestrations
  const loadSchedules = async () => {
    setIsLoadingSchedules(true);
    try {
      const userId = localStorage.getItem('userId') || 'default-user';
      const response = await fetch('/api/orchestration/schedules?limit=50', {
        headers: { 'X-User-ID': userId },
      });

      if (response.ok) {
        const data = await response.json();
        setSchedules(data);
      }
    } catch (error) {
      console.error('Failed to load schedules:', error);
      toast({
        title: 'Error',
        description: 'Failed to load scheduled orchestrations',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingSchedules(false);
    }
  };

  // Load available sources
  const loadSources = async () => {
    setIsLoadingSources(true);
    try {
      const data = await sourcesApi.list();
      console.log('🔍 Sources loaded:', data.length, 'sources');
      console.log('📄 First 3 sources:', data.slice(0, 3).map(s => ({ id: s.id, title: s.title })));
      setSources(data);
    } catch (error) {
      console.error('Failed to load sources:', error);
      toast({
        title: 'Error',
        description: 'Failed to load sources',
        variant: 'destructive',
      });
    } finally {
      setIsLoadingSources(false);
    }
  };

  // Toggle source selection
  const toggleSource = (sourceId: string) => {
    setSelectedSourceIds(prev => {
      const newSelection = prev.includes(sourceId)
        ? prev.filter(id => id !== sourceId)
        : [...prev, sourceId];
      console.log('✅ Source selection changed:', newSelection);
      return newSelection;
    });
  };

  // Filter sources based on search and type filter
  const filteredSources = sources.filter(source => {
    // Search filter
    const matchesSearch = sourceSearchQuery === '' ||
      source.title.toLowerCase().includes(sourceSearchQuery.toLowerCase()) ||
      source.source_type.toLowerCase().includes(sourceSearchQuery.toLowerCase());

    // Type filter
    const matchesType = sourceTypeFilter === 'all' || source.source_type === sourceTypeFilter;

    return matchesSearch && matchesType;
  });

  // Get unique source types for filter dropdown
  const sourceTypes = Array.from(new Set(sources.map(s => s.source_type)));

  // Select/deselect all visible sources
  const toggleAllVisible = () => {
    const visibleIds = filteredSources.map(s => s.id);
    const allSelected = visibleIds.every(id => selectedSourceIds.includes(id));

    if (allSelected) {
      // Deselect all visible
      setSelectedSourceIds(prev => prev.filter(id => !visibleIds.includes(id)));
    } else {
      // Select all visible
      setSelectedSourceIds(prev => {
        const newIds = [...prev];
        visibleIds.forEach(id => {
          if (!newIds.includes(id)) {
            newIds.push(id);
          }
        });
        return newIds;
      });
    }
  };

  const allVisibleSelected = filteredSources.length > 0 &&
    filteredSources.every(s => selectedSourceIds.includes(s.id));

  // Execute orchestration with streaming or scheduling
  const handleExecute = async () => {
    if (!goal.trim()) {
      toast({
        title: 'Error',
        description: 'Please enter a goal',
        variant: 'destructive',
      });
      return;
    }

    // Validate scheduling inputs
    if (executionMode === 'schedule') {
      if (scheduleType === 'once') {
        if (!scheduleDate || !scheduleTime) {
          toast({
            title: 'Error',
            description: 'Please select both date and time for scheduled execution',
            variant: 'destructive',
          });
          return;
        }

        // Check if scheduled time is in the future
        const scheduledDateTime = new Date(`${scheduleDate}T${scheduleTime}`);
        if (scheduledDateTime <= new Date()) {
          toast({
            title: '⚠️ Invalid Schedule Time',
            description: 'The scheduled date and time must be in the future. Please select a later time.',
            variant: 'destructive',
          });
          setIsExecuting(false);
          return;
        }
      } else if (scheduleType === 'recurring') {
        if (!cronExpression.trim()) {
          toast({
            title: 'Error',
            description: 'Please enter a cron expression',
            variant: 'destructive',
          });
          return;
        }
      }
    }

    setIsExecuting(true);

    // Handle scheduling mode
    if (executionMode === 'schedule') {
      try {
        const payload = {
          goal: goal.trim(),
          notebook_id: notebookId || undefined,
          resources: selectedSourceIds.length > 0 ? { source_ids: selectedSourceIds } : undefined,
          schedule: scheduleType === 'once'
            ? {
                type: 'once',
                datetime: `${scheduleDate}T${scheduleTime}`,
              }
            : {
                type: 'recurring',
                cron: cronExpression,
              },
        };

        console.log('📅 Scheduling orchestration:', payload);
        console.log('📅 User ID:', localStorage.getItem('userId') || 'default-user');

        // Call schedule API endpoint with user ID header
        const userId = localStorage.getItem('userId') || 'default-user';
        const response = await fetch('/api/orchestration/schedule', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': userId,
          },
          body: JSON.stringify(payload),
        });

        console.log('📅 Response status:', response.status, response.statusText);

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
          console.error('Schedule API error:', errorData);
          throw new Error(errorData.detail || 'Failed to schedule orchestration');
        }

        const data = await response.json();

        toast({
          title: '✅ Orchestration Scheduled',
          description: scheduleType === 'once'
            ? `Will execute on ${new Date(`${scheduleDate}T${scheduleTime}`).toLocaleString()}`
            : `Will execute on schedule: ${cronExpression}`,
        });

        // Reset form
        setGoal('');
        setNotebookId('');
        setSelectedSourceIds([]);
        setScheduleDate('');
        setScheduleTime('');
        setExecutionMode('immediate');

        // Switch to Scheduled tab and refresh schedules
        setActiveTab('scheduled');
        await loadSchedules();

        setIsExecuting(false);
        return;
      } catch (error) {
        console.error('Failed to schedule orchestration:', error);
        toast({
          title: '❌ Scheduling Failed',
          description: error instanceof Error ? error.message : 'Failed to schedule orchestration',
          variant: 'destructive',
        });
        setIsExecuting(false);
        return;
      }
    }

      // Handle immediate execution
      try {
        setStatus(null);
        setEvents([]);

        console.log('🚀 Executing orchestration with:');
        console.log('  - Goal:', goal.trim().substring(0, 50) + '...');
        console.log('  - Notebook ID:', notebookId || 'none');
        console.log('  - Selected Source IDs:', selectedSourceIds);
        console.log('  - Resources payload:', selectedSourceIds.length > 0 ? { source_ids: selectedSourceIds } : undefined);

        // Switch to progress tab
        setActiveTab('progress');

        // Use streaming endpoint
        await executeOrchestrationStream(
        {
          goal: goal.trim(),
          notebook_id: notebookId || undefined,
          resources: selectedSourceIds.length > 0 ? { source_ids: selectedSourceIds } : undefined,
        },
        // onEvent callback - update state with each event
        (event: OrchestrationEvent) => {
          console.log('Orchestration event:', event);

          // Store orchestration ID from first event
          if (event.type === 'orchestration.started' && event.data.orchestration_id) {
            setCurrentOrchestrationId(event.data.orchestration_id);
            toast({
              title: 'Orchestration Started',
              description: `Orchestration ${event.data.orchestration_id.slice(0, 8)} is running`,
            });
          }

          // Update events array
          setEvents(prev => [...prev, event]);

          // Update status based on event type
          if (event.data.orchestration_id) {
            const orchestrationId = event.data.orchestration_id;

            // Map event types to status phases
            let phase = 'starting';
            let progress = 0.0;

            switch (event.type) {
              case 'orchestration.started':
                phase = 'analyzing';
                progress = 0.1;
                break;
              case 'analysis.completed':
                phase = 'analyzing_complete';
                progress = 0.2;
                break;
              case 'decision.made':
                phase = 'decision_made';
                progress = 0.3;
                break;
              case 'team.spawning':
                phase = 'team_spawning';
                progress = 0.35;
                break;
              case 'agent.spawned':
                phase = 'team_spawned';
                progress = 0.4;
                break;
              case 'task.assigned':
              case 'task.started':
              case 'task.progress':
                phase = 'executing';
                progress = 0.5 + (Math.random() * 0.3); // Random progress 50-80%
                break;
              case 'task.completed':
                phase = 'executing';
                progress = 0.7;
                break;
              case 'synthesis.started':
                phase = 'synthesizing';
                progress = 0.85;
                break;
              case 'orchestration.completed':
                phase = 'completed';
                progress = 1.0;
                break;
              case 'orchestration.error':
                phase = 'failed';
                progress = 0.0;
                break;
            }

            // Update status with new data
            setStatus(prev => ({
              orchestration_id: orchestrationId,
              status: phase === 'completed' ? 'completed' : phase === 'failed' ? 'failed' : 'running',
              current_phase: phase,
              progress: progress,
              team_id: event.data.team_id || prev?.team_id,
              orchestration_mode: event.data.orchestration_mode || prev?.orchestration_mode,
              started_at: prev?.started_at || new Date().toISOString(),
              updated_at: new Date().toISOString(),
            }));
          }
        },
        // onError callback
        (error: Error) => {
          console.error('Orchestration stream error:', error);
          toast({
            title: 'Error',
            description: `Orchestration failed: ${error.message}`,
            variant: 'destructive',
          });
          setIsExecuting(false);
        },
        // onComplete callback
        () => {
          console.log('Orchestration stream completed');
          setIsExecuting(false);
          loadHistory(); // Refresh history
        }
      );
    } catch (error) {
      console.error('Failed to execute orchestration:', error);
      toast({
        title: 'Error',
        description: 'Failed to start orchestration',
        variant: 'destructive',
      });
      setIsExecuting(false);
    }
  };

  // Delete orchestration
  const handleDelete = async (orchestrationId: string) => {
    try {
      await deleteOrchestration(orchestrationId);
      toast({
        title: 'Success',
        description: 'Orchestration deleted',
      });
      loadHistory();
    } catch (error) {
      console.error('Failed to delete orchestration:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete orchestration',
        variant: 'destructive',
      });
    }
  };

  // Load orchestration from history
  const handleLoadOrchestration = async (orchestrationId: string) => {
    setCurrentOrchestrationId(orchestrationId);
    setActiveTab('progress'); // Switch to progress tab to view details
    try {
      const [statusData, eventsData] = await Promise.all([
        getOrchestrationStatus(orchestrationId),
        getOrchestrationEvents(orchestrationId),
      ]);
      setStatus(statusData);
      setEvents(eventsData);
    } catch (error) {
      console.error('Failed to load orchestration:', error);
      toast({
        title: 'Error',
        description: 'Failed to load orchestration',
        variant: 'destructive',
      });
    }
  };

  // Pause schedule
  const handlePauseSchedule = async (scheduleId: string) => {
    try {
      const userId = localStorage.getItem('userId') || 'default-user';
      const response = await fetch(`/api/orchestration/schedules/${scheduleId}/pause`, {
        method: 'POST',
        headers: { 'X-User-ID': userId },
      });

      if (response.ok) {
        toast({ title: 'Success', description: 'Schedule paused' });
        loadSchedules();
      } else {
        throw new Error('Failed to pause schedule');
      }
    } catch (error) {
      console.error('Failed to pause schedule:', error);
      toast({
        title: 'Error',
        description: 'Failed to pause schedule',
        variant: 'destructive',
      });
    }
  };

  // Resume schedule
  const handleResumeSchedule = async (scheduleId: string) => {
    try {
      const userId = localStorage.getItem('userId') || 'default-user';
      const response = await fetch(`/api/orchestration/schedules/${scheduleId}/resume`, {
        method: 'POST',
        headers: { 'X-User-ID': userId },
      });

      if (response.ok) {
        toast({ title: 'Success', description: 'Schedule resumed' });
        loadSchedules();
      } else {
        throw new Error('Failed to resume schedule');
      }
    } catch (error) {
      console.error('Failed to resume schedule:', error);
      toast({
        title: 'Error',
        description: 'Failed to resume schedule',
        variant: 'destructive',
      });
    }
  };

  // Delete schedule
  const handleDeleteSchedule = async (scheduleId: string) => {
    try {
      const userId = localStorage.getItem('userId') || 'default-user';
      const response = await fetch(`/api/orchestration/schedules/${scheduleId}`, {
        method: 'DELETE',
        headers: { 'X-User-ID': userId },
      });

      if (response.ok) {
        toast({ title: 'Success', description: 'Schedule deleted' });
        loadSchedules();
      } else {
        throw new Error('Failed to delete schedule');
      }
    } catch (error) {
      console.error('Failed to delete schedule:', error);
      toast({
        title: 'Error',
        description: 'Failed to delete schedule',
        variant: 'destructive',
      });
    }
  };

  return (
    <div className="p-6 space-y-6 bg-background min-h-screen">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-orange-100 via-amber-100 to-yellow-100 dark:from-orange-900/30 dark:via-amber-900/30 dark:to-yellow-900/30 p-8 shadow-lg border border-orange-200 dark:border-orange-800 animate-fade-in-up">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative z-10">
          <h1 className="text-4xl font-bold mb-2 flex items-center gap-3 text-gray-800 dark:text-gray-100">
            <Sparkles className="h-10 w-10 text-orange-600 dark:text-orange-400" />
            Autonomous Orchestration
          </h1>
          <p className="text-gray-700 dark:text-gray-300 text-lg">
            Trigger complex multi-agent workflows for sophisticated tasks
          </p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'new' | 'progress' | 'history' | 'scheduled' | 'schedule-template')} className="space-y-6">
        <TabsList className="grid w-full grid-cols-5 lg:w-[900px] h-12">
          <TabsTrigger value="new" className="text-sm font-semibold">New Orchestration</TabsTrigger>
          <TabsTrigger value="progress" className="text-sm font-semibold">Progress</TabsTrigger>
          <TabsTrigger value="schedule-template" className="text-sm font-semibold">Schedule Template</TabsTrigger>
          <TabsTrigger value="scheduled" className="text-sm font-semibold">Scheduled</TabsTrigger>
          <TabsTrigger value="history" className="text-sm font-semibold">History</TabsTrigger>
        </TabsList>

        {/* New Orchestration Tab */}
        <TabsContent value="new" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Create Orchestration</CardTitle>
              <CardDescription>
                Describe your goal and let the autonomous orchestrator decide the best execution
                strategy
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* 70-30 Grid Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-[70%_30%] gap-6">
                {/* Left Column - Goal (70%) */}
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="goal">Goal *</Label>
                    <Textarea
                      id="goal"
                      placeholder="Example: Query HANA for Q4 sales data, research competitor pricing, compare results, and create a comprehensive analysis report"
                      value={goal}
                      onChange={(e) => setGoal(e.target.value)}
                      className="min-h-[400px] resize-none"
                      disabled={isExecuting}
                    />
                    <p className="text-xs text-muted-foreground">
                      Describe what you want to achieve. The orchestrator will analyze complexity and
                      spawn appropriate agents.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="notebook">Notebook ID (Optional)</Label>
                    <Input
                      id="notebook"
                      placeholder="Leave empty for general orchestration"
                      value={notebookId}
                      onChange={(e) => setNotebookId(e.target.value)}
                      disabled={isExecuting}
                    />
                  </div>
                </div>

                {/* Right Column - Execution Timing + Data Sources (30%) */}
                <div className="space-y-4">
                  {/* Execution Timing Section */}
                  <div className="space-y-3 pb-4 border-b">
                    <Label className="text-sm font-semibold">Execution Timing</Label>
                    <RadioGroup
                      value={executionMode}
                      onValueChange={(v) => setExecutionMode(v as 'immediate' | 'schedule')}
                      disabled={isExecuting}
                      className="space-y-2"
                    >
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="immediate" id="immediate" />
                        <Label htmlFor="immediate" className="font-normal cursor-pointer text-sm">
                          Execute Immediately
                        </Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="schedule" id="schedule" />
                        <Label htmlFor="schedule" className="font-normal cursor-pointer text-sm">
                          Schedule for Later
                        </Label>
                      </div>
                    </RadioGroup>

                    {executionMode === 'schedule' && (
                      <div className="space-y-3 pl-4 border-l-2 border-primary/20 mt-3">
                        <div className="space-y-2">
                          <Label className="text-xs">Schedule Type</Label>
                          <RadioGroup
                            value={scheduleType}
                            onValueChange={(v) => setScheduleType(v as 'once' | 'recurring')}
                            disabled={isExecuting}
                            className="space-y-1.5"
                          >
                            <div className="flex items-center space-x-2">
                              <RadioGroupItem value="once" id="once" />
                              <Label htmlFor="once" className="font-normal cursor-pointer text-xs flex items-center gap-1.5">
                                <Calendar className="h-3 w-3" />
                                One-Time
                              </Label>
                            </div>
                            <div className="flex items-center space-x-2">
                              <RadioGroupItem value="recurring" id="recurring" />
                              <Label htmlFor="recurring" className="font-normal cursor-pointer text-xs flex items-center gap-1.5">
                                <Clock className="h-3 w-3" />
                                Recurring
                              </Label>
                            </div>
                          </RadioGroup>
                        </div>

                        {scheduleType === 'once' && (
                          <div className="space-y-2">
                            <div className="space-y-1.5">
                              <Label htmlFor="scheduleDate" className="text-xs">Date</Label>
                              <Input
                                id="scheduleDate"
                                type="date"
                                value={scheduleDate}
                                onChange={(e) => setScheduleDate(e.target.value)}
                                disabled={isExecuting}
                                min={new Date().toISOString().split('T')[0]}
                                className="text-xs h-8"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <Label htmlFor="scheduleTime" className="text-xs">Time</Label>
                              <Input
                                id="scheduleTime"
                                type="time"
                                value={scheduleTime}
                                onChange={(e) => setScheduleTime(e.target.value)}
                                disabled={isExecuting}
                                className="text-xs h-8"
                              />
                            </div>
                          </div>
                        )}

                        {scheduleType === 'recurring' && (
                          <div className="space-y-2">
                            <div className="space-y-1.5">
                              <Label htmlFor="cronExpression" className="text-xs">Cron Expression</Label>
                              <Input
                                id="cronExpression"
                                placeholder="0 9 * * *"
                                value={cronExpression}
                                onChange={(e) => setCronExpression(e.target.value)}
                                disabled={isExecuting}
                                className="text-xs h-8"
                              />
                              <p className="text-[10px] text-muted-foreground">
                                minute hour day month day-of-week
                              </p>
                            </div>

                            <div className="grid grid-cols-1 gap-1.5">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCronExpression('0 9 * * *')}
                                disabled={isExecuting}
                                className="h-7 text-[10px] justify-start"
                              >
                                Daily 9 AM
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCronExpression('0 9 * * 1')}
                                disabled={isExecuting}
                                className="h-7 text-[10px] justify-start"
                              >
                                Weekly Mon 9 AM
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCronExpression('0 9 1 * *')}
                                disabled={isExecuting}
                                className="h-7 text-[10px] justify-start"
                              >
                                Monthly 1st 9 AM
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCronExpression('0 */6 * * *')}
                                disabled={isExecuting}
                                className="h-7 text-[10px] justify-start"
                              >
                                Every 6 hours
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Execute/Schedule Button */}
                    <Button
                      onClick={handleExecute}
                      disabled={isExecuting}
                      className="w-full h-9 mt-3 bg-gradient-to-r from-gray-500 to-slate-500 hover:from-gray-600 hover:to-slate-600 text-white font-semibold shadow-md hover:shadow-lg transition-all duration-200"
                    >
                      {isExecuting ? (
                        <>
                          <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                          {executionMode === 'schedule' ? 'Scheduling...' : 'Executing...'}
                        </>
                      ) : (
                        <>
                          {executionMode === 'schedule' ? (
                            <>
                              <Calendar className="mr-2 h-3.5 w-3.5" />
                              Schedule
                            </>
                          ) : (
                            <>
                              <Play className="mr-2 h-3.5 w-3.5" />
                              Execute
                            </>
                          )}
                        </>
                      )}
                    </Button>
                  </div>

                  {/* Data Sources Section */}
                  <div className="space-y-3">
                    <Label className="text-sm font-semibold">Data Sources (Optional)</Label>
                    <p className="text-xs text-muted-foreground">
                      Select data sources for agents to access
                    </p>

                    {isLoadingSources ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                      </div>
                    ) : sources.length === 0 ? (
                      <Card className="bg-muted/50">
                        <CardContent className="py-8 text-center text-sm text-muted-foreground">
                          No sources available. Create sources from the Sources page.
                        </CardContent>
                      </Card>
                    ) : (
                      <div className="space-y-3">
                        {/* Search and Filter Bar */}
                        <div className="space-y-2">
                          <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <Input
                              placeholder="Search sources..."
                              value={sourceSearchQuery}
                              onChange={(e) => setSourceSearchQuery(e.target.value)}
                              className="pl-9 h-8 text-xs"
                              disabled={isExecuting}
                            />
                          </div>
                          <Select
                            value={sourceTypeFilter}
                            onValueChange={setSourceTypeFilter}
                            disabled={isExecuting}
                          >
                            <SelectTrigger className="w-full h-8 text-xs">
                              <Filter className="h-3.5 w-3.5 mr-2" />
                              <SelectValue placeholder="Filter by type" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">All Types</SelectItem>
                              {sourceTypes.map(type => (
                                <SelectItem key={type} value={type}>
                                  {type.replace('_', ' ')}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>

                        {/* Select All / Clear All */}
                        <div className="flex items-center justify-between px-1">
                          <p className="text-xs text-muted-foreground">
                            {filteredSources.length} found
                          </p>
                          {filteredSources.length > 0 && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={toggleAllVisible}
                              disabled={isExecuting}
                              className="h-auto py-1 text-xs"
                            >
                              {allVisibleSelected ? 'Deselect' : 'Select All'}
                            </Button>
                          )}
                        </div>

                        {/* Sources List */}
                        {filteredSources.length === 0 ? (
                          <Card className="bg-muted/50">
                            <CardContent className="py-6 text-center text-xs text-muted-foreground">
                              No sources match your search
                            </CardContent>
                          </Card>
                        ) : (
                          <div className="border rounded-lg h-[200px] overflow-y-auto">
                            <div className="divide-y">
                              {filteredSources.map((source) => (
                                <div
                                  key={source.id}
                                  className="flex items-start gap-2 p-2 hover:bg-muted/50 transition-colors cursor-pointer"
                                  onClick={() => toggleSource(source.id)}
                                >
                                  <Checkbox
                                    checked={selectedSourceIds.includes(source.id)}
                                    onCheckedChange={() => toggleSource(source.id)}
                                    disabled={isExecuting}
                                    className="mt-0.5"
                                  />
                                  <div className="flex items-start gap-2 flex-1 min-w-0">
                                    {source.source_type === 'hana_table' ? (
                                      <Database className="h-3.5 w-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
                                    ) : source.source_type === 'api' ? (
                                      <FileText className="h-3.5 w-3.5 text-green-500 flex-shrink-0 mt-0.5" />
                                    ) : source.source_type === 'file' ? (
                                      <FileText className="h-3.5 w-3.5 text-purple-500 flex-shrink-0 mt-0.5" />
                                    ) : (
                                      <FileText className="h-3.5 w-3.5 text-gray-500 flex-shrink-0 mt-0.5" />
                                    )}
                                    <div className="flex-1 min-w-0">
                                      <p className="text-xs font-medium truncate leading-tight">{source.title}</p>
                                      <p className="text-[10px] text-muted-foreground truncate">
                                        {source.source_type.replace('_', ' ')}
                                      </p>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Selection Summary */}
                        {selectedSourceIds.length > 0 && (
                          <div className="flex items-center justify-between px-1 pt-1">
                            <p className="text-xs font-medium text-primary">
                              {selectedSourceIds.length} selected
                            </p>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedSourceIds([])}
                              disabled={isExecuting}
                              className="h-auto py-1 text-xs"
                            >
                              Clear
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Progress Tab */}
        <TabsContent value="progress" className="space-y-6">
          {!status && !isExecuting && (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No active orchestration. Start one from the "New Orchestration" tab.
              </CardContent>
            </Card>
          )}

          {status && (
            <>
              <OrchestrationProgress status={status} events={events} />

              {/* Collaboration Graph - Mock data for now */}
              {status.team_id && (
                <Card>
                  <CardHeader>
                    <CardTitle>Agent Collaboration</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <AgentCollaborationGraph
                      agents={[
                        { id: 'agent-1', name: 'Planner', role: 'planner', status: 'completed' },
                        {
                          id: 'agent-2',
                          name: 'Researcher',
                          role: 'researcher',
                          status: 'working',
                        },
                        { id: 'agent-3', name: 'Analyst', role: 'analyst', status: 'idle' },
                      ]}
                      tasks={[
                        {
                          id: 'task-1',
                          description: 'Decompose goal',
                          agent_id: 'agent-1',
                          status: 'completed',
                          dependencies: [],
                        },
                        {
                          id: 'task-2',
                          description: 'Research competitors',
                          agent_id: 'agent-2',
                          status: 'in_progress',
                          dependencies: ['task-1'],
                        },
                        {
                          id: 'task-3',
                          description: 'Analyze data',
                          agent_id: 'agent-3',
                          status: 'assigned',
                          dependencies: ['task-1'],
                        },
                      ]}
                      handovers={[{ from_agent_id: 'agent-1', to_agent_id: 'agent-2', task_id: 'task-2' }]}
                    />
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* Schedule Template Tab */}
        <TabsContent value="schedule-template" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Schedule Template Execution</CardTitle>
              <CardDescription>
                Create recurring or one-time schedules from workspace templates with parameter configuration
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <div className="flex gap-3">
                  <Calendar className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-900 dark:text-blue-100">
                    <p className="font-medium mb-2">Template-Based Scheduling</p>
                    <ul className="list-disc list-inside space-y-1 text-blue-800 dark:text-blue-200">
                      <li>Select a pre-configured workspace template</li>
                      <li>Set parameter values for this execution</li>
                      <li>Choose one-time or recurring schedule (cron)</li>
                      <li>Template instantiates automatically on schedule</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button
                onClick={() => setIsScheduleTemplateDialogOpen(true)}
                size="lg"
                className="w-full"
              >
                <Calendar className="h-5 w-5 mr-2" />
                Create Template Schedule
              </Button>

              <div className="pt-4 border-t">
                <h3 className="text-sm font-semibold mb-3">Template-Based Schedules</h3>
                {isLoadingSchedules ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : schedules.filter(s => s.template_id).length === 0 ? (
                  <div className="text-center py-8 text-sm text-muted-foreground">
                    No template-based schedules yet
                  </div>
                ) : (
                  <div className="space-y-3">
                    {schedules.filter(s => s.template_id).map((schedule) => (
                      <div
                        key={schedule.id}
                        className="border rounded-lg p-4 bg-card hover:bg-muted/50 transition-colors"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <Badge variant={schedule.status === 'active' ? 'default' : 'secondary'}>
                              {schedule.status}
                            </Badge>
                            <Badge variant="outline" className="capitalize">
                              {schedule.schedule_type}
                            </Badge>
                            <Badge variant="outline" className="bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300">
                              Template
                            </Badge>
                          </div>
                        </div>

                        <p className="text-sm font-medium mb-1">{schedule.name || 'Unnamed Schedule'}</p>

                        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                          {schedule.schedule_type === 'recurring' && schedule.schedule_config?.cron && (
                            <div>
                              <span className="font-medium">Cron:</span> {schedule.schedule_config.cron}
                            </div>
                          )}
                          {schedule.next_run && (
                            <div>
                              <span className="font-medium">Next:</span>{' '}
                              {new Date(schedule.next_run).toLocaleString()}
                            </div>
                          )}
                          <div>
                            <span className="font-medium">Executed:</span> {schedule.execution_count || 0} times
                          </div>
                        </div>

                        <div className="flex items-center gap-2 mt-3">
                          {schedule.status === 'active' && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handlePauseSchedule(schedule.id)}
                            >
                              Pause
                            </Button>
                          )}
                          {schedule.status === 'paused' && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleResumeSchedule(schedule.id)}
                            >
                              Resume
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteSchedule(schedule.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Scheduled Tab */}
        <TabsContent value="scheduled" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Scheduled Orchestrations</h2>
            <Button variant="outline" size="sm" onClick={loadSchedules} disabled={isLoadingSchedules}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>

          <div className="space-y-4">
            {isLoadingSchedules ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
                </CardContent>
              </Card>
            ) : schedules.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  No scheduled orchestrations yet
                </CardContent>
              </Card>
            ) : (
              schedules.map((schedule) => (
                <Card key={schedule.id}>
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 space-y-3">
                        {/* Header */}
                        <div className="flex items-center gap-2">
                          <code className="text-xs bg-muted px-2 py-1 rounded">
                            {schedule.id.slice(0, 8)}
                          </code>
                          <Badge
                            variant={
                              schedule.status === 'active' ? 'default' :
                              schedule.status === 'paused' ? 'secondary' :
                              schedule.status === 'completed' ? 'outline' :
                              'destructive'
                            }
                          >
                            {schedule.status}
                          </Badge>
                          <Badge variant="outline" className="capitalize">
                            {schedule.schedule_type}
                          </Badge>
                        </div>

                        {/* Goal */}
                        <p className="text-sm font-medium">{schedule.goal}</p>

                        {/* Schedule Info */}
                        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                          {schedule.schedule_type === 'recurring' && schedule.schedule_config?.cron && (
                            <div>
                              <span className="font-medium">Cron:</span> {schedule.schedule_config.cron}
                            </div>
                          )}
                          {schedule.next_run && (
                            <div>
                              <span className="font-medium">Next run:</span>{' '}
                              {new Date(schedule.next_run).toLocaleString()}
                            </div>
                          )}
                          {schedule.last_run && (
                            <div>
                              <span className="font-medium">Last run:</span>{' '}
                              {new Date(schedule.last_run).toLocaleString()}
                            </div>
                          )}
                          <div>
                            <span className="font-medium">Executed:</span> {schedule.execution_count || 0} times
                          </div>
                        </div>

                        {/* Timestamps */}
                        <p className="text-xs text-muted-foreground">
                          Created: {new Date(schedule.created_at).toLocaleString()}
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedScheduleId(schedule.id);
                            setIsActionsDialogOpen(true);
                          }}
                          title="Configure Actions"
                        >
                          <Settings className="h-4 w-4" />
                        </Button>
                        {schedule.status === 'active' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handlePauseSchedule(schedule.id)}
                          >
                            Pause
                          </Button>
                        )}
                        {schedule.status === 'paused' && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleResumeSchedule(schedule.id)}
                          >
                            Resume
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteSchedule(schedule.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold">Orchestration History</h2>
            <Button variant="outline" size="sm" onClick={loadHistory} disabled={isLoadingHistory}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>

          <div className="space-y-4">
            {orchestrations.length === 0 && (
              <Card>
                <CardContent className="py-12 text-center text-muted-foreground">
                  No orchestrations yet
                </CardContent>
              </Card>
            )}

            {orchestrations.map((orchestration) => (
              <Card
                key={orchestration.orchestration_id}
                className="cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => handleLoadOrchestration(orchestration.orchestration_id)}
              >
                <CardContent className="py-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 space-y-2">
                      <div className="flex items-center gap-2">
                        <code className="text-xs bg-muted px-2 py-1 rounded">
                          {orchestration.orchestration_id.slice(0, 8)}
                        </code>
                        <Badge variant="outline">{orchestration.status}</Badge>
                        {orchestration.orchestration_mode && (
                          <Badge variant="secondary" className="capitalize">
                            {orchestration.orchestration_mode}
                          </Badge>
                        )}
                        {/* Show badge for scheduled executions */}
                        {(orchestration as any).schedule_id ? (
                          <Badge variant="default" className="bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 border-blue-500/30">
                            <Calendar className="h-3 w-3 mr-1" />
                            Scheduled
                          </Badge>
                        ) : (
                          <Badge variant="default" className="bg-green-500/10 text-green-600 hover:bg-green-500/20 border-green-500/30">
                            <Play className="h-3 w-3 mr-1" />
                            Immediate
                          </Badge>
                        )}
                      </div>

                      <p className="text-sm">{orchestration.goal}</p>

                      <p className="text-xs text-muted-foreground">
                        {new Date(orchestration.created_at).toLocaleString()}
                      </p>
                    </div>

                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(orchestration.orchestration_id);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Actions Configuration Dialog */}
      <Dialog open={isActionsDialogOpen} onOpenChange={setIsActionsDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Configure Schedule Actions</DialogTitle>
            <DialogDescription>
              Manage actions that execute when this schedule runs
            </DialogDescription>
          </DialogHeader>
          {selectedScheduleId && (
            <ScheduleActions scheduleId={selectedScheduleId} />
          )}
        </DialogContent>
      </Dialog>

      {/* Schedule Template Dialog */}
      <ScheduleTemplateForm
        open={isScheduleTemplateDialogOpen}
        onOpenChange={(open) => {
          setIsScheduleTemplateDialogOpen(open);
          if (!open) {
            // Refresh schedules when dialog closes
            loadSchedules();
          }
        }}
      />
    </div>
  );
}
