/**
 * Plan Generation Step
 *
 * Shows the generated task plan with phases and assignments.
 * Allows users to add custom manual tasks.
 */

'use client';

import { useState } from 'react';
import { useGuidedCreationStore, TaskItem } from '@/lib/stores/guided-creation-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  FileText,
  Clock,
  User,
  Link as LinkIcon,
  CheckCircle2,
  Plus,
  Pencil,
  Trash2,
} from 'lucide-react';

interface TaskDialogData {
  open: boolean;
  mode: 'add' | 'edit';
  phaseIndex: number;
  taskIndex?: number;
  task: Partial<TaskItem>;
}

export function PlanGenerationStep() {
  const { generatedPlan, addManualTask, updateManualTask, deleteManualTask } =
    useGuidedCreationStore();

  const [dialogData, setDialogData] = useState<TaskDialogData>({
    open: false,
    mode: 'add',
    phaseIndex: 0,
    task: {
      name: '',
      description: '',
      estimated_duration: 0,
      dependencies: [],
      required_tools: [],
      required_sources: [],
    },
  });

  if (!generatedPlan) {
    return <div>Loading plan...</div>;
  }

  const formatDuration = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  };

  const handleOpenDialog = (
    mode: 'add' | 'edit',
    phaseIndex: number,
    taskIndex?: number
  ) => {
    if (mode === 'edit' && taskIndex !== undefined) {
      const task = generatedPlan.phases[phaseIndex].tasks?.[taskIndex];
      if (task) {
        setDialogData({
          open: true,
          mode,
          phaseIndex,
          taskIndex,
          task: { ...task },
        });
      }
    } else {
      setDialogData({
        open: true,
        mode: 'add',
        phaseIndex,
        task: {
          name: '',
          description: '',
          estimated_duration: 30,
          dependencies: [],
          required_tools: [],
          required_sources: [],
        },
      });
    }
  };

  const handleCloseDialog = () => {
    setDialogData({
      open: false,
      mode: 'add',
      phaseIndex: 0,
      task: {
        name: '',
        description: '',
        estimated_duration: 0,
        dependencies: [],
        required_tools: [],
        required_sources: [],
      },
    });
  };

  const handleSaveTask = () => {
    const { mode, phaseIndex, taskIndex, task } = dialogData;

    if (!task.name || !task.description) {
      return;
    }

    const taskToSave: TaskItem = {
      name: task.name,
      description: task.description,
      assigned_agent_id: task.assigned_agent_id,
      estimated_duration: task.estimated_duration || 0,
      dependencies: task.dependencies || [],
      required_tools: task.required_tools || [],
      required_sources: task.required_sources || [],
    };

    if (mode === 'add') {
      addManualTask(phaseIndex, taskToSave);
    } else if (taskIndex !== undefined) {
      updateManualTask(phaseIndex, taskIndex, taskToSave);
    }

    handleCloseDialog();
  };

  const handleDeleteTask = (phaseIndex: number, taskIndex: number) => {
    if (confirm('Are you sure you want to delete this task?')) {
      deleteManualTask(phaseIndex, taskIndex);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          <FileText className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">Execution Plan</h2>
          <p className="text-muted-foreground">
            Based on your goal and selected resources, here's a phased plan to achieve your objectives.
            Tasks will be executed by AI agents and can run automatically or with your supervision.
          </p>
        </div>
      </div>

      {/* Summary */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="pt-6">
          <div className="grid grid-cols-3 gap-6 text-center">
            <div>
              <p className="text-3xl font-bold text-primary">
                {generatedPlan.phases.length}
              </p>
              <p className="text-sm text-muted-foreground mt-1">Phases</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-primary">
                {generatedPlan.phases.reduce((acc, phase) => acc + (phase.tasks?.length || 0), 0)}
              </p>
              <p className="text-sm text-muted-foreground mt-1">Tasks</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-primary">
                {formatDuration(generatedPlan.estimated_total_duration)}
              </p>
              <p className="text-sm text-muted-foreground mt-1">Estimated Time</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Phases */}
      <div className="space-y-6">
        {generatedPlan.phases.map((phase, phaseIndex) => (
          <Card key={phaseIndex}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">
                  Phase {phaseIndex + 1}: {phase.phase}
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Badge variant="outline">{phase.tasks?.length || 0} tasks</Badge>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenDialog('add', phaseIndex)}
                  >
                    <Plus className="h-4 w-4 mr-1" />
                    Add Task
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {phase.tasks && phase.tasks.map((task, taskIndex) => (
                <div key={taskIndex}>
                  {taskIndex > 0 && <Separator className="my-4" />}

                  <div className="space-y-3">
                    {/* Task Header */}
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
                          <h4 className="font-medium">{task.name}</h4>
                          {task.is_manual && (
                            <Badge variant="secondary" className="text-xs">
                              Manual
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1 ml-6">
                          {task.description}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        {task.estimated_duration && (
                          <Badge variant="secondary">
                            <Clock className="h-3 w-3 mr-1" />
                            {formatDuration(task.estimated_duration)}
                          </Badge>
                        )}
                        {task.is_manual && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenDialog('edit', phaseIndex, taskIndex)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteTask(phaseIndex, taskIndex)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Task Details */}
                    <div className="ml-6 space-y-2">
                      {/* Assigned Agent */}
                      {task.assigned_agent_id && (
                        <div className="flex items-center gap-2 text-sm">
                          <User className="h-3 w-3 text-muted-foreground" />
                          <span className="text-muted-foreground">Assigned to:</span>
                          <Badge variant="outline" className="text-xs">
                            {generatedPlan.agent_assignments[task.assigned_agent_id] ||
                              task.assigned_agent_id}
                          </Badge>
                        </div>
                      )}

                      {/* Dependencies */}
                      {task.dependencies && task.dependencies.length > 0 && (
                        <div className="flex items-start gap-2 text-sm">
                          <LinkIcon className="h-3 w-3 text-muted-foreground mt-0.5" />
                          <span className="text-muted-foreground">Depends on:</span>
                          <div className="flex flex-wrap gap-1">
                            {task.dependencies.map((dep, i) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {dep}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Required Tools */}
                      {task.required_tools && task.required_tools.length > 0 && (
                        <div className="flex items-start gap-2 text-sm">
                          <span className="text-muted-foreground">Tools:</span>
                          <div className="flex flex-wrap gap-1">
                            {task.required_tools.map((tool, i) => (
                              <Badge key={i} variant="secondary" className="text-xs">
                                {tool}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Required Sources */}
                      {task.required_sources && task.required_sources.length > 0 && (
                        <div className="flex items-start gap-2 text-sm">
                          <span className="text-muted-foreground">Data:</span>
                          <div className="flex flex-wrap gap-1">
                            {task.required_sources.map((source, i) => (
                              <Badge key={i} variant="secondary" className="text-xs">
                                {source}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Task Dialog */}
      <Dialog open={dialogData.open} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {dialogData.mode === 'add' ? 'Add Manual Task' : 'Edit Manual Task'}
            </DialogTitle>
            <DialogDescription>
              {dialogData.mode === 'add'
                ? 'Add a custom task to this phase that will be executed manually.'
                : 'Edit the details of this manual task.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="task-name">Task Name</Label>
              <Input
                id="task-name"
                placeholder="e.g., Review data quality"
                value={dialogData.task.name || ''}
                onChange={(e) =>
                  setDialogData((prev) => ({
                    ...prev,
                    task: { ...prev.task, name: e.target.value },
                  }))
                }
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="task-description">Description</Label>
              <Textarea
                id="task-description"
                placeholder="Describe what needs to be done..."
                value={dialogData.task.description || ''}
                onChange={(e) =>
                  setDialogData((prev) => ({
                    ...prev,
                    task: { ...prev.task, description: e.target.value },
                  }))
                }
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="task-duration">Estimated Duration (minutes)</Label>
              <Input
                id="task-duration"
                type="number"
                min="0"
                placeholder="30"
                value={dialogData.task.estimated_duration || 0}
                onChange={(e) =>
                  setDialogData((prev) => ({
                    ...prev,
                    task: {
                      ...prev.task,
                      estimated_duration: parseInt(e.target.value) || 0,
                    },
                  }))
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveTask}
              disabled={!dialogData.task.name || !dialogData.task.description}
            >
              {dialogData.mode === 'add' ? 'Add Task' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
