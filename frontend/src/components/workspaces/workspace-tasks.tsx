/**
 * Workspace Tasks Component
 *
 * Displays and manages tasks for AI-guided workspaces
 */

'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChartRenderer } from '@/components/notes/chart-renderer';
import { TaskCreationDialog } from '@/components/workspaces/task-creation-dialog';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  CheckCircle2,
  Circle,
  Clock,
  PlayCircle,
  XCircle,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  FileText,
  Copy,
  Check,
  Loader2,
  Plus,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  listWorkspaceTasks,
  getWorkspaceProgress,
  startTask,
  completeTask,
  blockTask,
  startTaskManually,
  cleanupStuckTasks,
  finalizeWorkspace,
  executeWorkspacePlan,
  type WorkspaceTask,
  type WorkspaceProgress,
} from '@/lib/api/workspace-tasks';

interface WorkspaceTasksProps {
  workspaceId: string;
  refreshKey?: number;
}

export function WorkspaceTasks({ workspaceId, refreshKey = 0 }: WorkspaceTasksProps) {
  const queryClient = useQueryClient();
  const [expandedPhases, setExpandedPhases] = useState<Set<string>>(new Set());
  const [selectedTask, setSelectedTask] = useState<WorkspaceTask | null>(null);
  const [taskNote, setTaskNote] = useState<any | null>(null);
  const [isLoadingNote, setIsLoadingNote] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showCreateTaskDialog, setShowCreateTaskDialog] = useState(false);

  // Fetch tasks with auto-refresh
  const { data: tasks = [], isLoading: tasksLoading } = useQuery({
    queryKey: ['workspace-tasks', workspaceId, refreshKey],
    queryFn: () => listWorkspaceTasks(workspaceId),
    refetchInterval: 10000, // Refresh every 10 seconds
    refetchIntervalInBackground: true,
  });

  // Fetch progress with auto-refresh
  const { data: progress, isLoading: progressLoading } = useQuery({
    queryKey: ['workspace-progress', workspaceId, refreshKey],
    queryFn: () => getWorkspaceProgress(workspaceId),
    refetchInterval: 10000, // Refresh every 10 seconds
    refetchIntervalInBackground: true,
  });

  // Mutation to update task status
  const updateTaskMutation = useMutation({
    mutationFn: async ({
      taskId,
      action,
    }: {
      taskId: string;
      action: 'start' | 'complete' | 'block';
    }) => {
      if (action === 'start') return startTask(workspaceId, taskId);
      if (action === 'complete') return completeTask(workspaceId, taskId);
      if (action === 'block') return blockTask(workspaceId, taskId);
      throw new Error('Invalid action');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-tasks', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['workspace-progress', workspaceId] });
      toast.success('Task updated successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update task');
    },
  });

  // Mutation to manually start/retry a task
  const startTaskMutation = useMutation({
    mutationFn: (taskId: string) => startTaskManually(workspaceId, taskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-tasks', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['workspace-progress', workspaceId] });
      toast.success('Task queued for execution');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start task');
    },
  });

  // Mutation to cleanup stuck tasks
  const cleanupStuckMutation = useMutation({
    mutationFn: () => cleanupStuckTasks(workspaceId, 30),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['workspace-tasks', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['workspace-progress', workspaceId] });
      toast.success(data.message);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cleanup stuck tasks');
    },
  });

  // Mutation to finalize workspace and generate summary
  const finalizeMutation = useMutation({
    mutationFn: async () => {
      // Show progress toast
      toast.info('🤖 Generating comprehensive AI summary... This may take 30-60 seconds.', {
        duration: 5000,
      });
      return finalizeWorkspace(workspaceId);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['workspace-tasks', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['workspace-progress', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['notes', workspaceId] }); // Refresh notes to show summary
      toast.success('✅ Workspace finalized! Summary generated successfully.', {
        duration: 4000,
      });
    },
    onError: (error: any) => {
      console.error('Finalize error:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to finalize workspace';
      toast.error(`❌ ${errorMsg}. Please try again.`, {
        duration: 5000,
      });
    },
    onSettled: () => {
      // This runs whether success or error, ensuring button returns to normal
      console.log('Finalize mutation settled - button should be re-enabled');
    },
  });

  // Mutation to execute workspace plan (manually trigger task execution)
  const executePlanMutation = useMutation({
    mutationFn: async () => {
      toast.info('🚀 Starting task execution... Tasks will run in the background.', {
        duration: 5000,
      });
      return executeWorkspacePlan(workspaceId);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['workspace-tasks', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['workspace-progress', workspaceId] });
      toast.success(`✅ Execution started! ${data.task_count} tasks will be processed.`, {
        duration: 4000,
      });
    },
    onError: (error: any) => {
      console.error('Execute plan error:', error);
      const errorMsg = error.response?.data?.detail || error.message || 'Failed to execute plan';
      toast.error(`❌ ${errorMsg}`, {
        duration: 5000,
      });
    },
  });

  // Toggle phase expansion
  const togglePhase = (phaseName: string) => {
    setExpandedPhases((prev) => {
      const next = new Set(prev);
      if (next.has(phaseName)) {
        next.delete(phaseName);
      } else {
        next.add(phaseName);
      }
      return next;
    });
  };

  // Handle task click to show note
  const handleTaskClick = async (task: WorkspaceTask) => {
    if (task.status !== 'completed' && task.status !== 'failed') return; // Only show notes for completed or failed tasks

    setSelectedTask(task);
    setIsLoadingNote(true);

    try {
      // Find the note that matches this task
      const response = await fetch(`/api/notes?notebook_id=${workspaceId}`);
      if (response.ok) {
        const notes = await response.json();
        // Match note by title containing task name
        const note = notes.find((n: any) =>
          n.title.includes(task.name) || n.title.includes(task.name.substring(0, 30))
        );
        setTaskNote(note);
      }
    } catch (error) {
      console.error('Failed to load task note:', error);
      toast.error('Failed to load task note');
    } finally {
      setIsLoadingNote(false);
    }
  };

  const closeNoteDialog = () => {
    setSelectedTask(null);
    setTaskNote(null);
    setCopied(false);
  };

  const handleCopyNote = async () => {
    if (!taskNote) return;

    try {
      // Create a clean text version by stripping HTML tags
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = taskNote.content_html || taskNote.content;
      const textContent = tempDiv.textContent || tempDiv.innerText || '';

      // Add title at the top
      const copyText = `${taskNote.title}\n\n${textContent}`;

      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      toast.success("Note copied to clipboard");

      // Reset icon after 2 seconds
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
      toast.error("Failed to copy note");
    }
  };

  // Group tasks by phase
  const tasksByPhase = tasks.reduce((acc, task) => {
    if (!acc[task.phase_name]) {
      acc[task.phase_name] = [];
    }
    acc[task.phase_name].push(task);
    return acc;
  }, {} as Record<string, WorkspaceTask[]>);

  // Get status icon and color
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return (
          <Badge variant="default" className="bg-green-500">
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Completed
          </Badge>
        );
      case 'in_progress':
        return (
          <Badge variant="default" className="bg-blue-500">
            <Clock className="w-3 h-3 mr-1" />
            In Progress
          </Badge>
        );
      case 'blocked':
        return (
          <Badge variant="destructive">
            <XCircle className="w-3 h-3 mr-1" />
            Blocked
          </Badge>
        );
      case 'failed':
        return (
          <Badge variant="destructive" className="bg-red-600">
            <XCircle className="w-3 h-3 mr-1" />
            Failed
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary">
            <Circle className="w-3 h-3 mr-1" />
            Pending
          </Badge>
        );
    }
  };

  // Check if task can be started (dependencies met)
  const canStartTask = (task: WorkspaceTask) => {
    if (task.status !== 'pending') return false;
    if (task.dependencies.length === 0) return true;

    // Check if all dependencies are completed
    return task.dependencies.every((depId) => {
      const depTask = tasks.find((t) => t.id === depId);
      return depTask?.status === 'completed';
    });
  };

  if (tasksLoading || progressLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Tasks</CardTitle>
          <CardDescription>Loading workspace tasks...</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  // Extract unique phase names for task creation
  const existingPhases = Array.from(new Set(tasks.map((t) => t.phase_name)));

  if (tasks.length === 0) {
    return (
      <>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Tasks</CardTitle>
                <CardDescription>
                  This workspace has no tasks. Create tasks to organize and track your work.
                </CardDescription>
              </div>
              <Button size="sm" onClick={() => setShowCreateTaskDialog(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Task
              </Button>
            </div>
          </CardHeader>
        </Card>
        <TaskCreationDialog
          open={showCreateTaskDialog}
          onOpenChange={setShowCreateTaskDialog}
          workspaceId={workspaceId}
          existingPhases={existingPhases}
        />
      </>
    );
  }

  return (
    <div className="space-y-6">
      {/* Progress Overview */}
      {progress && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Workspace Progress</CardTitle>
                <CardDescription>
                  {progress.completed_tasks} of {progress.total_tasks} tasks completed
                  {progress.current_phase && ` • Currently in: ${progress.current_phase}`}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                {/* Execute Plan button - only show if all tasks are pending */}
                {progress.pending_tasks === progress.total_tasks && progress.total_tasks > 0 && (
                  <Button
                    size="sm"
                    onClick={() => executePlanMutation.mutate()}
                    disabled={executePlanMutation.isPending}
                    title="Execute all tasks using autonomous orchestrator"
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {executePlanMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Starting...
                      </>
                    ) : (
                      <>
                        <PlayCircle className="w-4 h-4 mr-2" />
                        Execute Tasks
                      </>
                    )}
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowCreateTaskDialog(true)}
                  title="Create a new task"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Create Task
                </Button>
                {progress.in_progress_tasks > 0 && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => cleanupStuckMutation.mutate()}
                    disabled={cleanupStuckMutation.isPending}
                    title="Reset tasks stuck in 'In Progress' for more than 30 minutes"
                  >
                    <AlertCircle className="w-4 h-4 mr-2" />
                    Cleanup Stuck
                  </Button>
                )}
                {progress.completed_tasks === progress.total_tasks && progress.total_tasks > 0 && (
                  <Button
                    size="sm"
                    onClick={() => {
                      console.log('Generate Summary clicked');
                      finalizeMutation.mutate();
                    }}
                    disabled={finalizeMutation.isPending}
                    title="Generate AI-powered comprehensive summary (takes 30-60 seconds)"
                    className="bg-green-600 hover:bg-green-700"
                  >
                    {finalizeMutation.isPending ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Generating Summary...
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4 mr-2" />
                        Generate Summary
                      </>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span>Overall Completion</span>
                <span className="font-semibold">{progress.overall_completion_percentage}%</span>
              </div>
              <Progress value={progress.overall_completion_percentage} className="h-3" />
            </div>

            {progress.estimated_remaining_duration > 0 && (
              <div className="text-sm text-muted-foreground">
                Estimated time remaining: ~{Math.ceil(progress.estimated_remaining_duration / 60)}{' '}
                hours
              </div>
            )}

            {/* Phase Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
              <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {progress.completed_tasks}
                </div>
                <div className="text-xs text-muted-foreground">Completed</div>
              </div>
              <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {progress.in_progress_tasks}
                </div>
                <div className="text-xs text-muted-foreground">In Progress</div>
              </div>
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <div className="text-2xl font-bold">{progress.pending_tasks}</div>
                <div className="text-xs text-muted-foreground">Pending</div>
              </div>
              <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                <div className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {progress.blocked_tasks}
                </div>
                <div className="text-xs text-muted-foreground">Blocked</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tasks by Phase */}
      <div className="space-y-4">
        {Object.entries(tasksByPhase).map(([phaseName, phaseTasks]) => {
          const isExpanded = expandedPhases.has(phaseName);
          const phaseProgress = progress?.phases.find((p) => p.phase_name === phaseName);
          const completionPct = phaseProgress?.completion_percentage || 0;

          return (
            <Card key={phaseName}>
              <CardHeader
                className="cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => togglePhase(phaseName)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5" />
                    ) : (
                      <ChevronRight className="w-5 h-5" />
                    )}
                    <div>
                      <CardTitle className="text-lg">{phaseName}</CardTitle>
                      {phaseProgress && (
                        <CardDescription className="mt-1">
                          {phaseProgress.completed_tasks} of {phaseProgress.total_tasks} tasks
                          completed
                        </CardDescription>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold">{Math.round(completionPct)}%</div>
                    {phaseProgress && phaseProgress.estimated_duration > 0 && (
                      <div className="text-xs text-muted-foreground">
                        ~{Math.ceil(phaseProgress.estimated_duration / 60)}h
                      </div>
                    )}
                  </div>
                </div>
              </CardHeader>

              {isExpanded && (
                <CardContent className="space-y-3">
                  {phaseTasks.map((task) => (
                    <div
                      key={task.id}
                      className={`border rounded-lg p-4 transition-colors ${
                        task.status === 'completed' || task.status === 'failed'
                          ? 'hover:bg-muted/50 cursor-pointer'
                          : 'hover:bg-muted/30'
                      }`}
                      onClick={() => (task.status === 'completed' || task.status === 'failed') && handleTaskClick(task)}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center gap-3">
                            {task.status === 'completed' && (
                              <FileText className="w-4 h-4 text-primary" />
                            )}
                            <h4 className="font-semibold">{task.name}</h4>
                            {getStatusBadge(task.status)}
                          </div>

                          {task.description && (
                            <p className="text-sm text-muted-foreground">{task.description}</p>
                          )}

                          {task.status === 'completed' && (
                            <p className="text-xs text-primary">Click to view results</p>
                          )}

                          {task.status === 'failed' && (
                            <p className="text-xs text-red-600">Click to view error details</p>
                          )}

                          <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                            {task.estimated_duration && (
                              <div className="flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                ~{task.estimated_duration} min
                              </div>
                            )}
                            {task.dependencies.length > 0 && (
                              <div className="flex items-center gap-1">
                                <AlertCircle className="w-3 h-3" />
                                {task.dependencies.length} dependencies
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex gap-2">
                          {task.status === 'pending' && canStartTask(task) && (
                            <Button
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                startTaskMutation.mutate(task.id);
                              }}
                              disabled={startTaskMutation.isPending}
                            >
                              <PlayCircle className="w-4 h-4 mr-1" />
                              Start
                            </Button>
                          )}

                          {task.status === 'in_progress' && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  startTaskMutation.mutate(task.id);
                                }}
                                disabled={startTaskMutation.isPending}
                                title="Retry this task (reset and restart)"
                              >
                                <PlayCircle className="w-4 h-4 mr-1" />
                                Retry
                              </Button>
                              <Button
                                size="sm"
                                variant="default"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  updateTaskMutation.mutate({ taskId: task.id, action: 'complete' });
                                }}
                                disabled={updateTaskMutation.isPending}
                                className="bg-green-600 hover:bg-green-700"
                              >
                                <CheckCircle2 className="w-4 h-4 mr-1" />
                                Complete
                              </Button>
                            </>
                          )}

                          {(task.status === 'blocked' || (task.status === 'pending' && task.error)) && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                startTaskMutation.mutate(task.id);
                              }}
                              disabled={startTaskMutation.isPending}
                            >
                              <PlayCircle className="w-4 h-4 mr-1" />
                              Retry
                            </Button>
                          )}

                          {task.status === 'pending' && !canStartTask(task) && !task.error && (
                            <Badge variant="secondary" className="text-xs">
                              Waiting for dependencies
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>

      {/* Task Note Viewer Dialog */}
      <Dialog open={!!selectedTask} onOpenChange={(open) => !open && closeNoteDialog()}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <div className="flex items-center justify-between">
              <DialogTitle className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                {selectedTask?.name}
              </DialogTitle>
              {taskNote && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCopyNote}
                  className="ml-2"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 mr-2 text-green-600" />
                      Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4 mr-2" />
                      Copy
                    </>
                  )}
                </Button>
              )}
            </div>
          </DialogHeader>

          {isLoadingNote ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center space-y-2">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
                <p className="text-sm text-muted-foreground">Loading task results...</p>
              </div>
            </div>
          ) : taskNote ? (
            <div className="space-y-4">
              {taskNote.content_html ? (
                <ChartRenderer html={taskNote.content_html} />
              ) : (
                <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap">
                  {taskNote.content}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground">
                No results found for this task yet.
              </p>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Task Creation Dialog */}
      <TaskCreationDialog
        open={showCreateTaskDialog}
        onOpenChange={setShowCreateTaskDialog}
        workspaceId={workspaceId}
        existingPhases={existingPhases}
      />
    </div>
  );
}
