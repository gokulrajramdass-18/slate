/**
 * Task Creation Dialog
 *
 * Allows users to manually create tasks for workspaces
 */

'use client';

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api/client';

interface TaskCreationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workspaceId: string;
  existingPhases?: string[];
}

interface CreateTaskData {
  phase_name: string;
  name: string;
  description?: string;
  estimated_duration?: number;
}

export function TaskCreationDialog({
  open,
  onOpenChange,
  workspaceId,
  existingPhases = [],
}: TaskCreationDialogProps) {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<CreateTaskData>({
    phase_name: existingPhases[0] || 'Default Phase',
    name: '',
    description: '',
    estimated_duration: undefined,
  });

  const createTaskMutation = useMutation({
    mutationFn: async (data: CreateTaskData) => {
      const response = await apiClient.post(`/workspaces/${workspaceId}/tasks`, data);
      return response.data;
    },
    onSuccess: () => {
      toast.success('Task created successfully');
      queryClient.invalidateQueries({ queryKey: ['workspace-tasks', workspaceId] });
      queryClient.invalidateQueries({ queryKey: ['workspace-progress', workspaceId] });
      onOpenChange(false);
      resetForm();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create task');
    },
  });

  const resetForm = () => {
    setFormData({
      phase_name: existingPhases[0] || 'Default Phase',
      name: '',
      description: '',
      estimated_duration: undefined,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.name.trim()) {
      toast.error('Please enter a task name');
      return;
    }

    if (!formData.phase_name.trim()) {
      toast.error('Please enter a phase name');
      return;
    }

    createTaskMutation.mutate(formData);
  };

  const handleClose = (open: boolean) => {
    onOpenChange(open);
    if (!open) {
      resetForm();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Create Task</DialogTitle>
          <DialogDescription>
            Add a new task to this workspace. Tasks help you organize and track your work.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="phase_name">
              Phase <span className="text-red-500">*</span>
            </Label>
            <Input
              id="phase_name"
              value={formData.phase_name}
              onChange={(e) => setFormData({ ...formData, phase_name: e.target.value })}
              placeholder="e.g., Research, Implementation, Testing"
              required
            />
            {existingPhases.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                <p className="text-xs text-muted-foreground w-full">Existing phases:</p>
                {existingPhases.map((phase) => (
                  <button
                    key={phase}
                    type="button"
                    onClick={() => setFormData({ ...formData, phase_name: phase })}
                    className="text-xs px-2 py-1 rounded-md bg-secondary hover:bg-secondary/80 transition-colors"
                  >
                    {phase}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="name">
              Task Name <span className="text-red-500">*</span>
            </Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Research API documentation"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Describe what needs to be done..."
              rows={4}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="estimated_duration">Estimated Duration (minutes)</Label>
            <Input
              id="estimated_duration"
              type="number"
              min="0"
              value={formData.estimated_duration || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  estimated_duration: e.target.value ? parseInt(e.target.value) : undefined,
                })
              }
              placeholder="e.g., 30"
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleClose(false)}
              disabled={createTaskMutation.isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createTaskMutation.isPending}>
              <Plus className="w-4 h-4 mr-2" />
              {createTaskMutation.isPending ? 'Creating...' : 'Create Task'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
