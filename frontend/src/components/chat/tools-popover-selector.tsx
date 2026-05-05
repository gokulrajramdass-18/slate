"use client";

import { useState, useEffect } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Wrench, Database, Globe, Calculator, Code } from "lucide-react";
import { apiClient } from "@/lib/api/client";

interface Tool {
  id: string;
  name: string;
  description: string;
  tool_type: string;
  category?: string;
  source?: 'registry' | 'source' | 'mcp';
  server_name?: string;
  server_id?: string;
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

interface ToolsPopoverSelectorProps {
  sessionId: string;
  notebookId?: string;
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

export function ToolsPopoverSelector({
  sessionId,
  notebookId,
  selectedToolIds,
  onSelectionChange,
  disabled = false,
}: ToolsPopoverSelectorProps) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (sessionId && notebookId) {
      const timer = setTimeout(() => {
        fetchTools();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [sessionId, notebookId]);

  const fetchTools = async () => {
    if (!sessionId || !notebookId) {
      console.warn("[ToolsPopoverSelector] Cannot fetch tools: missing sessionId or notebookId");
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const url = `/chat/sessions/${sessionId}/tools`;
      const { data } = await apiClient.get(url);
      setTools(data.tools || []);
      setMcpServers(data.mcp_servers || []);

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
      console.error("[ToolsPopoverSelector] Failed to fetch tools:", err);
      const errorMsg = err.response?.data?.detail ||
                      err.message ||
                      "Failed to load tools";
      setError(errorMsg);
      // Set empty arrays so component can still render
      setTools([]);
      setMcpServers([]);
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

  // Group tools by source type
  const sourceTools = tools.filter(t => t.source === "source");
  const registryTools = tools.filter(t => t.source === "registry");
  const totalMcpTools = mcpServers.reduce((sum, server) => sum + server.tools.length, 0);
  const totalTools = tools.length + totalMcpTools;

  // Don't render until we have required data
  if (!sessionId || !notebookId) {
    return null;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          disabled={disabled}
          className="h-8 w-8 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 relative"
          title={`Tools (${selectedToolIds.length} selected)`}
        >
          <Wrench className="w-4 h-4 text-gray-600 dark:text-gray-400" />
          {selectedToolIds.length > 0 && (
            <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-blue-500 text-white text-[10px] font-medium flex items-center justify-center">
              {selectedToolIds.length}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[320px] p-0 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700" align="start">
        <div className="flex items-center justify-between p-3 border-b">
          <div className="flex items-center gap-2">
            <Wrench className="w-4 h-4" />
            <span className="text-sm font-medium">Available Tools</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSelectAll}
              disabled={disabled}
              className="text-xs text-blue-600 hover:text-blue-800 disabled:text-gray-400"
            >
              All
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

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
          </div>
        ) : error ? (
          <div className="p-3 text-sm text-red-600">{error}</div>
        ) : totalTools === 0 ? (
          <div className="p-3 text-sm text-gray-500">
            No tools available. Add HANA tables or API sources to enable tools.
          </div>
        ) : (
          <>
            <div className="px-3 py-2 text-xs text-gray-500 border-b">
              {selectedToolIds.length} of {totalTools} selected
            </div>

            <Tabs defaultValue="tools" className="w-full">
              <TabsList className="w-full grid grid-cols-2 rounded-none border-b">
                <TabsTrigger value="tools" className="text-xs">
                  Tools ({tools.length})
                </TabsTrigger>
                <TabsTrigger value="mcp" className="text-xs">
                  MCP ({totalMcpTools})
                </TabsTrigger>
              </TabsList>

              {/* Regular Tools Tab */}
              <TabsContent value="tools" className="mt-0">
                <ScrollArea className="h-[350px]">
                  <div className="space-y-3 p-3">
                    {tools.length === 0 ? (
                      <div className="text-xs text-gray-500 text-center py-4">
                        No regular tools available
                      </div>
                    ) : (
                      <>
                        {/* Source-based tools */}
                        {sourceTools.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1.5">
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
                                    id={`tool-popover-${tool.id}`}
                                    checked={selectedToolIds.includes(tool.id)}
                                    onCheckedChange={() => handleToggle(tool.id)}
                                    disabled={disabled}
                                  />
                                  <div className="flex-1 min-w-0 flex items-center gap-2">
                                    {getToolIcon(tool.tool_type)}
                                    <Label
                                      htmlFor={`tool-popover-${tool.id}`}
                                      className="text-xs font-medium cursor-pointer truncate"
                                    >
                                      {tool.name}
                                    </Label>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Registry tools */}
                        {registryTools.length > 0 && (
                          <div>
                            <h4 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1.5">
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
                                    id={`tool-popover-${tool.id}`}
                                    checked={selectedToolIds.includes(tool.id)}
                                    onCheckedChange={() => handleToggle(tool.id)}
                                    disabled={disabled}
                                  />
                                  <div className="flex-1 min-w-0 flex items-center gap-2">
                                    {getToolIcon(tool.tool_type)}
                                    <Label
                                      htmlFor={`tool-popover-${tool.id}`}
                                      className="text-xs font-medium cursor-pointer truncate"
                                    >
                                      {tool.name}
                                    </Label>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>

              {/* MCP Tools Tab */}
              <TabsContent value="mcp" className="mt-0">
                <ScrollArea className="h-[350px]">
                  <div className="space-y-3 p-3">
                    {mcpServers.length === 0 ? (
                      <div className="text-xs text-gray-500 text-center py-4">
                        No MCP servers connected
                      </div>
                    ) : (
                      mcpServers.map((server) => (
                        <div key={server.id} className="space-y-1">
                          <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400 px-2">
                            <Globe className="h-3 w-3" />
                            <span className="font-medium">{server.name}</span>
                            <Badge variant="secondary" className="text-xs h-4 px-1">
                              {server.tools.length}
                            </Badge>
                            {server.status === 'connected' && (
                              <Badge variant="default" className="text-xs h-4 px-1 bg-green-500">
                                Connected
                              </Badge>
                            )}
                            {server.status === 'needs_auth' && (
                              <Badge variant="default" className="text-xs h-4 px-1 bg-yellow-500">
                                Auth Required
                              </Badge>
                            )}
                            {server.status === 'disconnected' && (
                              <Badge variant="destructive" className="text-xs h-4 px-1">
                                Disconnected
                              </Badge>
                            )}
                            {server.status === 'error' && (
                              <Badge variant="destructive" className="text-xs h-4 px-1">
                                Error
                              </Badge>
                            )}
                          </div>
                          {server.status !== 'connected' && (
                            <div className="ml-4 px-2 py-1 text-xs text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-950 rounded">
                              ⚠ Please authenticate this server in Settings → MCP Servers
                            </div>
                          )}
                          <div className="space-y-1 ml-4">
                            {server.tools.map((tool) => (
                              <div
                                key={tool.id}
                                className={`flex items-center space-x-2 px-2 py-1.5 rounded transition-colors ${
                                  selectedToolIds.includes(tool.id)
                                    ? "bg-blue-50 dark:bg-blue-950"
                                    : "hover:bg-gray-50 dark:hover:bg-gray-800"
                                } ${
                                  disabled || server.status !== 'connected'
                                    ? "opacity-50 cursor-not-allowed"
                                    : "cursor-pointer"
                                }`}
                                onClick={() => server.status === 'connected' && handleToggle(tool.id)}
                              >
                                <Checkbox
                                  id={`tool-popover-${tool.id}`}
                                  checked={selectedToolIds.includes(tool.id)}
                                  onCheckedChange={() => handleToggle(tool.id)}
                                  disabled={disabled || server.status !== 'connected'}
                                />
                                <div className="flex-1 min-w-0 flex items-center gap-2">
                                  {getToolIcon(tool.tool_type)}
                                  <Label
                                    htmlFor={`tool-popover-${tool.id}`}
                                    className="text-xs font-medium cursor-pointer truncate"
                                  >
                                    {tool.name}
                                  </Label>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
