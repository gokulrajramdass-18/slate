"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Newspaper, Loader2, Sparkles, Database } from "lucide-react";
import { dailyBriefApi, type DailyBriefConfig } from "@/lib/api/daily-brief";
import { useToast } from "@/hooks/use-toast";
import { SettingsHeader } from "@/components/settings/settings-header";
import { useAuthStore } from "@/lib/stores/auth-store";

const DATA_SOURCES = [
  { id: "executions", label: "Workflow Executions", description: "Show workflow execution stats" },
  { id: "approvals", label: "Pending Approvals", description: "Show approvals needing attention" },
  { id: "schedules", label: "Upcoming Schedules", description: "Show next scheduled runs" },
  { id: "notifications", label: "Notifications", description: "Show notification summary" },
  { id: "orchestrations", label: "Orchestrations", description: "Show orchestration runs" },
];

export default function DailyBriefSettingsPage() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [saved, setSaved] = useState(false);

  // Check admin access
  if (!user?.is_superadmin) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">
          Admin access required to manage daily brief settings
        </p>
      </div>
    );
  }

  // Fetch current settings
  const { data: config, isLoading } = useQuery({
    queryKey: ["daily-brief-settings"],
    queryFn: dailyBriefApi.getSettings,
  });

  // Local state for form
  const [enabled, setEnabled] = useState(true);
  const [aiEnabled, setAiEnabled] = useState(true);
  const [sources, setSources] = useState<string[]>([]);
  const [maxItems, setMaxItems] = useState(5);

  // Update local state when data loads
  useEffect(() => {
    if (config) {
      setEnabled(config.enabled);
      setAiEnabled(config.ai_enabled);
      setSources(config.sources);
      setMaxItems(config.max_items);
    }
  }, [config]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: dailyBriefApi.updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["daily-brief-settings"] });
      queryClient.invalidateQueries({ queryKey: ["daily-brief"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      toast({
        title: "Settings saved",
        description: "Daily brief settings have been updated successfully.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "Failed to save settings",
        description: error?.response?.data?.detail || "An error occurred",
        variant: "destructive",
      });
    },
  });

  const handleSave = () => {
    updateMutation.mutate({
      enabled,
      ai_enabled: aiEnabled,
      sources,
      max_items: maxItems,
    });
  };

  const toggleSource = (sourceId: string) => {
    if (sources.includes(sourceId)) {
      setSources(sources.filter((s) => s !== sourceId));
    } else {
      setSources([...sources, sourceId]);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="Daily Brief Settings"
        description="Configure daily brief feature and AI-powered summaries"
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Newspaper className="w-5 h-5 text-primary-600" />
            Feature Configuration
          </CardTitle>
          <CardDescription>
            Control daily brief feature and behavior for all users
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Enable Feature Toggle */}
          <div className="flex items-start justify-between space-x-4 border-b border-gray-200 dark:border-gray-800 pb-6">
            <div className="flex-1 space-y-1">
              <Label htmlFor="enabled" className="text-base font-medium">
                Enable Daily Brief
              </Label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Show personalized daily brief on dashboard after login
              </p>
            </div>
            <Switch
              id="enabled"
              checked={enabled}
              onCheckedChange={setEnabled}
            />
          </div>

          {/* AI Summaries Toggle */}
          <div className="flex items-start justify-between space-x-4 border-b border-gray-200 dark:border-gray-800 pb-6">
            <div className="flex-1 space-y-1">
              <Label htmlFor="ai-enabled" className="text-base font-medium flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                Enable AI Summaries
              </Label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Generate natural language summaries using AI
              </p>
            </div>
            <Switch
              id="ai-enabled"
              checked={aiEnabled}
              onCheckedChange={setAiEnabled}
              disabled={!enabled}
            />
          </div>

          {/* Data Sources */}
          <div className="space-y-4 border-b border-gray-200 dark:border-gray-800 pb-6">
            <div className="flex items-center gap-2">
              <Database className="w-5 h-5 text-primary-600" />
              <Label className="text-base font-medium">Data Sources</Label>
            </div>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Select which data sources to include in the daily brief
            </p>
            <div className="space-y-3 mt-4">
              {DATA_SOURCES.map((source) => (
                <div key={source.id} className="flex items-start space-x-3">
                  <Checkbox
                    id={source.id}
                    checked={sources.includes(source.id)}
                    onCheckedChange={() => toggleSource(source.id)}
                    disabled={!enabled}
                  />
                  <div className="flex-1">
                    <Label
                      htmlFor={source.id}
                      className="text-sm font-medium cursor-pointer"
                    >
                      {source.label}
                    </Label>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {source.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Max Items */}
          <div className="space-y-3">
            <Label htmlFor="max-items" className="text-base font-medium">
              Maximum Items per Section
            </Label>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
              Limit how many items to display in each section (1-20)
            </p>
            <Input
              id="max-items"
              type="number"
              min={1}
              max={20}
              value={maxItems}
              onChange={(e) => setMaxItems(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
              disabled={!enabled}
              className="w-32"
            />
          </div>

          {/* Save Button */}
          <div className="flex items-center justify-end gap-4 pt-4">
            {saved && (
              <span className="text-sm text-green-600 dark:text-green-400 flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                Saved successfully
              </span>
            )}
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending || saved}
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Settings"
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
