"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Edit, Play, Pause, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import { ActionForm } from "@/components/actions/ActionForm";
import { ActionExecutionHistory } from "@/components/actions/ExecutionHistory";
import { actionsApi } from "@/lib/api/actions";
import type { ActionResponse } from "@/lib/api/actions";

export default function ActionsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingAction, setEditingAction] = useState<ActionResponse | null>(null);
  const [historyActionId, setHistoryActionId] = useState<string | null>(null);

  // Fetch actions
  const { data: actions, isLoading } = useQuery({
    queryKey: ["actions"],
    queryFn: () => actionsApi.list(),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => actionsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      toast({
        title: "Success",
        description: "Action deleted successfully",
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

  // Toggle active mutation
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      actionsApi.update(id, { is_active: !isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      toast({
        title: "Success",
        description: "Action status updated",
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

  // Test mutation
  const testMutation = useMutation({
    mutationFn: (id: string) => actionsApi.test(id),
    onSuccess: (result) => {
      toast({
        title: result.success ? "Test Passed" : "Test Failed",
        description: result.message,
        variant: result.success ? "default" : "destructive",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Test Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleCreate = () => {
    setEditingAction(null);
    setIsFormOpen(true);
  };

  const handleEdit = (action: ActionResponse) => {
    setEditingAction(action);
    setIsFormOpen(true);
  };

  const handleDelete = (id: string) => {
    if (confirm("Are you sure you want to delete this action?")) {
      deleteMutation.mutate(id);
    }
  };

  const handleToggleActive = (action: ActionResponse) => {
    toggleActiveMutation.mutate({ id: action.id, isActive: action.is_active });
  };

  const handleTest = (id: string) => {
    testMutation.mutate(id);
  };

  const handleFormClose = () => {
    setIsFormOpen(false);
    setEditingAction(null);
  };

  const getActionTypeColor = (type: string) => {
    switch (type) {
      case "webhook":
        return "bg-blue-500";
      case "email":
        return "bg-green-500";
      case "hana_operation":
        return "bg-purple-500";
      case "workflow_trigger":
        return "bg-orange-500";
      default:
        return "bg-gray-500";
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Actions</h1>
          <p className="text-muted-foreground mt-2">
            Configure reusable actions for orchestrations and chat
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="h-4 w-4 mr-2" />
          New Action
        </Button>
      </div>

      {actions && actions.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Configured Actions</CardTitle>
            <CardDescription>
              {actions.length} action{actions.length !== 1 ? "s" : ""} configured
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Endpoint</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Executions</TableHead>
                  <TableHead>Last Executed</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {actions.map((action) => (
                  <TableRow key={action.id}>
                    <TableCell className="font-medium">
                      {action.name}
                      {action.description && (
                        <p className="text-sm text-muted-foreground">
                          {action.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={getActionTypeColor(action.action_type)}>
                        {action.action_type.replace("_", " ")}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-xs truncate">
                      {action.endpoint || "-"}
                    </TableCell>
                    <TableCell>
                      {action.is_active ? (
                        <Badge variant="outline" className="bg-green-50">
                          Active
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-gray-50">
                          Inactive
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="link"
                        size="sm"
                        onClick={() => setHistoryActionId(action.id)}
                        className="p-0 h-auto"
                      >
                        {action.execution_count || 0}
                      </Button>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {action.last_executed_at
                        ? new Date(action.last_executed_at).toLocaleString()
                        : "Never"}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleTest(action.id)}
                          disabled={testMutation.isPending}
                        >
                          <Play className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setHistoryActionId(action.id)}
                        >
                          <Activity className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleActive(action)}
                        >
                          {action.is_active ? (
                            <Pause className="h-4 w-4" />
                          ) : (
                            <Play className="h-4 w-4" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEdit(action)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(action.id)}
                          disabled={deleteMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-muted-foreground mb-4">No actions configured yet</p>
            <Button onClick={handleCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Action
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Action Form Dialog */}
      <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingAction ? "Edit Action" : "Create Action"}
            </DialogTitle>
            <DialogDescription>
              Configure action details, authentication, and execution settings
            </DialogDescription>
          </DialogHeader>
          <ActionForm
            action={editingAction}
            onSuccess={handleFormClose}
            onCancel={handleFormClose}
          />
        </DialogContent>
      </Dialog>

      {/* Execution History Dialog */}
      <Dialog open={!!historyActionId} onOpenChange={() => setHistoryActionId(null)}>
        <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Execution History</DialogTitle>
            <DialogDescription>
              View past executions for this action
            </DialogDescription>
          </DialogHeader>
          {historyActionId && <ActionExecutionHistory actionId={historyActionId} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}
