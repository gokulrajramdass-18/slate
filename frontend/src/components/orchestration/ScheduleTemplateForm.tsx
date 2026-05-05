"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Loader2, CalendarIcon, Clock, Info } from "lucide-react";
import { templatesApi, type WorkspaceTemplate } from "@/lib/api/templates";
import { schedulesApi } from "@/lib/api/schedules";
import { ParameterForm } from "@/components/templates/ParameterForm";
import { toast } from "sonner";

interface ScheduleTemplateFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTemplateId?: string;
}

const cronPresets = [
  { value: "0 * * * *", label: "Every hour", description: "At minute 0 of every hour" },
  { value: "0 0 * * *", label: "Daily at midnight", description: "Every day at 00:00" },
  { value: "0 9 * * *", label: "Daily at 9am", description: "Every day at 09:00" },
  { value: "0 0 * * 0", label: "Weekly (Sunday)", description: "Every Sunday at 00:00" },
  { value: "0 0 1 * *", label: "Monthly", description: "First day of month at 00:00" },
  { value: "custom", label: "Custom expression", description: "Enter your own cron" },
];

export function ScheduleTemplateForm({ open, onOpenChange, initialTemplateId }: ScheduleTemplateFormProps) {
  const queryClient = useQueryClient();

  // Form state
  const [templateId, setTemplateId] = useState(initialTemplateId || "");
  const [scheduleType, setScheduleType] = useState<"once" | "recurring">("once");
  const [scheduleName, setScheduleName] = useState("");

  // Once schedule state
  const [onceDate, setOnceDate] = useState("");
  const [onceTime, setOnceTime] = useState("09:00");

  // Recurring schedule state
  const [cronPreset, setCronPreset] = useState("0 9 * * *");
  const [customCron, setCustomCron] = useState("");

  // Parameters state
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [parameterErrors, setParameterErrors] = useState<Record<string, string>>({});

  // Fetch templates
  const { data: templates } = useQuery({
    queryKey: ["templates"],
    queryFn: () => templatesApi.list({ limit: 100 }),
  });

  // Fetch selected template details
  const { data: selectedTemplate, isLoading: isLoadingTemplate } = useQuery({
    queryKey: ["templates", templateId],
    queryFn: () => templatesApi.get(templateId),
    enabled: !!templateId,
  });

  // Create schedule mutation
  const createMutation = useMutation({
    mutationFn: schedulesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      toast.success("Schedule created successfully!");
      handleClose();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to create schedule");
    },
  });

  useEffect(() => {
    if (initialTemplateId) {
      setTemplateId(initialTemplateId);
    }
  }, [initialTemplateId]);

  useEffect(() => {
    if (selectedTemplate) {
      // Auto-generate schedule name
      const suffix = scheduleType === "once" ? "once" : "recurring";
      setScheduleName(`${selectedTemplate.name} - ${suffix}`);

      // Reset parameters
      setParameters({});
      setParameterErrors({});
    }
  }, [selectedTemplate, scheduleType]);

  const handleClose = () => {
    setTemplateId(initialTemplateId || "");
    setScheduleType("once");
    setScheduleName("");
    setOnceDate("");
    setOnceTime("09:00");
    setCronPreset("0 9 * * *");
    setCustomCron("");
    setParameters({});
    setParameterErrors({});
    onOpenChange(false);
  };

  const validateParameters = (): boolean => {
    if (!selectedTemplate?.parameters) return true;

    const errors: Record<string, string> = {};

    for (const param of selectedTemplate.parameters) {
      if (param.required && !parameters[param.name]) {
        errors[param.name] = `${param.name} is required`;
      }

      // Type validation
      const value = parameters[param.name];
      if (value !== undefined && value !== "") {
        if (param.type === "number" && isNaN(Number(value))) {
          errors[param.name] = "Must be a number";
        }
        if (param.type === "date" && isNaN(Date.parse(value))) {
          errors[param.name] = "Must be a valid date";
        }
      }
    }

    setParameterErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = () => {
    if (!validateParameters()) {
      toast.error("Please fix parameter errors");
      return;
    }

    const scheduleConfig: any = {};

    if (scheduleType === "once") {
      if (!onceDate) {
        toast.error("Please select a date");
        return;
      }

      // Combine date and time
      const [hours, minutes] = onceTime.split(":").map(Number);
      const datetime = new Date(onceDate);
      datetime.setHours(hours, minutes, 0, 0);

      scheduleConfig.datetime = datetime.toISOString();
    } else {
      // Recurring
      const cron = cronPreset === "custom" ? customCron : cronPreset;

      if (!cron || cron.trim() === "") {
        toast.error("Please enter a cron expression");
        return;
      }

      scheduleConfig.cron = cron;
    }

    createMutation.mutate({
      template_id: templateId,
      parameters,
      schedule_type: scheduleType,
      schedule_config: scheduleConfig,
      enabled: true,
    } as any);
  };

  const canSubmit = templateId !== "" && scheduleName.trim() !== "" &&
    (scheduleType === "recurring" || (scheduleType === "once" && onceDate));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Schedule Template Execution</DialogTitle>
          <DialogDescription>
            Configure automated execution for a workspace template
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Template Selection */}
          <div className="space-y-2">
            <Label htmlFor="template">Template *</Label>
            <Select value={templateId} onValueChange={setTemplateId}>
              <SelectTrigger id="template">
                <SelectValue placeholder="Select a template" />
              </SelectTrigger>
              <SelectContent>
                {templates?.map((template) => (
                  <SelectItem key={template.id} value={template.id}>
                    {template.name} ({template.phase_count} phases, {template.task_count} tasks)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Template Preview */}
          {isLoadingTemplate ? (
            <div className="flex items-center justify-center py-8 border rounded-lg">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : selectedTemplate ? (
            <div className="border rounded-lg p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-medium">{selectedTemplate.name}</h3>
                  {selectedTemplate.description && (
                    <p className="text-sm text-muted-foreground mt-1">
                      {selectedTemplate.description}
                    </p>
                  )}
                </div>
                {selectedTemplate.category && (
                  <Badge variant="outline">{selectedTemplate.category.replace("_", " ")}</Badge>
                )}
              </div>

              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="space-y-1">
                  <p className="text-xl font-bold text-primary">{selectedTemplate.phase_count}</p>
                  <p className="text-xs text-muted-foreground">Phases</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xl font-bold text-primary">{selectedTemplate.task_count}</p>
                  <p className="text-xs text-muted-foreground">Tasks</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xl font-bold text-primary">{selectedTemplate.parameter_count}</p>
                  <p className="text-xs text-muted-foreground">Parameters</p>
                </div>
              </div>
            </div>
          ) : null}

          {/* Schedule Name */}
          <div className="space-y-2">
            <Label htmlFor="name">Schedule Name *</Label>
            <Input
              id="name"
              value={scheduleName}
              onChange={(e) => setScheduleName(e.target.value)}
              placeholder="e.g., Daily Sales Report - 9am"
            />
          </div>

          {/* Schedule Type Tabs */}
          <Tabs value={scheduleType} onValueChange={(val) => setScheduleType(val as "once" | "recurring")}>
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="once">One-Time</TabsTrigger>
              <TabsTrigger value="recurring">Recurring</TabsTrigger>
            </TabsList>

            {/* One-Time Schedule */}
            <TabsContent value="once" className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="date">Date *</Label>
                  <Input
                    id="date"
                    type="date"
                    value={onceDate}
                    onChange={(e) => setOnceDate(e.target.value)}
                    min={new Date().toISOString().split('T')[0]}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="time">Time *</Label>
                  <Input
                    id="time"
                    type="time"
                    value={onceTime}
                    onChange={(e) => setOnceTime(e.target.value)}
                  />
                </div>
              </div>

              <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <div className="flex gap-2">
                  <Info className="h-5 w-5 text-blue-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-900 dark:text-blue-100">
                    <p className="font-medium mb-1">One-Time Execution</p>
                    <p className="text-blue-800 dark:text-blue-200">
                      Template will be instantiated and executed once at the specified date and time.
                    </p>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* Recurring Schedule */}
            <TabsContent value="recurring" className="space-y-4 mt-4">
              <div className="space-y-2">
                <Label htmlFor="preset">Schedule Frequency</Label>
                <Select value={cronPreset} onValueChange={setCronPreset}>
                  <SelectTrigger id="preset">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {cronPresets.map((preset) => (
                      <SelectItem key={preset.value} value={preset.value}>
                        <div className="flex flex-col">
                          <span className="font-medium">{preset.label}</span>
                          <span className="text-xs text-muted-foreground">{preset.description}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {cronPreset === "custom" && (
                <div className="space-y-2">
                  <Label htmlFor="cron">Cron Expression *</Label>
                  <Input
                    id="cron"
                    value={customCron}
                    onChange={(e) => setCustomCron(e.target.value)}
                    placeholder="0 9 * * *"
                    className="font-mono"
                  />
                  <p className="text-xs text-muted-foreground">
                    Format: minute hour day month weekday (e.g., "0 9 * * *" = daily at 9am)
                  </p>
                </div>
              )}

              <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                <div className="flex gap-2">
                  <Clock className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-amber-900 dark:text-amber-100">
                    <p className="font-medium mb-1">Recurring Execution</p>
                    <p className="text-amber-800 dark:text-amber-200">
                      Template will be instantiated and executed automatically on the specified schedule.
                      {cronPreset !== "custom" && ` Using: ${cronPreset}`}
                    </p>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          {/* Parameters Form */}
          {selectedTemplate && selectedTemplate.parameters && selectedTemplate.parameters.length > 0 && (
            <div className="space-y-2">
              <h3 className="font-medium">Template Parameters</h3>
              <div className="border rounded-lg p-4">
                <ParameterForm
                  parameters={selectedTemplate.parameters}
                  values={parameters}
                  onChange={setParameters}
                  errors={parameterErrors}
                />
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex justify-between sm:justify-between">
          <Button type="button" variant="ghost" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit || createMutation.isPending}
          >
            {createMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Creating...
              </>
            ) : (
              "Create Schedule"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
