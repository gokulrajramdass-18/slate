"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2, Wrench, Database, Globe, Calculator, Code } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface Tool {
  id: string;
  name: string;
  description: string;
  tool_type: string;
  category?: string;
  source?: 'registry' | 'source' | 'mcp';  // Added 'mcp'
  server_name?: string;  // For MCP tools
  server_id?: string;    // For MCP tools
  metadata?: {
    icon?: string;
    tags?: string[];
  };
}

interface MCPServer {
  id: string;
  name: string;
  status: string;
  tools: Tool[];
}

interface ToolsSelectorProps {
  sessionId: string;
  notebookId?: string;  // Optional since session may not have notebook_id
  selectedToolIds: string[];
  onSelectionChange: (toolIds: string[]) => void;
  disabled?: boolean;
}

const TOOL_ICONS: Record<string, typeof Wrench> = {
  hana_query: Database,
  api_call: Globe,
  web_search: Globe,
  calculator: Calculator,
  code_exec: Code,
  default: Wrench,
};

const CATEGORY_COLORS: Record<string, string> = {
  data_query: "bg-blue-100 text-blue-800",
  web: "bg-green-100 text-green-800",
  computation: "bg-purple-100 text-purple-800",
  file_analysis: "bg-orange-100 text-orange-800",
  default: "bg-gray-100 text-gray-800",
};

export function ToolsSelector({
  sessionId,
  notebookId,
  selectedToolIds,
  onSelectionChange,
  disabled = false,
}: ToolsSelectorProps) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Only fetch tools when we have both sessionId and notebookId
    if (sessionId && notebookId) {
      // Small delay to ensure session is fully loaded
      const timer = setTimeout(() => {
        fetchTools();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [sessionId, notebookId]);

  const fetchTools = async () => {
    // Guard against fetching when data isn't ready
    if (!sessionId || !notebookId) {
      console.warn("[ToolsSelector] Cannot fetch tools: missing sessionId or notebookId");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const url = `/chat/sessions/${sessionId}/tools`;
      console.log(`[ToolsSelector] Fetching tools from: ${url}`);
      console.log(`[ToolsSelector] API Base URL: ${apiClient.defaults.baseURL}`);
      console.log(`[ToolsSelector] Full URL: ${apiClient.defaults.baseURL}${url}`);
      console.log(`[ToolsSelector] Session ID: ${sessionId}, Notebook ID: ${notebookId}`);

      // Fetch available tools for this notebook
      const { data } = await apiClient.get(url);
      setTools(data.tools || []);
      setMcpServers(data.mcp_servers || []);

      console.log(`[ToolsSelector] Fetched ${data.tools?.length || 0} tools`);
      console.log(`[ToolsSelector] Fetched ${data.mcp_servers?.length || 0} MCP servers`);

      // Select all tools by default if none selected
      const allToolIds = [
        ...(data.tools || []).map((t: Tool) => t.id),
        ...(data.mcp_servers || []).flatMap((server: MCPServer) =>
          server.tools.map((t: Tool) => t.id)
        )
      ];

      if (selectedToolIds.length === 0 && allToolIds.length > 0) {
        onSelectionChange(allToolIds);
      }
    } catch (err: any) {
      console.error("[ToolsSelector] Failed to fetch tools:", err);
      console.error("[ToolsSelector] Error message:", err.message);
      console.error("[ToolsSelector] Error code:", err.code);
      console.error("[ToolsSelector] Error response:", err.response?.data);
      console.error("[ToolsSelector] Error status:", err.response?.status);
      console.error("[ToolsSelector] Request config:", err.config);

      // Show more helpful error message
      const errorMsg = err.response?.data?.detail ||
                      err.message ||
                      "Failed to load tools. Please check if the backend is running.";
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (toolId: string) => {
    if (disabled) return;

    if (selectedToolIds.includes(toolId)) {
      onSelectionChange(selectedToolIds.filter(id => id !== toolId));
    } else {
      onSelectionChange([...selectedToolIds, toolId]);
    }
  };

  const handleSelectAll = () => {
    if (disabled) return;
    const allToolIds = [
      ...tools.map(t => t.id),
      ...mcpServers.flatMap(server => server.tools.map(t => t.id))
    ];
    onSelectionChange(allToolIds);
  };

  const handleSelectNone = () => {
    if (disabled) return;
    onSelectionChange([]);
  };

  const getToolIcon = (toolType: string) => {
    const Icon = TOOL_ICONS[toolType] || TOOL_ICONS.default;
    return <Icon className="w-4 h-4" />;
  };

  const getCategoryColor = (category?: string) => {
    return CATEGORY_COLORS[category || "default"] || CATEGORY_COLORS.default;
  };

  // Group tools by source type
  const sourceTools = tools.filter(t => t.source === "source");
  const registryTools = tools.filter(t => t.source === "registry");

  // Calculate total MCP tools
  const totalMcpTools = mcpServers.reduce((sum, server) => sum + server.tools.length, 0);

  // Don't render until we have required data
  if (!sessionId || !notebookId) {
    return null;
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="w-5 h-5" />
            Available Tools
          </CardTitle>
          <CardDescription>Loading tools...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="w-5 h-5" />
            Available Tools
          </CardTitle>
          <CardDescription className="text-red-600">{error}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (tools.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="w-5 h-5" />
            Available Tools
          </CardTitle>
          <CardDescription>
            No tools available. Add HANA tables or API sources to enable tools.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Wrench className="w-5 h-5" />
              Available Tools
            </CardTitle>
            <CardDescription>
              {selectedToolIds.length} of {tools.length + totalMcpTools} selected
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSelectAll}
              disabled={disabled}
              className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
            >
              Select All
            </button>
            <span className="text-xs text-gray-400">|</span>
            <button
              onClick={handleSelectNone}
              disabled={disabled}
              className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
            >
              None
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[300px] pr-4">
          <div className="space-y-4">
            {/* Source-based tools */}
            {sourceTools.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">
                  Notebook Sources ({sourceTools.length})
                </h4>
                <div className="space-y-1">
                  {sourceTools.map((tool) => (
                    <div
                      key={tool.id}
                      className={`flex items-center space-x-2 px-2 py-1.5 rounded transition-colors ${
                        selectedToolIds.includes(tool.id)
                          ? "bg-blue-50 dark:bg-blue-950"
                          : "hover:bg-gray-50 dark:hover:bg-gray-800"
                      } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                      onClick={() => handleToggle(tool.id)}
                    >
                      <Checkbox
                        id={`tool-${tool.id}`}
                        checked={selectedToolIds.includes(tool.id)}
                        onCheckedChange={() => handleToggle(tool.id)}
                        disabled={disabled}
                      />
                      <div className="flex-1 min-w-0 flex items-center gap-2">
                        {getToolIcon(tool.tool_type)}
                        <Label
                          htmlFor={`tool-${tool.id}`}
                          className="text-sm font-medium cursor-pointer truncate"
                        >
                          {tool.name}
                        </Label>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                        {tool.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Registry tools */}
            {registryTools.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">
                  Global Tools ({registryTools.length})
                </h4>
                <div className="space-y-1">
                  {registryTools.map((tool) => (
                    <div
                      key={tool.id}
                      className={`flex items-center space-x-2 px-2 py-1.5 rounded transition-colors ${
                        selectedToolIds.includes(tool.id)
                          ? "bg-blue-50 dark:bg-blue-950"
                          : "hover:bg-gray-50 dark:hover:bg-gray-800"
                      } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                      onClick={() => handleToggle(tool.id)}
                    >
                      <Checkbox
                        id={`tool-${tool.id}`}
                        checked={selectedToolIds.includes(tool.id)}
                        onCheckedChange={() => handleToggle(tool.id)}
                        disabled={disabled}
                      />
                      <div className="flex-1 min-w-0 flex items-center gap-2">
                        {getToolIcon(tool.tool_type)}
                        <Label
                          htmlFor={`tool-${tool.id}`}
                          className="text-sm font-medium cursor-pointer truncate"
                        >
                          {tool.name}
                        </Label>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                        {tool.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* MCP Server tools */}
            {mcpServers.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">
                  MCP Tools ({totalMcpTools})
                </h4>
                <div className="space-y-3">
                  {mcpServers.map((server) => (
                    <div key={server.id} className="space-y-2">
                      <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 px-2">
                        <Globe className="h-3 w-3" />
                        <span className="font-medium">{server.name}</span>
                        <Badge variant="secondary" className="text-xs h-5">
                          {server.tools.length} {server.tools.length === 1 ? 'tool' : 'tools'}
                        </Badge>
                        {server.status === 'connected' && (
                          <Badge variant="default" className="text-xs h-5 bg-green-500">
                            Connected
                          </Badge>
                        )}
                        {server.status === 'disconnected' && (
                          <Badge variant="destructive" className="text-xs h-5">
                            Disconnected
                          </Badge>
                        )}
                      </div>
                      <div className="space-y-1 ml-5">
                        {server.tools.map((tool) => (
                          <div
                            key={tool.id}
                            className={`flex items-center space-x-2 px-2 py-1.5 rounded transition-colors ${
                              selectedToolIds.includes(tool.id)
                                ? "bg-blue-50 dark:bg-blue-950"
                                : "hover:bg-gray-50 dark:hover:bg-gray-800"
                            } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                            onClick={() => handleToggle(tool.id)}
                          >
                            <Checkbox
                              id={`tool-${tool.id}`}
                              checked={selectedToolIds.includes(tool.id)}
                              onCheckedChange={() => handleToggle(tool.id)}
                              disabled={disabled}
                            />
                            <div className="flex-1 min-w-0 flex items-center gap-2">
                              {getToolIcon(tool.tool_type)}
                              <Label
                                htmlFor={`tool-${tool.id}`}
                                className="text-sm font-medium cursor-pointer truncate"
                              >
                                {tool.name}
                              </Label>
                            </div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[200px]">
                              {tool.description}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
