"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Workflow, Play, Copy, Eye, TrendingUp, Users, Calendar, Tag, Clock, ChevronDown } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/stores/auth-store";

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
}

interface WorkflowNode {
  id: string;
  type: string;
  label: string;
  config: any;
  position: { x: number; y: number };
}

interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  entry_node_id: string;
}

interface WorkflowTemplateDetail extends WorkflowTemplate {
  graph_json: string;
  graph?: WorkflowGraph;
  parameters: TemplateParameter[];
}

export default function WorkflowTemplatesPage() {
  const { toast } = useToast();
  const router = useRouter();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const userId = user?.id || user?.username || "test-user";
  const [activeTab, setActiveTab] = useState("public");
  const [selectedTemplate, setSelectedTemplate] = useState<WorkflowTemplateDetail | null>(null);
  const [parameterValues, setParameterValues] = useState<Record<string, any>>({});
  const [showExecuteDialog, setShowExecuteDialog] = useState(false);
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [showViewDialog, setShowViewDialog] = useState(false);
  const [scheduleType, setScheduleType] = useState<"daily" | "weekly" | "monthly" | "custom">("daily");
  const [scheduleTime, setScheduleTime] = useState("09:00");
  const [scheduleDayOfWeek, setScheduleDayOfWeek] = useState("monday");
  const [scheduleDayOfMonth, setScheduleDayOfMonth] = useState("1");
  const [customCron, setCustomCron] = useState("0 9 * * *");

  const handleScheduleClick = (type: "daily" | "weekly" | "monthly" | "custom") => {
    setShowViewDialog(false); // Close the view dialog first
    setScheduleType(type);
    setTimeout(() => setShowScheduleDialog(true), 100); // Open schedule dialog after view dialog closes
  };

  // Fetch templates
  const { data: templates = [], isLoading } = useQuery<WorkflowTemplate[]>({
    queryKey: ["workflow-templates", activeTab, userId],
    queryFn: async () => {
      const endpoint = activeTab === "public"
        ? "/api/workflow-templates/public"
        : "/api/workflow-templates";

      const headers: Record<string, string> = {
        "X-User-ID": userId
      };

      const response = await fetch(endpoint, { headers });
      if (!response.ok) throw new Error("Failed to fetch templates");
      return response.json();
    },
  });

  // Fetch template details
  const fetchTemplateDetails = async (templateId: string) => {
    const response = await fetch(`/api/workflow-templates/${templateId}`, {
      headers: { "X-User-ID": userId }
    });
    if (!response.ok) throw new Error("Failed to fetch template details");
    return response.json();
  };

  // Instantiate template mutation
  const instantiateMutation = useMutation({
    mutationFn: async ({ templateId, parameters }: { templateId: string; parameters: Record<string, any> }) => {
      const response = await fetch(`/api/workflow-templates/${templateId}/instantiate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId
        },
        body: JSON.stringify({ parameters })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to instantiate template");
      }
      
      return response.json();
    },
    onSuccess: (data) => {
      toast({
        title: "Success",
        description: "Workflow created from template",
      });
      router.push(`/workflows/${data.workflow_id}`);
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Execute template mutation
  const executeMutation = useMutation({
    mutationFn: async ({ templateId, parameters }: { templateId: string; parameters: Record<string, any> }) => {
      const response = await fetch(`/api/workflow-templates/${templateId}/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": userId
        },
        body: JSON.stringify({ parameters, input_data: {} })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to execute template");
      }
      
      return response.json();
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

  const handleViewDetails = async (template: WorkflowTemplate) => {
    try {
      const details = await fetchTemplateDetails(template.id);

      // Parse graph JSON
      try {
        details.graph = JSON.parse(details.graph_json);
      } catch (e) {
        console.error("Failed to parse graph JSON:", e);
      }

      setSelectedTemplate(details);

      // Initialize parameter values with defaults
      const defaults: Record<string, any> = {};
      details.parameters.forEach((param: TemplateParameter) => {
        if (param.default_value !== undefined) {
          defaults[param.name] = param.default_value;
        }
      });
      setParameterValues(defaults);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to load template details",
        variant: "destructive",
      });
    }
  };

  const handleInstantiate = () => {
    if (!selectedTemplate) return;
    instantiateMutation.mutate({
      templateId: selectedTemplate.id,
      parameters: parameterValues
    });
  };

  const handleExecute = () => {
    if (!selectedTemplate) return;
    executeMutation.mutate({
      templateId: selectedTemplate.id,
      parameters: parameterValues
    });
    setShowExecuteDialog(false);
  };

  const handleScheduleCreate = async () => {
    if (!selectedTemplate) return;

    try {
      // Step 1: Instantiate the template to create a workflow
      const instantiateResponse = await fetch("/api/workflow-templates/instantiate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          template_id: selectedTemplate.id,
          parameters: parameterValues,
        }),
      });

      if (!instantiateResponse.ok) {
        throw new Error("Failed to create workflow from template");
      }

      const { workflow } = await instantiateResponse.json();

      // Step 2: Build cron expression based on schedule type
      let cronExpression = customCron;
      if (scheduleType !== "custom") {
        const [hours, minutes] = scheduleTime.split(":");

        if (scheduleType === "daily") {
          cronExpression = `${minutes} ${hours} * * *`;
        } else if (scheduleType === "weekly") {
          const dayMap: Record<string, string> = {
            sunday: "0", monday: "1", tuesday: "2", wednesday: "3",
            thursday: "4", friday: "5", saturday: "6"
          };
          cronExpression = `${minutes} ${hours} * * ${dayMap[scheduleDayOfWeek]}`;
        } else if (scheduleType === "monthly") {
          cronExpression = `${minutes} ${hours} ${scheduleDayOfMonth} * *`;
        }
      }

      // Step 3: Create the schedule
      const scheduleResponse = await fetch(`/api/workflows/${workflow.id}/schedules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schedule_type: "cron",
          cron_expression: cronExpression,
          is_enabled: true,
        }),
      });

      if (!scheduleResponse.ok) {
        throw new Error("Failed to create schedule");
      }

      toast({
        title: "Schedule Created",
        description: `Workflow "${workflow.name}" will run ${scheduleType}`,
      });

      setShowScheduleDialog(false);
      queryClient.invalidateQueries({ queryKey: ["workflow-templates"] });
    } catch (error) {
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to create schedule",
        variant: "destructive",
      });
    }
  };

  const renderParameterInput = (param: TemplateParameter) => {
    const value = parameterValues[param.name] ?? param.default_value ?? "";
    
    const handleChange = (newValue: any) => {
      setParameterValues(prev => ({ ...prev, [param.name]: newValue }));
    };

    switch (param.type) {
      case "select":
        return (
          <Select value={value} onValueChange={handleChange}>
            <SelectTrigger>
              <SelectValue placeholder="Select an option" />
            </SelectTrigger>
            <SelectContent>
              {param.options?.map(option => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      
      case "boolean":
        return (
          <Select value={value.toString()} onValueChange={(v) => handleChange(v === "true")}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="true">True</SelectItem>
              <SelectItem value="false">False</SelectItem>
            </SelectContent>
          </Select>
        );
      
      case "number":
        return (
          <Input
            type="number"
            value={value}
            onChange={(e) => handleChange(Number(e.target.value))}
          />
        );
      
      default:
        return (
          <Input
            type="text"
            value={value}
            onChange={(e) => handleChange(e.target.value)}
          />
        );
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Workflow Templates</h1>
          <p className="text-muted-foreground mt-2 text-base">Browse and use reusable workflow templates</p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="public">Public Gallery</TabsTrigger>
          <TabsTrigger value="my-templates">My Templates</TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="space-y-4 mt-6">
          {isLoading ? (
            <Card>
              <CardContent className="p-6">
                <p className="text-center text-muted-foreground">Loading templates...</p>
              </CardContent>
            </Card>
          ) : templates.length === 0 ? (
            <Card>
              <CardContent className="p-6">
                <p className="text-center text-muted-foreground">No templates found</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templates.map((template) => (
                <Card key={template.id} className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <Workflow className="h-8 w-8 text-primary" />
                      {template.is_public && (
                        <Badge variant="secondary">Public</Badge>
                      )}
                    </div>
                    <CardTitle className="mt-2">{template.name}</CardTitle>
                    <CardDescription className="line-clamp-2">
                      {template.description || "No description"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {/* Category */}
                    {template.category && (
                      <Badge variant="outline" className="flex items-center gap-1 w-fit">
                        <Tag className="h-3 w-3" />
                        {template.category}
                      </Badge>
                    )}

                    {/* Stats */}
                    <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Workflow className="h-3 w-3" />
                        {template.node_count} nodes
                      </span>
                      <span className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        {template.usage_count} uses
                      </span>
                    </div>

                    {/* Tags */}
                    {template.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {template.tags.slice(0, 3).map(tag => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                        {template.tags.length > 3 && (
                          <Badge variant="secondary" className="text-xs">
                            +{template.tags.length - 3}
                          </Badge>
                        )}
                      </div>
                    )}
                  </CardContent>
                  <CardFooter className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1"
                      onClick={() => { handleViewDetails(template); setShowViewDialog(true); }}
                    >
                      <Eye className="h-4 w-4 mr-2" />
                      View
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* View Template Dialog - Outside the map loop */}
      <Dialog open={showViewDialog} onOpenChange={setShowViewDialog}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle>{selectedTemplate?.name}</DialogTitle>
                          <DialogDescription>
                            {selectedTemplate?.description}
                          </DialogDescription>
                        </DialogHeader>

                        {selectedTemplate && (
                          <div className="space-y-6">
                            {/* Template info */}
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <strong>Nodes:</strong> {selectedTemplate.node_count}
                              </div>
                              <div>
                                <strong>Edges:</strong> {selectedTemplate.edge_count}
                              </div>
                              <div>
                                <strong>Category:</strong> {selectedTemplate.category || "None"}
                              </div>
                              <div>
                                <strong>Usage:</strong> {selectedTemplate.usage_count} times
                              </div>
                            </div>

                            {/* Node List */}
                            {selectedTemplate.graph && (
                              <div className="space-y-3">
                                <h3 className="font-semibold">Workflow Nodes</h3>
                                <div className="space-y-2">
                                  {selectedTemplate.graph.nodes.map((node) => (
                                    <div
                                      key={node.id}
                                      className="flex items-center gap-3 p-3 border rounded-lg bg-muted/30"
                                    >
                                      <div className="flex items-center justify-center w-8 h-8 rounded bg-primary/10">
                                        <Workflow className="h-4 w-4 text-primary" />
                                      </div>
                                      <div className="flex-1">
                                        <div className="font-medium">{node.label}</div>
                                        <div className="text-xs text-muted-foreground">
                                          Type: {node.type}
                                        </div>
                                      </div>
                                      {node.id === selectedTemplate.graph?.entry_node_id && (
                                        <Badge variant="secondary" className="text-xs">
                                          Start
                                        </Badge>
                                      )}
                                    </div>
                                  ))}
                                </div>

                                {/* Simple visual diagram */}
                                <div className="p-4 border rounded-lg bg-muted/30">
                                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    {selectedTemplate.graph.nodes.map((node, idx) => (
                                      <div key={node.id} className="flex items-center">
                                        <Badge variant="outline" className="text-xs">
                                          {node.label}
                                        </Badge>
                                        {idx < selectedTemplate.graph!.nodes.length - 1 && (
                                          <span className="mx-2">→</span>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Input Node Schema */}
                            {selectedTemplate.graph && (
                              (() => {
                                const inputNode = selectedTemplate.graph.nodes.find(
                                  n => n.id === selectedTemplate.graph?.entry_node_id
                                );
                                if (inputNode && inputNode.config?.input_fields) {
                                  return (
                                    <div className="space-y-3">
                                      <h3 className="font-semibold">Input Fields</h3>
                                      <div className="space-y-2">
                                        {inputNode.config.input_fields.map((field: any) => (
                                          <div key={field.name} className="p-3 border rounded-lg">
                                            <div className="font-medium">
                                              {field.name}
                                              {field.required && (
                                                <span className="text-red-500 ml-1">*</span>
                                              )}
                                            </div>
                                            <div className="text-xs text-muted-foreground mt-1">
                                              Type: {field.type}
                                              {field.description && ` - ${field.description}`}
                                            </div>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  );
                                }
                                return null;
                              })()
                            )}

                            {/* Parameters */}
                            {selectedTemplate.parameters.length > 0 && (
                              <div className="space-y-4">
                                <h3 className="font-semibold">Parameters</h3>
                                {selectedTemplate.parameters.map((param) => (
                                  <div key={param.name} className="space-y-2">
                                    <Label>
                                      {param.name}
                                      {param.required && <span className="text-red-500 ml-1">*</span>}
                                    </Label>
                                    {param.description && (
                                      <p className="text-xs text-muted-foreground">{param.description}</p>
                                    )}
                                    {renderParameterInput(param)}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        <DialogFooter className="gap-2">
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button disabled={executeMutation.isPending}>
                                <Play className="h-4 w-4 mr-2" />
                                Execute Workflow
                                <ChevronDown className="h-4 w-4 ml-2" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem onClick={() => setShowExecuteDialog(true)}>
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
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>

      {/* Execute confirmation dialog */}
      <Dialog open={showExecuteDialog} onOpenChange={setShowExecuteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Execute Template</DialogTitle>
            <DialogDescription>
              This will create a new workflow and execute it immediately.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowExecuteDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleExecute} disabled={executeMutation.isPending}>
              <Play className="h-4 w-4 mr-2" />
              Execute
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Schedule dialog */}
      <Dialog open={showScheduleDialog} onOpenChange={setShowScheduleDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Schedule Workflow Execution</DialogTitle>
            <DialogDescription>
              Configure when this workflow should run
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Schedule Type Info */}
            <div className="p-3 bg-muted rounded-lg">
              <div className="font-medium capitalize">{scheduleType} Execution</div>
              <div className="text-sm text-muted-foreground mt-1">
                {scheduleType === "daily" && "Runs every day at the specified time"}
                {scheduleType === "weekly" && "Runs once per week on the specified day"}
                {scheduleType === "monthly" && "Runs once per month on the specified date"}
                {scheduleType === "custom" && "Define your own schedule using cron expression"}
              </div>
            </div>

            {scheduleType !== "custom" ? (
              <>
                {/* Time picker */}
                <div className="space-y-2">
                  <Label htmlFor="time">Execution Time</Label>
                  <Input
                    id="time"
                    type="time"
                    value={scheduleTime}
                    onChange={(e) => setScheduleTime(e.target.value)}
                  />
                </div>

                {/* Day of week picker (for weekly) */}
                {scheduleType === "weekly" && (
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
                )}

                {/* Day of month picker (for monthly) */}
                {scheduleType === "monthly" && (
                  <div className="space-y-2">
                    <Label htmlFor="day-of-month">Day of Month</Label>
                    <Select value={scheduleDayOfMonth} onValueChange={setScheduleDayOfMonth}>
                      <SelectTrigger id="day-of-month">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Array.from({ length: 28 }, (_, i) => i + 1).map(day => (
                          <SelectItem key={day} value={day.toString()}>
                            {day}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </>
            ) : (
              /* Custom cron expression */
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
                  Examples: "0 9 * * *" (daily at 9am), "0 9 * * 1" (Monday at 9am), "*/15 * * * *" (every 15 min)
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowScheduleDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleScheduleCreate}>
              <Calendar className="h-4 w-4 mr-2" />
              Create Schedule
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
