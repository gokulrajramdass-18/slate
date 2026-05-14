"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Loader2, Link2, Settings, CheckCircle, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TagInput } from "@/components/ui/tag-input";
import { SyncSettings } from "./sync-settings";
import { apiConnectionsApi } from "@/lib/api/api-connections";
import { toast } from "sonner";
import type { SyncConfig } from "@/lib/types";
import { Link } from 'react-router-dom';

interface ApiFormProps {
  onSubmit: (data: {
    title: string;
    connection_id: string;
    tags?: string[];
    sync_config?: SyncConfig;
  }) => Promise<void>;
  isLoading?: boolean;
  notebookId?: string;
}

interface FormData {
  title: string;
}

export function ApiForm({ onSubmit, isLoading = false, notebookId }: ApiFormProps) {
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [syncConfig, setSyncConfig] = useState<SyncConfig>({
    enabled: false,
    frequency: "manual",
    status: "idle",
  });

  // Fetch saved API connections
  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ["api-connections"],
    queryFn: apiConnectionsApi.list,
  });

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>();

  // Test connection
  const handleTest = async (connectionId: string) => {
    setTestingId(connectionId);
    setTestResult(null);
    try {
      const result = await apiConnectionsApi.test(connectionId);
      setTestResult(result);
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    } catch (error: any) {
      toast.error(error.message || "Failed to test connection");
      setTestResult({ success: false, message: error.message });
    } finally {
      setTestingId(null);
    }
  };

  const handleFormSubmit = async (data: FormData) => {
    if (!selectedConnectionId) {
      toast.error("Please select a connection");
      return;
    }

    // Get connection details for title
    const connection = connections?.find((c) => c.id === selectedConnectionId);
    const title = data.title || connection?.name || "API Source";

    await onSubmit({
      title,
      connection_id: selectedConnectionId,
      tags: tags,
      sync_config: syncConfig.enabled ? syncConfig : undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-6">
      {/* Connection Selection */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Link2 className="h-5 w-5" />
                API Connection
              </CardTitle>
              <CardDescription>Select a saved API connection</CardDescription>
            </div>
            <Link to="/settings/api-connections">
              <Button type="button" variant="outline" size="sm">
                <Settings className="h-4 w-4 mr-2" />
                Manage Connections
              </Button>
            </Link>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="connection">
              Connection <span className="text-red-500">*</span>
            </Label>
            {connectionsLoading ? (
              <div className="flex items-center gap-2 p-3 border rounded-md">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-gray-500">Loading connections...</span>
              </div>
            ) : connections && connections.length > 0 ? (
              <Select
                value={selectedConnectionId}
                onValueChange={setSelectedConnectionId}
                disabled={isLoading}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select a connection" />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                  {connections.map((conn) => (
                    <SelectItem key={conn.id} value={conn.id}>
                      <div className="flex flex-col">
                        <span className="font-medium">{conn.name}</span>
                        <span className="text-xs text-muted-foreground">
                          {conn.endpoint} · {conn.method} · {conn.auth_type}
                        </span>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : (
              <div className="p-4 border border-dashed rounded-md text-center">
                <p className="text-sm text-gray-500 mb-3">No API connections configured</p>
                <Link to="/settings/api-connections">
                  <Button type="button" variant="outline" size="sm">
                    <Settings className="h-4 w-4 mr-2" />
                    Create Connection
                  </Button>
                </Link>
              </div>
            )}
          </div>

          {/* Test Connection Button */}
          {selectedConnectionId && (
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleTest(selectedConnectionId)}
                disabled={testingId === selectedConnectionId || isLoading}
                className="flex-1"
              >
                {testingId === selectedConnectionId ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Testing Connection...
                  </>
                ) : testResult?.success ? (
                  <>
                    <CheckCircle className="mr-2 h-4 w-4 text-green-600" />
                    Test Connection
                  </>
                ) : testResult?.success === false ? (
                  <>
                    <XCircle className="mr-2 h-4 w-4 text-red-600" />
                    Test Connection
                  </>
                ) : (
                  "Test Connection"
                )}
              </Button>
            </div>
          )}

          {/* Test Result */}
          {testResult && (
            <div
              className={`p-3 rounded-md text-sm ${
                testResult.success
                  ? "bg-green-50 dark:bg-green-950 border border-green-200 dark:border-green-800"
                  : "bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800"
              }`}
            >
              <p className={testResult.success ? "text-green-900 dark:text-green-100" : "text-red-900 dark:text-red-100"}>
                {testResult.message}
              </p>
              {testResult.preview && (
                <details className="mt-2">
                  <summary className="cursor-pointer font-medium">
                    View Preview ({testResult.record_count} records)
                  </summary>
                  <pre className="mt-2 text-xs bg-white dark:bg-gray-900 p-2 rounded overflow-auto max-h-48">
                    {JSON.stringify(testResult.preview, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Connection Details Preview */}
      {selectedConnectionId && connections && (
        <Card>
          <CardHeader>
            <CardTitle>Connection Details</CardTitle>
          </CardHeader>
          <CardContent>
            {(() => {
              const conn = connections.find((c) => c.id === selectedConnectionId);
              if (!conn) return null;
              return (
                <div className="space-y-2 text-sm">
                  <div className="grid grid-cols-2 gap-2">
                    <span className="text-gray-500">Endpoint:</span>
                    <span className="font-mono text-xs">{conn.endpoint}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <span className="text-gray-500">Method:</span>
                    <span>{conn.method}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <span className="text-gray-500">Authentication:</span>
                    <span className="capitalize">{conn.auth_type}</span>
                  </div>
                  {conn.data_path && (
                    <div className="grid grid-cols-2 gap-2">
                      <span className="text-gray-500">Data Path:</span>
                      <span className="font-mono text-xs">{conn.data_path}</span>
                    </div>
                  )}
                  {conn.content_fields.length > 0 && (
                    <div className="grid grid-cols-2 gap-2">
                      <span className="text-gray-500">Content Fields:</span>
                      <span className="font-mono text-xs">{conn.content_fields.join(", ")}</span>
                    </div>
                  )}
                </div>
              );
            })()}
          </CardContent>
        </Card>
      )}

      {/* Source Details */}
      <Card>
        <CardHeader>
          <CardTitle>Source Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title (optional)</Label>
            <Input
              id="title"
              placeholder="Auto-generated from connection name"
              {...register("title")}
              disabled={isLoading}
            />
          </div>

          <TagInput
            label="Tags (optional)"
            value={tags}
            onChange={setTags}
            placeholder="Type and press Enter to add tags"
            disabled={isLoading}
          />
        </CardContent>
      </Card>

      {/* Sync Settings */}
      <SyncSettings config={syncConfig} onChange={setSyncConfig} />

      {/* Submit */}
      <div className="flex justify-end gap-3">
        <Button type="submit" disabled={!selectedConnectionId || isLoading}>
          {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Add API Source
        </Button>
      </div>
    </form>
  );
}
