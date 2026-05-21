"use client";

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, ExternalLink, Globe } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface APINodePropertyPanelProps {
  selectedNode: any;
  handleUpdate: (key: string, value: any) => void;
}

export function APINodePropertyPanel({ selectedNode, handleUpdate }: APINodePropertyPanelProps) {
  const [selectedConnection, setSelectedConnection] = useState(selectedNode.data.config.api_connection_id || "");

  // Sync local state with node config when node changes
  useEffect(() => {
    setSelectedConnection(selectedNode.data.config.api_connection_id || "");
  }, [selectedNode.id]);

  // Fetch API connections
  const { data: connections = [], isLoading: connectionsLoading } = useQuery({
    queryKey: ["api-connections"],
    queryFn: async () => {
      const response = await apiClient.get("/api-connections");
      return response.data;
    },
  });

  // Fetch selected connection details
  const { data: connectionDetails, isLoading: detailsLoading } = useQuery({
    queryKey: ["api-connection", selectedConnection],
    queryFn: async () => {
      if (!selectedConnection) return null;
      const response = await apiClient.get(`/api-connections/${selectedConnection}`);
      return response.data;
    },
    enabled: !!selectedConnection,
  });

  // Update node configuration when connection changes
  useEffect(() => {
    const nodeConnection = selectedNode.data.config.api_connection_id || "";
    if (selectedConnection && selectedConnection !== nodeConnection) {
      handleUpdate("api_connection_id", selectedConnection);
    }
  }, [selectedConnection, selectedNode.data.config.api_connection_id, handleUpdate]);

  return (
    <div className="space-y-4">
      {/* API Connection Selector */}
      <div className="space-y-2">
        <Label>API Connection *</Label>
        {connectionsLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading connections...
          </div>
        ) : connections.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            No API connections found.{" "}
            <a
              href="/settings/api-connections"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline inline-flex items-center gap-1"
            >
              Create one in Settings
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        ) : (
          <Select value={selectedConnection} onValueChange={setSelectedConnection}>
            <SelectTrigger>
              <SelectValue placeholder="Select API connection" />
            </SelectTrigger>
            <SelectContent>
              {connections.map((conn: any) => (
                <SelectItem key={conn.id} value={conn.id}>
                  <div className="flex items-center gap-2">
                    <Globe className="h-3 w-3" />
                    {conn.name}
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {/* Connection Details */}
      {selectedConnection && connectionDetails && (
        <>
          <div className="rounded-lg border bg-muted/50 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Connection Details</span>
              <Badge variant="outline" className="text-xs">
                {connectionDetails.method}
              </Badge>
            </div>

            <div className="space-y-1">
              <div className="text-xs">
                <span className="text-muted-foreground">Base Endpoint:</span>
                <div className="font-mono text-xs break-all mt-0.5 text-foreground">
                  {connectionDetails.endpoint}
                </div>
              </div>

              {connectionDetails.data_path && (
                <div className="text-xs">
                  <span className="text-muted-foreground">Data Path:</span>
                  <div className="font-mono text-xs mt-0.5 text-foreground">
                    {connectionDetails.data_path}
                  </div>
                </div>
              )}

              {connectionDetails.auth_type !== "none" && (
                <div className="text-xs">
                  <span className="text-muted-foreground">Auth:</span>
                  <span className="ml-1 font-medium capitalize">{connectionDetails.auth_type}</span>
                </div>
              )}
            </div>
          </div>

          {/* API Path Override */}
          <div className="space-y-2">
            <Label htmlFor="api-path">API Path (optional)</Label>
            <Input
              id="api-path"
              value={selectedNode.data.config.api_path || ''}
              onChange={(e) => handleUpdate('api_path', e.target.value)}
              placeholder="/users/123 or /todos"
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Path to append to the base endpoint. Leave empty to use the connection's default endpoint.
            </p>
            {selectedNode.data.config.api_path && (
              <div className="text-xs bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded p-2">
                <span className="text-muted-foreground">Full URL:</span>
                <div className="font-mono text-xs mt-1 break-all text-foreground">
                  {connectionDetails.endpoint}{selectedNode.data.config.api_path}
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Snapshot Configuration */}
      {selectedConnection && (
        <>
          <div className="h-px bg-border" />

          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Checkbox
                id="api-enable-snapshots"
                checked={selectedNode.data.config.enable_snapshots || false}
                onCheckedChange={(checked) => handleUpdate("enable_snapshots", checked)}
              />
              <Label htmlFor="api-enable-snapshots" className="cursor-pointer">
                Enable Snapshots
              </Label>
            </div>

            <p className="text-xs text-muted-foreground">
              Automatically create snapshots for change detection and comparison
            </p>

            {selectedNode.data.config.enable_snapshots && (
              <>
                <div className="space-y-2 pl-6 border-l-2 border-primary/20">
                  <div className="space-y-2">
                    <Label className="text-xs">Snapshot Label (optional)</Label>
                    <Input
                      value={selectedNode.data.config.snapshot_label || ""}
                      onChange={(e) => handleUpdate("snapshot_label", e.target.value)}
                      placeholder="baseline, today, etc."
                      className="text-xs h-8"
                    />
                    <p className="text-xs text-muted-foreground">
                      Label to identify this snapshot (e.g., "baseline", "daily")
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label className="text-xs">Retention Days</Label>
                    <Input
                      type="number"
                      value={selectedNode.data.config.retention_days || 30}
                      onChange={(e) => handleUpdate("retention_days", parseInt(e.target.value))}
                      min="1"
                      max="365"
                      className="text-xs h-8"
                    />
                    <p className="text-xs text-muted-foreground">
                      How many days to keep snapshots before deletion
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>
        </>
      )}

      <div className="h-px bg-border" />

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Checkbox
            id="api-fail-on-empty"
            checked={selectedNode.data.config.api_fail_on_empty || false}
            onCheckedChange={(checked) => handleUpdate("api_fail_on_empty", checked)}
          />
          <Label htmlFor="api-fail-on-empty" className="cursor-pointer">
            Fail on empty response
          </Label>
        </div>

        <p className="text-xs text-muted-foreground">
          Halt the workflow if the response is empty at the configured path
        </p>

        {selectedNode.data.config.api_fail_on_empty && (
          <div className="space-y-2 pl-6 border-l-2 border-primary/20">
            <Label className="text-xs">Empty-check path (optional)</Label>
            <Input
              value={selectedNode.data.config.api_empty_check_path || ""}
              onChange={(e) => handleUpdate("api_empty_check_path", e.target.value || null)}
              placeholder="Defaults to response data path"
              className="text-xs h-8"
            />
            <p className="text-xs text-muted-foreground">
              JSONPath to check for emptiness (e.g. <code>$.meta.total</code>). Falls back to the response data path when unset.
            </p>
          </div>
        )}

        <div className="space-y-2">
          <Label className="text-xs">Expected status codes (optional)</Label>
          <Input
            value={(selectedNode.data.config.api_expected_status_codes || []).join(", ")}
            onChange={(e) => {
              const raw = e.target.value;
              if (!raw.trim()) {
                handleUpdate("api_expected_status_codes", null);
                return;
              }
              const codes = raw
                .split(",")
                .map((s) => parseInt(s.trim(), 10))
                .filter((n) => !isNaN(n));
              handleUpdate("api_expected_status_codes", codes);
            }}
            placeholder="e.g. 200, 201"
            className="text-xs h-8"
          />
          <p className="text-xs text-muted-foreground">
            Comma-separated list of acceptable HTTP status codes. When unset, any 2xx is accepted.
          </p>
        </div>
      </div>

      {/* Help Text */}
      {!selectedConnection && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 dark:border-blue-900 dark:bg-blue-950 p-3">
          <p className="text-xs text-blue-900 dark:text-blue-100">
            <strong>Getting Started:</strong> Select an API connection to fetch data from a REST API endpoint.
            API connections are managed in{" "}
            <a
              href="/settings/api-connections"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-blue-700 dark:hover:text-blue-300"
            >
              Settings → API Connections
            </a>
          </p>
        </div>
      )}
    </div>
  );
}
