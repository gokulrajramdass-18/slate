"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Edit2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import {
  actionsApi,
  orchestrationActionsApi,
  type ActionBindingCreate,
  type ActionBindingResponse,
  type ActionResponse,
} from "@/lib/api/actions";

interface ScheduleActionsProps {
  scheduleId: string;
}

export function ScheduleActions({ scheduleId }: ScheduleActionsProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editingBinding, setEditingBinding] = useState<ActionBindingResponse | null>(null);
  const [formData, setFormData] = useState<ActionBindingCreate>({
    action_id: "",
    trigger_condition: "on_completion",
    execution_order: 0,
  });

  // Fetch bindings for this schedule
  const { data: bindings, isLoading: bindingsLoading } = useQuery({
    queryKey: ["schedule-actions", scheduleId],
    queryFn: () => orchestrationActionsApi.listScheduleActions(scheduleId),
  });

  // Fetch available actions
  const { data: availableActions } = useQuery({
    queryKey: ["actions", { is_active: true }],
    queryFn: () => actionsApi.list({ is_active: true }),
  });

  // Add binding mutation
  const addMutation = useMutation({
    mutationFn: (data: ActionBindingCreate) =>
      orchestrationActionsApi.bindToSchedule(scheduleId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule-actions", scheduleId] });
      toast({
        title: "Success",
        description: "Action bound to schedule successfully",
      });
      setIsAddDialogOpen(false);
      resetForm();
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Update binding mutation
  const updateMutation = useMutation({
    mutationFn: ({
      bindingId,
      data,
    }: {
      bindingId: string;
      data: Partial<ActionBindingCreate>;
    }) => orchestrationActionsApi.updateScheduleAction(scheduleId, bindingId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule-actions", scheduleId] });
      toast({
        title: "Success",
        description: "Binding updated successfully",
      });
      setEditingBinding(null);
      resetForm();
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Delete binding mutation
  const deleteMutation = useMutation({
    mutationFn: (bindingId: string) =>
      orchestrationActionsApi.deleteScheduleAction(scheduleId, bindingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedule-actions", scheduleId] });
      toast({
        title: "Success",
        description: "Action binding removed",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const resetForm = () => {
    setFormData({
      action_id: "",
      trigger_condition: "on_completion",
      execution_order: 0,
    });
  };

  const handleSubmit = () => {
    if (editingBinding) {
      updateMutation.mutate({
        bindingId: editingBinding.id,
        data: formData,
      });
    } else {
      addMutation.mutate(formData);
    }
  };

  const handleEdit = (binding: ActionBindingResponse) => {
    setEditingBinding(binding);
    setFormData({
      action_id: binding.action_id,
      trigger_condition: binding.trigger_condition as any,
      phase_filter: binding.phase_filter || undefined,
      execution_order: binding.execution_order,
    });
    setIsAddDialogOpen(true);
  };

  const handleDelete = (bindingId: string) => {
    if (confirm("Are you sure you want to remove this action binding?")) {
      deleteMutation.mutate(bindingId);
    }
  };

  const getTriggerLabel = (condition: string) => {
    const labels: Record<string, string> = {
      on_start: "On Start",
      on_completion: "On Completion",
      on_failure: "On Failure",
      on_phase_change: "On Phase Change",
      always: "Always",
    };
    return labels[condition] || condition;
  };

  const getTriggerColor = (condition: string) => {
    const colors: Record<string, string> = {
      on_start: "bg-blue-100 text-blue-800",
      on_completion: "bg-green-100 text-green-800",
      on_failure: "bg-red-100 text-red-800",
      on_phase_change: "bg-purple-100 text-purple-800",
      always: "bg-gray-100 text-gray-800",
    };
    return colors[condition] || "bg-gray-100 text-gray-800";
  };

  if (bindingsLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-semibold">Action Bindings</h3>
          <p className="text-sm text-muted-foreground">
            Configure actions to execute when this schedule runs
          </p>
        </div>
        <Button
          onClick={() => {
            resetForm();
            setEditingBinding(null);
            setIsAddDialogOpen(true);
          }}
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Action
        </Button>
      </div>

      {bindings && bindings.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Action</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Trigger</TableHead>
              <TableHead>Phase Filter</TableHead>
              <TableHead>Order</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {bindings.map((binding) => (
              <TableRow key={binding.id}>
                <TableCell className="font-medium">{binding.action_name}</TableCell>
                <TableCell>
                  <Badge variant="outline">{binding.action_type}</Badge>
                </TableCell>
                <TableCell>
                  <Badge className={getTriggerColor(binding.trigger_condition)}>
                    {getTriggerLabel(binding.trigger_condition)}
                  </Badge>
                </TableCell>
                <TableCell>
                  {binding.phase_filter && binding.phase_filter.length > 0 ? (
                    <div className="flex gap-1">
                      {binding.phase_filter.map((phase) => (
                        <Badge key={phase} variant="outline" className="text-xs">
                          {phase}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <span className="text-muted-foreground text-sm">All phases</span>
                  )}
                </TableCell>
                <TableCell>{binding.execution_order}</TableCell>
                <TableCell>
                  {binding.is_active ? (
                    <Badge className="bg-green-100 text-green-800">Active</Badge>
                  ) : (
                    <Badge variant="outline">Inactive</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEdit(binding)}
                    >
                      <Edit2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(binding.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="text-center py-12 border rounded-lg bg-muted/20">
          <Play className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
          <h3 className="text-lg font-semibold mb-1">No actions configured</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Add actions to automate tasks when this schedule runs
          </p>
          <Button
            onClick={() => {
              resetForm();
              setEditingBinding(null);
              setIsAddDialogOpen(true);
            }}
          >
            <Plus className="h-4 w-4 mr-2" />
            Add First Action
          </Button>
        </div>
      )}

      {/* Add/Edit Dialog */}
      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingBinding ? "Edit Action Binding" : "Add Action Binding"}
            </DialogTitle>
            <DialogDescription>
              Configure when and how this action should execute
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Action Selection */}
            <div>
              <Label htmlFor="action">Action *</Label>
              <Select
                value={formData.action_id}
                onValueChange={(value) =>
                  setFormData({ ...formData, action_id: value })
                }
                disabled={!!editingBinding}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select an action" />
                </SelectTrigger>
                <SelectContent>
                  {availableActions?.map((action) => (
                    <SelectItem key={action.id} value={action.id}>
                      {action.name} ({action.action_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Trigger Condition */}
            <div>
              <Label htmlFor="trigger">Trigger Condition *</Label>
              <Select
                value={formData.trigger_condition}
                onValueChange={(value) =>
                  setFormData({ ...formData, trigger_condition: value as any })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="on_start">On Start</SelectItem>
                  <SelectItem value="on_completion">On Completion</SelectItem>
                  <SelectItem value="on_failure">On Failure</SelectItem>
                  <SelectItem value="on_phase_change">On Phase Change</SelectItem>
                  <SelectItem value="always">Always</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-sm text-muted-foreground mt-1">
                When should this action execute?
              </p>
            </div>

            {/* Phase Filter (only for on_phase_change) */}
            {formData.trigger_condition === "on_phase_change" && (
              <div>
                <Label htmlFor="phases">Phase Filter (comma-separated)</Label>
                <Input
                  id="phases"
                  placeholder="planning, execution, synthesis"
                  value={formData.phase_filter?.join(", ") || ""}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      phase_filter: e.target.value
                        .split(",")
                        .map((p) => p.trim())
                        .filter(Boolean),
                    })
                  }
                />
                <p className="text-sm text-muted-foreground mt-1">
                  Leave empty to trigger on all phase changes
                </p>
              </div>
            )}

            {/* Execution Order */}
            <div>
              <Label htmlFor="order">Execution Order</Label>
              <Input
                id="order"
                type="number"
                min="0"
                value={formData.execution_order}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    execution_order: parseInt(e.target.value) || 0,
                  })
                }
              />
              <p className="text-sm text-muted-foreground mt-1">
                Lower numbers execute first (0 = highest priority)
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsAddDialogOpen(false);
                setEditingBinding(null);
                resetForm();
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={
                !formData.action_id ||
                addMutation.isPending ||
                updateMutation.isPending
              }
            >
              {addMutation.isPending || updateMutation.isPending
                ? "Saving..."
                : editingBinding
                ? "Update Binding"
                : "Add Binding"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
