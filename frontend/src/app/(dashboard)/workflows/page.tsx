/**
 * Workflows & Templates Page
 *
 * Combined view for managing workflows and workflow templates.
 */

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Plus, Play, Calendar, MoreVertical, Pencil, Trash2, Workflow as WorkflowIcon, Copy, Eye, TrendingUp, Users, Tag, Clock, ChevronDown, Globe, Share2 } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import { workflowsApi } from '@/lib/api/workflows';
import { workflowTemplatesApi } from '@/lib/api/workflow-templates';
import { apiClient } from '@/lib/api/client';
import { useToast } from '@/hooks/use-toast';
import { useAuthStore } from '@/lib/stores/auth-store';
import type { Workflow } from '@/lib/api/workflows';
import { PublicGallery } from '@/components/workflows/PublicGallery';
import { MyWorkflows } from '@/components/workflows/MyWorkflows';
import { MyTemplates } from '@/components/workflows/MyTemplates';

// ============================================================================
// Types
// ============================================================================

interface WorkflowSummary {
  id: string;
  name: string;
  description?: string;
  node_count: number;
  edge_count: number;
  is_active: boolean;
  tags: string[];
  created_by: string;
  updated_at?: string;
  source_template?: {
    template_id: string;
    template_name: string;
    template_is_public: boolean;
  };
}

interface TemplateParameter {
  name: string;
  type: string;
  description?: string;
  default_value?: any;
  required: boolean;
  options?: string[];
}

interface WorkflowTemplate {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  category?: string;
  source_workflow_id?: string;
  node_count: number;
  edge_count: number;
  parameter_count: number;
  version: number;
  is_public: boolean;
  tags: string[];
  usage_count: number;
  created_at: string;
  updated_at: string;
  consumed_by_user?: boolean;
}

interface WorkflowTemplateDetail extends WorkflowTemplate {
  graph_json: string;
  graph?: any;
  parameters: TemplateParameter[];
}

// ============================================================================
// Workflow Card Component
// ============================================================================

function WorkflowCard({ workflow }: { workflow: WorkflowSummary }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [showSaveAsTemplateDialog, setShowSaveAsTemplateDialog] = React.useState(false);
  const [templateName, setTemplateName] = React.useState(workflow.name + ' Template');
  const [templateDescription, setTemplateDescription] = React.useState('');
  const [templateCategory, setTemplateCategory] = React.useState('');
  const [templateIsPublic, setTemplateIsPublic] = React.useState(false);
  const [templateTags, setTemplateTags] = React.useState('');

  const deleteMutation = useMutation({
    mutationFn: () => workflowsApi.delete(workflow.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
      setShowDeleteDialog(false);
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => workflowsApi.execute(workflow.id),
  });

  const saveAsTemplateMutation = useMutation({
    mutationFn: async () => {
      const tags = templateTags.split(',').map(tag => tag.trim()).filter(Boolean);
      const { data } = await apiClient.post(
        `/workflows/${workflow.id}/save-as-template`,
        null,
        {
          params: {
            name: templateName,
            description: templateDescription || undefined,
            category: templateCategory || undefined,
            is_public: templateIsPublic,
            tags: tags.length > 0 ? tags : undefined,
          }
        }
      );
      return data;
    },
    onSuccess: (data) => {
      toast({
        title: "Success",
        description: templateIsPublic
          ? "Workflow saved as public template and available in the gallery"
          : "Workflow saved as private template",
      });
      queryClient.invalidateQueries({ queryKey: ['workflow-templates'] });
      setShowSaveAsTemplateDialog(false);
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleEdit = () => {
    router.push(`/workflows/${workflow.id}`);
  };

  const handleExecute = async () => {
    try {
      await executeMutation.mutateAsync();
      router.push(`/workflows/${workflow.id}/executions`);
    } catch (error) {
      console.error('Failed to execute workflow:', error);
    }
  };

  const handleDeleteConfirm = async () => {
    await deleteMutation.mutateAsync();
  };

  const handleSaveAsTemplate = () => {
    setTemplateName(workflow.name + ' Template');
    setTemplateDescription(workflow.description || '');
    setTemplateCategory('');
    setTemplateIsPublic(false);
    setTemplateTags(workflow.tags.join(', '));
    setShowSaveAsTemplateDialog(true);
  };

  const handleSaveAsTemplateConfirm = async () => {
    await saveAsTemplateMutation.mutateAsync();
  };

  return (
    <>
      <Card className="hover:shadow-lg transition-shadow cursor-pointer group">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0" onClick={handleEdit}>
              <CardTitle className="mb-2 truncate">{workflow.name}</CardTitle>
              {workflow.description && (
                <CardDescription className="line-clamp-2">{workflow.description}</CardDescription>
              )}
            </div>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={handleEdit}>
                  <Pencil className="h-4 w-4 mr-2" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleExecute}>
                  <Play className="h-4 w-4 mr-2" />
                  Execute
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => router.push(`/workflows/${workflow.id}/schedules`)}>
                  <Calendar className="h-4 w-4 mr-2" />
                  Schedules
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleSaveAsTemplate}>
                  <Copy className="h-4 w-4 mr-2" />
                  Save as Template
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => setShowDeleteDialog(true)}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardHeader>

        <CardContent className="space-y-3">
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>{workflow.node_count} nodes</span>
            <span>{workflow.edge_count} edges</span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {workflow.source_template?.template_is_public && (
              <Badge variant="secondary" className="bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900 dark:text-purple-300">
                <Globe className="h-3 w-3 mr-1" />
                From Gallery
              </Badge>
            )}

            {workflow.is_active ? (
              <Badge variant="default">Active</Badge>
            ) : (
              <Badge variant="secondary">Inactive</Badge>
            )}

            {workflow.tags.slice(0, 3).map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
            {workflow.tags.length > 3 && (
              <Badge variant="outline" className="text-xs">
                +{workflow.tags.length - 3}
              </Badge>
            )}
          </div>

          {workflow.source_template && (
            <div className="text-xs text-muted-foreground truncate">
              Created from template: <span className="font-medium">{workflow.source_template.template_name}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Workflow</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{workflow.name}"? This action cannot be undone.
              All associated schedules and execution history will also be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Save as Template Dialog */}
      <Dialog open={showSaveAsTemplateDialog} onOpenChange={setShowSaveAsTemplateDialog}>
        <DialogContent className="sm:max-w-[550px]">
          <DialogHeader>
            <DialogTitle>Save as Template</DialogTitle>
            <DialogDescription>
              Convert this workflow into a reusable template. Public templates will be visible in the gallery for all users.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="template-name">
                Template Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="template-name"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="Enter template name"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-description">Description</Label>
              <Input
                id="template-description"
                value={templateDescription}
                onChange={(e) => setTemplateDescription(e.target.value)}
                placeholder="Describe what this template does"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-category">Category</Label>
              <Select value={templateCategory} onValueChange={setTemplateCategory}>
                <SelectTrigger id="template-category">
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="data">Data Processing</SelectItem>
                  <SelectItem value="research">Research</SelectItem>
                  <SelectItem value="automation">Automation</SelectItem>
                  <SelectItem value="content">Content Generation</SelectItem>
                  <SelectItem value="analysis">Analysis</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="template-tags">Tags (comma-separated)</Label>
              <Input
                id="template-tags"
                value={templateTags}
                onChange={(e) => setTemplateTags(e.target.value)}
                placeholder="e.g., automation, research, data"
              />
            </div>

            <div className="flex items-center space-x-2 pt-2 pb-2 px-3 border rounded-md bg-muted/30">
              <input
                type="checkbox"
                id="template-public"
                checked={templateIsPublic}
                onChange={(e) => setTemplateIsPublic(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300"
              />
              <div className="flex-1">
                <Label htmlFor="template-public" className="cursor-pointer font-medium">
                  Make this template public
                </Label>
                <p className="text-xs text-muted-foreground">
                  Public templates will appear in the gallery and can be used by all users
                </p>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveAsTemplateDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveAsTemplateConfirm}
              disabled={!templateName.trim() || saveAsTemplateMutation.isPending}
            >
              {saveAsTemplateMutation.isPending ? "Saving..." : "Save Template"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ============================================================================
// Template Card Component
// ============================================================================

function TemplateCard({ template, onViewDetails }: { template: WorkflowTemplate; onViewDetails: (template: WorkflowTemplate) => void }) {
  const { toast } = useToast();
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const userId = user?.id || user?.username || "test-user";
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplateDetail | null>(null);
  const [parameterValues, setParameterValues] = useState<Record<string, any>>({});
  const [showExecuteDialog, setShowExecuteDialog] = useState(false);
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [scheduleType, setScheduleType] = useState<"daily" | "weekly" | "monthly" | "custom">("daily");
  const [scheduleTime, setScheduleTime] = useState("09:00");
  const [scheduleDayOfWeek, setScheduleDayOfWeek] = useState("monday");
  const [scheduleDayOfMonth, setScheduleDayOfMonth] = useState("1");
  const [customCron, setCustomCron] = useState("0 9 * * *");

  const executeMutation = useMutation({
    mutationFn: async ({ templateId, parameters }: { templateId: string; parameters: Record<string, any> }) => {
      return workflowTemplatesApi.execute(templateId, { parameters, input_data: {} });
    },
    onSuccess: (data) => {
      toast({
        title: "Success",
        description: "Workflow executed from template",
      });
      router.push(`/workflows/${data.workflow_id}/executions/${data.execution_id}`);
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const createScheduleMutation = useMutation({
    mutationFn: async ({ templateId, workflowId, cronExpression, parameters }: {
      templateId: string;
      workflowId: string;
      cronExpression: string;
      parameters: Record<string, any>;
    }) => {
      return workflowsApi.createSchedule(workflowId, {
        schedule_type: "cron",
        cron_expression: cronExpression,
        enabled: true,
      });
    },
    onSuccess: () => {
      toast({
        title: "Schedule Created",
        description: "Template will run automatically based on the schedule",
      });
      setShowScheduleDialog(false);
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const handleExecuteClick = async () => {
    const details = await workflowTemplatesApi.get(template.id);

    try {
      if (details.graph_json) {
        (details as any).graph = JSON.parse(details.graph_json);
      }
    } catch (e) {
      console.error("Failed to parse graph JSON:", e);
    }

    setSelectedTemplate(details as any);

    // Initialize parameter values with defaults
    const defaults: Record<string, any> = {};
    (details.parameters || []).forEach((param: TemplateParameter) => {
      if (param.default_value !== undefined) {
        defaults[param.name] = param.default_value;
      }
    });
    setParameterValues(defaults);
    setShowExecuteDialog(true);
  };

  const handleExecute = () => {
    if (!selectedTemplate) return;
    executeMutation.mutate({
      templateId: selectedTemplate.id,
      parameters: parameterValues
    });
    setShowExecuteDialog(false);
  };

  const handleScheduleClick = async (type: "daily" | "weekly" | "monthly" | "custom") => {
    const details = await workflowTemplatesApi.get(template.id);

    try {
      if (details.graph_json) {
        (details as any).graph = JSON.parse(details.graph_json);
      }
    } catch (e) {
      console.error("Failed to parse graph JSON:", e);
    }

    setSelectedTemplate(details as any);

    // Initialize parameter values with defaults
    const defaults: Record<string, any> = {};
    (details.parameters || []).forEach((param: TemplateParameter) => {
      if (param.default_value !== undefined) {
        defaults[param.name] = param.default_value;
      }
    });
    setParameterValues(defaults);
    setScheduleType(type);
    setShowScheduleDialog(true);
  };

  const handleCreateSchedule = async () => {
    if (!selectedTemplate) return;

    try {
      // First, instantiate the template to get a workflow ID
      const { workflow_id } = await workflowTemplatesApi.instantiate(selectedTemplate.id, {
        parameters: parameterValues
      });

      // Convert schedule type to cron expression
      let cronExpression = customCron;
      if (scheduleType === "daily") {
        const [hour, minute] = scheduleTime.split(":");
        cronExpression = `${minute} ${hour} * * *`;
      } else if (scheduleType === "weekly") {
        const [hour, minute] = scheduleTime.split(":");
        const dayMap: Record<string, string> = {
          monday: "1", tuesday: "2", wednesday: "3", thursday: "4",
          friday: "5", saturday: "6", sunday: "0"
        };
        cronExpression = `${minute} ${hour} * * ${dayMap[scheduleDayOfWeek]}`;
      } else if (scheduleType === "monthly") {
        const [hour, minute] = scheduleTime.split(":");
        cronExpression = `${minute} ${hour} ${scheduleDayOfMonth} * *`;
      }

      // Create the schedule
      createScheduleMutation.mutate({
        templateId: selectedTemplate.id,
        workflowId: workflow_id,
        cronExpression,
        parameters: parameterValues
      });
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create schedule",
        variant: "destructive",
      });
    }
  };

  return (
    <>
      <Card className="hover:shadow-lg transition-all">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="mb-2">{template.name}</CardTitle>
              <CardDescription className="line-clamp-2">
                {template.description || "No description"}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {template.consumed_by_user && (
                <span style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  padding: '0.125rem 0.625rem',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  backgroundColor: '#d1fae5',
                  color: '#047857',
                  border: '1px solid #a7f3d0'
                }}>
                  <Copy className="h-3 w-3" />
                  Consumed
                </span>
              )}
              <Badge variant={template.is_public ? "default" : "secondary"}>
                {template.is_public ? "Public" : "Private"}
              </Badge>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          <div className="space-y-3">
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <WorkflowIcon className="h-4 w-4" />
                <span>{template.node_count} nodes</span>
              </div>
              <div className="flex items-center gap-1">
                <Users className="h-4 w-4" />
                <span>{template.usage_count} uses</span>
              </div>
            </div>

            {template.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {template.tags.slice(0, 3).map((tag) => (
                  <Badge key={tag} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
                {template.tags.length > 3 && (
                  <Badge variant="outline" className="text-xs">
                    +{template.tags.length - 3}
                  </Badge>
                )}
              </div>
            )}
          </div>
        </CardContent>

        <CardFooter className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button className="flex-1">
                <Play className="h-4 w-4 mr-2" />
                Execute
                <ChevronDown className="h-4 w-4 ml-2" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={handleExecuteClick}>
                <Play className="h-4 w-4 mr-2" />
                Execute Now
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleScheduleClick("daily")}>
                <Calendar className="h-4 w-4 mr-2" />
                Schedule Daily
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleScheduleClick("weekly")}>
                <Calendar className="h-4 w-4 mr-2" />
                Schedule Weekly
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleScheduleClick("monthly")}>
                <Calendar className="h-4 w-4 mr-2" />
                Schedule Monthly
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleScheduleClick("custom")}>
                <Clock className="h-4 w-4 mr-2" />
                Schedule Custom
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <Button variant="outline" onClick={() => onViewDetails(template)}>
            <Eye className="h-4 w-4 mr-2" />
            View
          </Button>
        </CardFooter>
      </Card>

      {/* Execute Dialog */}
      <Dialog open={showExecuteDialog} onOpenChange={setShowExecuteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Execute Template</DialogTitle>
            <DialogDescription>Configure parameters and execute the workflow</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {selectedTemplate?.parameters.map((param) => (
              <div key={param.name} className="space-y-2">
                <Label htmlFor={param.name}>
                  {param.name}
                  {param.required && <span className="text-destructive ml-1">*</span>}
                </Label>
                {param.type === "select" && param.options ? (
                  <Select
                    value={parameterValues[param.name] || param.default_value || ""}
                    onValueChange={(value) =>
                      setParameterValues((prev) => ({ ...prev, [param.name]: value }))
                    }
                  >
                    <SelectTrigger id={param.name}>
                      <SelectValue placeholder="Select value" />
                    </SelectTrigger>
                    <SelectContent>
                      {param.options.map((option) => (
                        <SelectItem key={option} value={option}>
                          {option}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    id={param.name}
                    type="text"
                    value={parameterValues[param.name] || param.default_value || ""}
                    onChange={(e) =>
                      setParameterValues((prev) => ({ ...prev, [param.name]: e.target.value }))
                    }
                    placeholder={param.description}
                  />
                )}
                {param.description && (
                  <p className="text-sm text-muted-foreground">{param.description}</p>
                )}
              </div>
            ))}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowExecuteDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleExecute} disabled={executeMutation.isPending}>
              {executeMutation.isPending ? "Executing..." : "Execute"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Schedule Dialog */}
      <Dialog open={showScheduleDialog} onOpenChange={setShowScheduleDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Schedule Template Execution</DialogTitle>
            <DialogDescription>
              Configure when this workflow template should run automatically
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {scheduleType === "daily" && (
              <div className="space-y-2">
                <Label htmlFor="time">Time</Label>
                <Input
                  id="time"
                  type="time"
                  value={scheduleTime}
                  onChange={(e) => setScheduleTime(e.target.value)}
                />
                <p className="text-sm text-muted-foreground">
                  Workflow will run every day at this time
                </p>
              </div>
            )}

            {scheduleType === "weekly" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="day-of-week">Day of Week</Label>
                  <Select value={scheduleDayOfWeek} onValueChange={setScheduleDayOfWeek}>
                    <SelectTrigger id="day-of-week">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="monday">Monday</SelectItem>
                      <SelectItem value="tuesday">Tuesday</SelectItem>
                      <SelectItem value="wednesday">Wednesday</SelectItem>
                      <SelectItem value="thursday">Thursday</SelectItem>
                      <SelectItem value="friday">Friday</SelectItem>
                      <SelectItem value="saturday">Saturday</SelectItem>
                      <SelectItem value="sunday">Sunday</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="time">Time</Label>
                  <Input
                    id="time"
                    type="time"
                    value={scheduleTime}
                    onChange={(e) => setScheduleTime(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Workflow will run every {scheduleDayOfWeek} at this time
                  </p>
                </div>
              </>
            )}

            {scheduleType === "monthly" && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="day-of-month">Day of Month</Label>
                  <Select value={scheduleDayOfMonth} onValueChange={setScheduleDayOfMonth}>
                    <SelectTrigger id="day-of-month">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 28 }, (_, i) => i + 1).map((day) => (
                        <SelectItem key={day} value={String(day)}>
                          {day}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="time">Time</Label>
                  <Input
                    id="time"
                    type="time"
                    value={scheduleTime}
                    onChange={(e) => setScheduleTime(e.target.value)}
                  />
                  <p className="text-sm text-muted-foreground">
                    Workflow will run on day {scheduleDayOfMonth} of each month at this time
                  </p>
                </div>
              </>
            )}

            {scheduleType === "custom" && (
              <div className="space-y-2">
                <Label htmlFor="cron">Cron Expression</Label>
                <Input
                  id="cron"
                  type="text"
                  value={customCron}
                  onChange={(e) => setCustomCron(e.target.value)}
                  placeholder="0 9 * * *"
                />
                <p className="text-xs text-muted-foreground">
                  Format: minute hour day month day-of-week
                  <br />
                  Examples: "0 9 * * *" (daily at 9am), "*/15 * * * *" (every 15 min)
                </p>
              </div>
            )}

            {selectedTemplate?.parameters && selectedTemplate.parameters.length > 0 && (
              <div className="border-t pt-4 space-y-4">
                <h4 className="font-medium text-sm">Template Parameters</h4>
                {selectedTemplate.parameters.map((param) => (
                  <div key={param.name} className="space-y-2">
                    <Label htmlFor={param.name}>
                      {param.name}
                      {param.required && <span className="text-destructive ml-1">*</span>}
                    </Label>
                    {param.type === "select" && param.options ? (
                      <Select
                        value={parameterValues[param.name] || param.default_value || ""}
                        onValueChange={(value) =>
                          setParameterValues((prev) => ({ ...prev, [param.name]: value }))
                        }
                      >
                        <SelectTrigger id={param.name}>
                          <SelectValue placeholder="Select value" />
                        </SelectTrigger>
                        <SelectContent>
                          {param.options.map((option) => (
                            <SelectItem key={option} value={option}>
                              {option}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input
                        id={param.name}
                        type="text"
                        value={parameterValues[param.name] || param.default_value || ""}
                        onChange={(e) =>
                          setParameterValues((prev) => ({ ...prev, [param.name]: e.target.value }))
                        }
                        placeholder={param.description}
                      />
                    )}
                    {param.description && (
                      <p className="text-sm text-muted-foreground">{param.description}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowScheduleDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateSchedule}
              disabled={createScheduleMutation.isPending}
            >
              {createScheduleMutation.isPending ? "Creating..." : "Create Schedule"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ============================================================================
// Main Page
// ============================================================================

export default function WorkflowsPage() {
  const router = useRouter();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const userId = user?.id || user?.username || "test-user";
  const [activeTab, setActiveTab] = useState("public-gallery");
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplate | null>(null);

  // Fetch workflows
  const { data: workflows, isLoading: workflowsLoading } = useQuery<WorkflowSummary[]>({
    queryKey: ['workflows'],
    queryFn: async () => {
      const data = await workflowsApi.list();
      return data.map((w: any) => ({
        id: w.id,
        name: w.name,
        description: w.description,
        node_count: w.node_count || 0,
        edge_count: w.edge_count || 0,
        is_active: w.is_active,
        tags: w.tags || [],
        created_by: w.created_by,
        updated_at: w.updated_at,
        source_template: w.source_template,
      }));
    },
  });

  // Fetch templates
  const { data: myTemplates = [], isLoading: myTemplatesLoading } = useQuery<any[]>({
    queryKey: ["workflow-templates", "my-templates", userId],
    queryFn: () => workflowTemplatesApi.list(),
    enabled: activeTab === "my-templates",
  });

  const { data: publicTemplates = [], isLoading: publicTemplatesLoading } = useQuery<any[]>({
    queryKey: ["workflow-templates", "public", userId],
    queryFn: () => workflowTemplatesApi.listPublic(),
    enabled: activeTab === "public-gallery",
  });

  // Fetch schedules
  const { data: schedulesData, isLoading: schedulesLoading } = useQuery({
    queryKey: ["scheduler-jobs"],
    queryFn: async () => {
      const { data } = await apiClient.get("/workflows/scheduler/jobs");
      return data;
    },
    enabled: activeTab === "schedules",
  });

  const handleCreateNew = () => {
    router.push('/workflows/new');
  };

  const handleViewTemplateDetails = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
  };

  const handleScheduleTemplate = async (template: WorkflowTemplate) => {
    // Get template details
    const details = await workflowTemplatesApi.get(template.id);

    try {
      if (details.graph_json) {
        (details as any).graph = JSON.parse(details.graph_json);
      }
    } catch (e) {
      console.error("Failed to parse graph JSON:", e);
    }

    // Initialize parameter values with defaults
    const defaults: Record<string, any> = {};
    (details.parameters || []).forEach((param: any) => {
      if (param.default_value !== undefined) {
        defaults[param.name] = param.default_value;
      }
    });

    // For now, just show a toast - full implementation would need schedule dialog
    toast({
      title: "Schedule Template",
      description: "Schedule functionality coming soon! Use the dropdown in the template card for now.",
    });
  };

  const handleExecuteTemplate = async (template: WorkflowTemplate) => {
    try {
      const details = await workflowTemplatesApi.get(template.id);
      const result = await workflowTemplatesApi.execute(template.id, {
        parameters: {},
        input_data: {}
      });

      toast({
        title: "Success",
        description: "Workflow executed from template",
      });

      router.push(`/workflows/${result.workflow_id}/executions/${result.execution_id}`);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to execute template",
        variant: "destructive",
      });
    }
  };

  // Workflow handlers
  const handleEditWorkflow = (id: string) => {
    router.push(`/workflows/${id}`);
  };

  const handleExecuteWorkflow = async (id: string) => {
    try {
      await workflowsApi.execute(id);
      router.push(`/workflows/${id}/executions`);
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to execute workflow",
        variant: "destructive",
      });
    }
  };

  const handleScheduleWorkflow = (id: string) => {
    router.push(`/workflows/${id}/schedules`);
  };

  const handleSaveAsTemplate = (id: string) => {
    // This will be handled by WorkflowCard's dialog
    toast({
      title: "Info",
      description: "Use the workflow card's action menu to save as template",
    });
  };

  const handleDeleteWorkflow = async (id: string) => {
    try {
      await workflowsApi.delete(id);
      toast({
        title: "Success",
        description: "Workflow deleted",
      });
      // Invalidate and refetch workflows without page reload
      queryClient.invalidateQueries({ queryKey: ['workflows'] });
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to delete workflow",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="p-6 space-y-6 bg-background min-h-screen">
      {/* Header */}
      <div className="flex justify-between items-center animate-fade-in-up">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
            Workflows
          </h1>
          <p className="text-muted-foreground mt-1">
            Create and manage visual workflow automations
          </p>
        </div>

        <Button onClick={handleCreateNew} className="transition-all hover:scale-105 hover:shadow-lg">
          <Plus className="mr-2 h-4 w-4" />
          New Workflow
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-4 lg:w-[800px] h-12">
          <TabsTrigger value="public-gallery" className="text-sm font-semibold">Public Gallery</TabsTrigger>
          <TabsTrigger value="my-workflows" className="text-sm font-semibold">My Workflows</TabsTrigger>
          <TabsTrigger value="my-templates" className="text-sm font-semibold">My Templates</TabsTrigger>
          <TabsTrigger value="schedules" className="text-sm font-semibold">Schedules</TabsTrigger>
        </TabsList>

        {/* Public Gallery Tab */}
        <TabsContent value="public-gallery" className="space-y-4">
          <PublicGallery
            templates={publicTemplates}
            isLoading={publicTemplatesLoading}
            onExecute={handleExecuteTemplate}
            onView={handleViewTemplateDetails}
            onSchedule={handleScheduleTemplate}
          />
        </TabsContent>

        {/* My Workflows Tab */}
        <TabsContent value="my-workflows" className="space-y-4">
          <MyWorkflows
            workflows={workflows || []}
            isLoading={workflowsLoading}
            onEdit={handleEditWorkflow}
            onExecute={handleExecuteWorkflow}
            onSchedule={handleScheduleWorkflow}
            onSaveAsTemplate={handleSaveAsTemplate}
            onDelete={handleDeleteWorkflow}
            onCreateNew={handleCreateNew}
          />
        </TabsContent>

        {/* My Templates Tab */}
        <TabsContent value="my-templates" className="space-y-4">
          <MyTemplates
            templates={myTemplates}
            isLoading={myTemplatesLoading}
            onExecute={handleExecuteTemplate}
            onView={handleViewTemplateDetails}
            onSchedule={handleScheduleTemplate}
          />
        </TabsContent>

        {/* Schedules Tab */}
        <TabsContent value="schedules" className="space-y-4">
          {schedulesLoading ? (
            <div className="space-y-4">
              {[...Array(4)].map((_, i) => (
                <Card key={i} className="h-24 animate-pulse">
                  <CardHeader>
                    <div className="h-6 bg-muted rounded w-3/4" />
                    <div className="h-4 bg-muted rounded w-1/2 mt-2" />
                  </CardHeader>
                </Card>
              ))}
            </div>
          ) : schedulesData?.jobs && schedulesData.jobs.length > 0 ? (
            <div className="space-y-4">
              {schedulesData.jobs.map((job: any) => (
                <Card key={job.job_id || job.schedule_id}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <CardTitle className="mb-2">{job.name || job.job_id}</CardTitle>
                        <CardDescription>
                          {job.trigger === "cron" && (
                            <span>Cron: {job.cron_expression || "N/A"}</span>
                          )}
                          {job.trigger === "interval" && (
                            <span>Interval: Every {job.interval_seconds}s</span>
                          )}
                        </CardDescription>
                      </div>
                      <Badge variant={job.next_run_time ? "default" : "secondary"}>
                        {job.next_run_time ? "Scheduled" : "Paused"}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <div className="text-muted-foreground">Next Run</div>
                        <div className="font-medium">
                          {job.next_run_time ? new Date(job.next_run_time).toLocaleString() : "Not scheduled"}
                        </div>
                      </div>
                      <div>
                        <div className="text-muted-foreground">Schedule ID</div>
                        <div className="font-mono text-xs truncate">
                          {job.schedule_id || "N/A"}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                  <CardFooter className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        // Extract workflow_id from job_id (format: workflow_{workflow_id}_{schedule_id})
                        const match = job.job_id?.match(/workflow_([a-f0-9-]+)_/);
                        if (match && match[1]) {
                          router.push(`/workflows/${match[1]}`);
                        }
                      }}
                    >
                      View Workflow
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-destructive"
                      onClick={async () => {
                        try {
                          await apiClient.delete(`/workflows/scheduler/jobs/${job.schedule_id}`);
                          toast({
                            title: "Schedule Deleted",
                            description: "The scheduled job has been removed",
                          });
                          // Refresh schedules list
                          window.location.reload();
                        } catch (error) {
                          toast({
                            title: "Error",
                            description: "Failed to delete schedule",
                            variant: "destructive",
                          });
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          ) : (
            <Card className="p-12 text-center">
              <div className="flex flex-col items-center gap-4">
                <div className="rounded-full bg-muted p-4">
                  <Calendar className="h-8 w-8 text-muted-foreground" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold">No scheduled workflows</h3>
                  <p className="text-muted-foreground mt-1">
                    Schedule templates to run automatically
                  </p>
                </div>
              </div>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
