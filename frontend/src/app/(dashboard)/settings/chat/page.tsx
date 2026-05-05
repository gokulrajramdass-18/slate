"use client";

import { useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { MessageSquare, Loader2, CheckCircle2 } from "lucide-react";
import { chatSettingsApi, type ChatPreferences } from "@/lib/api/chat-settings";
import { useToast } from "@/hooks/use-toast";
import { SettingsHeader } from "@/components/settings/settings-header";

export default function ChatSettingsPage() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [saved, setSaved] = useState(false);

  // Fetch current preferences
  const { data: preferences, isLoading } = useQuery({
    queryKey: ["chat-settings"],
    queryFn: chatSettingsApi.get,
  });

  // Local state for form
  const [enableGenerativeUI, setEnableGenerativeUI] = useState(false);
  const [streamResponses, setStreamResponses] = useState(true);
  const [includeContextByDefault, setIncludeContextByDefault] = useState(true);

  // Update local state when data loads
  useEffect(() => {
    if (preferences) {
      setEnableGenerativeUI(preferences.enable_generative_ui);
      setStreamResponses(preferences.stream_responses);
      setIncludeContextByDefault(preferences.include_context_by_default);
    }
  }, [preferences]);

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: chatSettingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-settings"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      toast({
        title: "Settings saved",
        description: "Chat preferences have been updated successfully.",
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
      enable_generative_ui: enableGenerativeUI,
      stream_responses: streamResponses,
      include_context_by_default: includeContextByDefault,
    });
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
        title="Chat Settings"
        description="Configure chat preferences and behavior"
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-primary-600" />
            Chat Preferences
          </CardTitle>
          <CardDescription>
            Control how chat responses are displayed and processed
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Generative UI Toggle */}
          <div className="flex items-start justify-between space-x-4 border-b border-gray-200 dark:border-gray-800 pb-6">
            <div className="flex-1 space-y-1">
              <Label htmlFor="generative-ui" className="text-base font-medium">
                Enable Generative UI
              </Label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Automatically render interactive components (data tables, charts, metrics)
                from tool execution results. When disabled, all responses are plain text.
              </p>
              <div className="pt-2">
                <div className="space-y-1 text-xs text-gray-500">
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-600" />
                    <span>HANA query results → Sortable data tables</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-600" />
                    <span>COUNT queries → Metric cards with KPIs</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-600" />
                    <span>API responses → Interactive JSON viewers</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-primary-600" />
                    <span>Time-series data → Line charts</span>
                  </div>
                </div>
              </div>
            </div>
            <Switch
              id="generative-ui"
              checked={enableGenerativeUI}
              onCheckedChange={setEnableGenerativeUI}
            />
          </div>

          {/* Stream Responses Toggle */}
          <div className="flex items-start justify-between space-x-4 border-b border-gray-200 dark:border-gray-800 pb-6">
            <div className="flex-1 space-y-1">
              <Label htmlFor="stream-responses" className="text-base font-medium">
                Stream Responses
              </Label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Display AI responses as they are generated in real-time. Provides faster
                feedback but may not be suitable for slow connections.
              </p>
            </div>
            <Switch
              id="stream-responses"
              checked={streamResponses}
              onCheckedChange={setStreamResponses}
            />
          </div>

          {/* Include Context Toggle */}
          <div className="flex items-start justify-between space-x-4">
            <div className="flex-1 space-y-1">
              <Label htmlFor="include-context" className="text-base font-medium">
                Include Context by Default
              </Label>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Automatically include relevant content from notebook sources in chat context.
                Improves answer quality but may use more tokens.
              </p>
            </div>
            <Switch
              id="include-context"
              checked={includeContextByDefault}
              onCheckedChange={setIncludeContextByDefault}
            />
          </div>

          {/* Save Button */}
          <div className="pt-4 flex items-center gap-3">
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending}
              className="min-w-[120px]"
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : saved ? (
                <>
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  Saved
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
            {saved && (
              <span className="text-sm text-green-600 dark:text-green-400">
                Settings updated successfully
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Info Card */}
      <Card className="border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30">
        <CardHeader>
          <CardTitle className="text-base">About Generative UI</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
          <p>
            Generative UI transforms your chat experience by automatically rendering
            structured data as interactive components instead of plain text.
          </p>
          <p>
            When enabled, AI agents analyze tool execution results (HANA queries, API calls)
            and generate the most appropriate visualization: data tables for tabular results,
            metric cards for counts/sums, JSON viewers for complex data, and charts for time-series.
          </p>
          <p className="font-medium text-gray-700 dark:text-gray-300">
            Requirements: Your notebook must have HANA tables or authenticated APIs configured as sources.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
