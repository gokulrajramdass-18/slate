"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, use } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ArrowLeft,
  Play,
  Calendar,
  Trash2,
  Loader2,
  Globe,
  Lock,
  TrendingUp,
  Users,
  ListChecks,
  Settings2,
  Database,
  FileSearch,
  FileText,
  BarChart3,
  Bell,
  Workflow,
} from "lucide-react";
import { templatesApi, type WorkspaceTemplate } from "@/lib/api/templates";
import { workspacesApi } from "@/lib/api/workspaces";
import { TemplateExecutionHistory } from "@/components/templates/TemplateExecutionHistory";
import { TemplateExecutionDialog } from "@/components/templates/TemplateExecutionDialog";
import { toast } from "sonner";
import Link from "next/link";

interface TemplateDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

const categoryIcons: Record<string, React.ElementType> = {
  data_pipeline: Database,
  research: FileSearch,
  reporting: FileText,
  monitoring: Bell,
  analysis: BarChart3,
  automation: Workflow,
  other: Workflow,
};

const categoryColors: Record<string, string> = {
  data_pipeline: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  research: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  reporting: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  monitoring: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  analysis: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300",
  automation: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300",
  other: "bg-gray-100 text-gray-700 dark:bg-gray-900 dark:text-gray-300",
};

export default function TemplateDetailPage({ params }: TemplateDetailPageProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [instantiateDialogOpen, setInstantiateDialogOpen] = useState(false);
  const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);

  // Unwrap the async params
  const { id } = use(params);

  const { data: template, isLoading, isError, error } = useQuery({
    queryKey: ["templates", id],
    queryFn: () => templatesApi.get(id),
  });

  // Fetch source workspace
  const { data: sourceWorkspace } = useQuery({
    queryKey: ["workspaces", template?.source_workspace_id],
    queryFn: () => template?.source_workspace_id ? workspacesApi.get(template.source_workspace_id) : null,
    enabled: !!template?.source_workspace_id,
  });

  // Fetch execution history to check for running executions
  const { data: executions } = useQuery({
    queryKey: ["templates", id, "executions"],
    queryFn: () => templatesApi.getExecutions(id),
    refetchInterval: (data) => {
      // Poll every 3 seconds if there's a running execution
      const hasRunning = Array.isArray(data) && data.some((e: any) => e.status === "running");
      return hasRunning ? 3000 : false;
    },
  });

  // Check if there's a running execution
  const hasRunningExecution = Array.isArray(executions) && executions.some((e: any) => e.status === "running");

  const deleteMutation = useMutation({
    mutationFn: () => templatesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["templates"] });
      toast.success("Template deleted successfully");
      router.push("/templates");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to delete template");
    },
  });

  const handleInstantiate = () => {
    setInstantiateDialogOpen(true);
  };

  const handleSchedule = () => {
    toast.info("Opening schedule dialog...");
    // TODO: Open ScheduleTemplateForm
  };

  if (isLoading) {
    return (
      <div className="p-6 h-full overflow-auto">
        <div className="space-y-8 max-w-7xl mx-auto">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 h-full overflow-auto">
        <div className="space-y-8 max-w-7xl mx-auto">
          <div className="text-center py-12">
            <p className="text-muted-foreground">
              {(error as any)?.response?.data?.detail || "Failed to load template"}
            </p>
            <Link href="/templates">
              <Button variant="outline" className="mt-4">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Templates
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (!template) {
    return (
      <div className="p-6 h-full overflow-auto">
        <div className="space-y-8 max-w-7xl mx-auto">
          <div className="text-center py-12">
            <p className="text-muted-foreground">Template not found</p>
            <Link href="/templates">
              <Button variant="link" className="mt-4">
                Back to Templates
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const CategoryIcon = categoryIcons[template.category || "other"] || Workflow;
  const categoryColor = categoryColors[template.category || "other"];

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-in-up">
        <div className="flex items-center gap-4">
          <Link href="/templates">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
              {template.name}
            </h1>
            {template.description && (
              <p className="text-muted-foreground mt-2 text-base">{template.description}</p>
            )}
            <div className="flex items-center gap-2 mt-2">
              <div className={`p-1.5 rounded-lg ${categoryColor}`}>
                <CategoryIcon className="h-4 w-4" />
              </div>
              {template.is_public ? (
                <Globe className="h-4 w-4 text-blue-500" />
              ) : (
                <Lock className="h-4 w-4 text-gray-400" />
              )}
            </div>
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={handleInstantiate}
            disabled={hasRunningExecution}
          >
            {hasRunningExecution ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Executing...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Run Now
              </>
            )}
          </Button>
          <Button onClick={handleSchedule} variant="outline">
            <Calendar className="h-4 w-4 mr-2" />
            Schedule
          </Button>
          <Button
            variant="destructive"
            onClick={() => setDeleteDialogOpen(true)}
            disabled={deleteMutation.isPending}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Phases</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <ListChecks className="h-5 w-5 text-primary" />
              <p className="text-3xl font-bold">{template.phase_count}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Tasks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              <p className="text-3xl font-bold">{template.task_count}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Parameters</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-primary" />
              <p className="text-3xl font-bold">{template.parameter_count}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardDescription>Usage Count</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              <p className="text-3xl font-bold">{template.usage_count}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tags and Category */}
      <Card>
        <CardHeader>
          <CardTitle>Metadata</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {sourceWorkspace && (
            <div>
              <p className="text-sm font-medium mb-2">Source Workspace</p>
              <Link href={`/workspaces/${sourceWorkspace.id}`}>
                <Badge variant="outline" className="hover:bg-accent cursor-pointer">
                  <Workflow className="h-3 w-3 mr-1" />
                  {sourceWorkspace.name}
                </Badge>
              </Link>
            </div>
          )}

          {template.category && (
            <div>
              <p className="text-sm font-medium mb-2">Category</p>
              <Badge variant="outline" className={categoryColor}>
                {template.category.replace("_", " ")}
              </Badge>
            </div>
          )}

          {template.tags && template.tags.length > 0 && (
            <div>
              <p className="text-sm font-medium mb-2">Tags</p>
              <div className="flex flex-wrap gap-2">
                {template.tags.map((tag) => (
                  <Badge key={tag} variant="secondary">
                    {tag}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4 pt-4 border-t text-sm">
            <div>
              <p className="text-muted-foreground">Created</p>
              <p className="font-medium">{new Date(template.created_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Last Updated</p>
              <p className="font-medium">{new Date(template.updated_at).toLocaleString()}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Version</p>
              <p className="font-medium">v{template.version}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Visibility</p>
              <p className="font-medium">{template.is_public ? "Public" : "Private"}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="structure">
        <TabsList>
          <TabsTrigger value="structure">Structure</TabsTrigger>
          <TabsTrigger value="parameters">Parameters</TabsTrigger>
          <TabsTrigger value="history">Execution History</TabsTrigger>
        </TabsList>

        <TabsContent value="structure" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Template Structure</CardTitle>
              <CardDescription>Phases and tasks defined in this template</CardDescription>
            </CardHeader>
            <CardContent>
              {template.phases && template.phases.length > 0 ? (
                <div className="space-y-4">
                  {template.phases.map((phase: any, phaseIndex: number) => (
                    <div key={phaseIndex} className="border rounded-lg p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Badge variant="outline">Phase {phaseIndex + 1}</Badge>
                        <h3 className="font-medium">{phase.name}</h3>
                      </div>

                      {phase.description && (
                        <p className="text-sm text-muted-foreground mb-3">{phase.description}</p>
                      )}

                      {phase.tasks && phase.tasks.length > 0 && (
                        <div className="space-y-2 ml-4">
                          {phase.tasks.map((task: any, taskIndex: number) => (
                            <div
                              key={taskIndex}
                              className="flex items-start gap-3 p-3 bg-muted/50 rounded border"
                            >
                              <Badge variant="secondary" className="mt-0.5">
                                {taskIndex + 1}
                              </Badge>
                              <div className="flex-1">
                                <p className="font-medium text-sm">{task.name || task.title}</p>
                                {task.description && (
                                  <p className="text-sm text-muted-foreground mt-1">{task.description}</p>
                                )}
                                {task.agent_assignment && (
                                  <p className="text-xs text-muted-foreground mt-2">
                                    Agent: {task.agent_assignment}
                                  </p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">No structure defined</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="parameters" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Template Parameters</CardTitle>
              <CardDescription>Variables that can be customized on execution</CardDescription>
            </CardHeader>
            <CardContent>
              {template.parameters && template.parameters.length > 0 ? (
                <div className="space-y-4">
                  {template.parameters.map((param: any, index: number) => (
                    <div key={index} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <h3 className="font-medium">{param.name}</h3>
                          {param.required && (
                            <Badge variant="destructive" className="text-xs">
                              Required
                            </Badge>
                          )}
                        </div>
                        <Badge variant="outline">{param.type}</Badge>
                      </div>

                      {param.description && (
                        <p className="text-sm text-muted-foreground mb-2">{param.description}</p>
                      )}

                      {param.default_value && (
                        <div className="text-sm">
                          <span className="text-muted-foreground">Default: </span>
                          <code className="bg-muted px-2 py-0.5 rounded font-mono text-xs">
                            {String(param.default_value)}
                          </code>
                        </div>
                      )}

                      {param.options && param.options.length > 0 && (
                        <div className="mt-2">
                          <p className="text-sm text-muted-foreground mb-1">Options:</p>
                          <div className="flex flex-wrap gap-1">
                            {param.options.map((option: string) => (
                              <Badge key={option} variant="secondary" className="text-xs">
                                {option}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-8">No parameters defined</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="mt-6">
          <TemplateExecutionHistory templateId={id} />
        </TabsContent>
      </Tabs>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Template</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this template? This action cannot be undone.
              All schedules using this template will be affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteMutation.mutate()}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Instantiate Dialog */}
      {template && (
        <TemplateExecutionDialog
          open={instantiateDialogOpen}
          onOpenChange={setInstantiateDialogOpen}
          templateId={id}
          templateName={template.name}
          sourceWorkspaceId={(template as any).source_workspace_id}
          parameters={template.parameters || []}
        />
      )}
      </div>
    </div>
  );
}
