"use client";

/**
 * MCP Servers Settings Page
 *
 * UI for managing MCP (Model Context Protocol) server connections.
 * Users can connect to stdio or HTTP-based MCP servers, test connections,
 * and view available tools/resources/prompts.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { mcpServersApi, MCPServer, MCPServerCreate } from "@/lib/api/mcp-servers";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Loader2,
  Plus,
  Server,
  Trash2,
  TestTube,
  ChevronDown,
  ChevronRight,
  Edit,
  AlertCircle,
  CheckCircle,
  MinusCircle,
  LogOut,
} from "lucide-react";
import { toast } from "sonner";
import { SettingsHeader } from "@/components/settings/settings-header";

export default function MCPServersPage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingServer, setEditingServer] = useState<MCPServer | null>(null);
  const [expandedServers, setExpandedServers] = useState<Set<string>>(new Set());

  const queryClient = useQueryClient();

  // Fetch servers
  const { data: servers = [], isLoading } = useQuery({
    queryKey: ["mcp-servers"],
    queryFn: mcpServersApi.list,
  });

  // Create/Update mutation
  const saveMutation = useMutation({
    mutationFn: async (data: MCPServerCreate) => {
      if (editingServer) {
        return mcpServersApi.update(editingServer.id, data);
      } else {
        return mcpServersApi.create(data);
      }
    },
    onSuccess: async (createdServer) => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
      setIsDialogOpen(false);
      setEditingServer(null);
      toast.success(editingServer ? "Server updated" : "Server created");

      // Auto-test server after creation to trigger OAuth flow if needed
      if (!editingServer && createdServer?.id) {
        try {
          const testResult = await mcpServersApi.test(createdServer.id);

          // Check if OAuth is required
          if (!testResult.success && (testResult.capabilities as any)?.needs_oauth) {
            // Check if manual setup is required
            if ((testResult.capabilities as any).manual_setup_required) {
              toast.warning("OAuth required. Please configure OAuth credentials manually.");
              return;
            }

            const authUrl = (testResult.capabilities as any).authorization_url;

            // Open OAuth authorization in popup
            const popup = window.open(
              authUrl,
              'mcp_oauth_authorization',
              'width=600,height=700,left=200,top=100'
            );

            // Listen for OAuth success message
            const messageHandler = (event: MessageEvent) => {
              if (event.data.type === 'mcp_oauth_success') {
                window.removeEventListener('message', messageHandler);
                popup?.close();

                // Re-test server after OAuth
                queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
                toast.success("OAuth authentication successful!");
              }
            };

            window.addEventListener('message', messageHandler);
          }
        } catch (error) {
          console.error('Auto-test failed:', error);
        }
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to save server");
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: mcpServersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
      toast.success("Server deleted");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to delete server");
    },
  });

  // Test mutation
  const testMutation = useMutation({
    mutationFn: mcpServersApi.test,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });

      // Check if OAuth is required
      if (!result.success && (result as any).capabilities?.needs_oauth) {
        // Check if manual setup is required
        if ((result as any).capabilities.manual_setup_required) {
          toast.error("OAuth required but automatic setup not supported. Please configure OAuth manually.");
          return;
        }

        const authUrl = (result as any).capabilities.authorization_url;
        toast.info("OAuth authentication required");

        // Open OAuth authorization in popup
        const popup = window.open(
          authUrl,
          'mcp_oauth_authorization',
          'width=600,height=700,left=200,top=100'
        );

        // Listen for OAuth success message
        const messageHandler = (event: MessageEvent) => {
          if (event.data.type === 'mcp_oauth_success') {
            window.removeEventListener('message', messageHandler);
            popup?.close();
            queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
            toast.success("OAuth authentication successful!");
          }
        };

        window.addEventListener('message', messageHandler);
      } else if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to test server");
    },
  });

  // Logout mutation
  const logoutMutation = useMutation({
    mutationFn: mcpServersApi.logout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
      toast.success("Logged out successfully. OAuth tokens cleared.");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to logout");
    },
  });

  const handleEdit = (server: MCPServer) => {
    setEditingServer(server);
    setIsDialogOpen(true);
  };

  const handleNew = () => {
    setEditingServer(null);
    setIsDialogOpen(true);
  };

  const toggleExpanded = (serverId: string) => {
    const newExpanded = new Set(expandedServers);
    if (newExpanded.has(serverId)) {
      newExpanded.delete(serverId);
    } else {
      newExpanded.add(serverId);
    }
    setExpandedServers(newExpanded);
  };

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="MCP Servers"
        description="Connect to Model Context Protocol servers to extend agent capabilities"
      />
      <Button onClick={handleNew}>
        <Plus className="mr-2 h-4 w-4" />
        New Server
      </Button>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin" />
        </div>
      ) : servers.length === 0 ? (
        <Card className="p-12 text-center">
          <Server className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-semibold">No MCP Servers</h3>
          <p className="text-muted-foreground">
            Connect to MCP servers to add tools, resources, and prompts to your agents
          </p>
          <Button className="mt-4" onClick={handleNew}>
            <Plus className="mr-2 h-4 w-4" />
            Add Your First Server
          </Button>
        </Card>
      ) : (
        <div className="grid gap-4">
          {servers.map((server) => (
            <ServerCard
              key={server.id}
              server={server}
              isExpanded={expandedServers.has(server.id)}
              onToggleExpand={() => toggleExpanded(server.id)}
              onEdit={() => handleEdit(server)}
              onDelete={() => {
                if (confirm(`Delete server "${server.name}"?`)) {
                  deleteMutation.mutate(server.id);
                }
              }}
              onTest={() => testMutation.mutate(server.id)}
              onLogout={() => {
                if (confirm(`Logout from "${server.name}"? This will clear stored OAuth tokens.`)) {
                  logoutMutation.mutate(server.id);
                }
              }}
              isTesting={testMutation.isPending}
              isLoggingOut={logoutMutation.isPending}
            />
          ))}
        </div>
      )}

      <MCPServerDialog
        open={isDialogOpen}
        onOpenChange={setIsDialogOpen}
        server={editingServer}
        onSave={(data) => saveMutation.mutate(data)}
        isSaving={saveMutation.isPending}
      />
    </div>
  );
}

// ============================================================================
// ServerCard Component
// ============================================================================

interface ServerCardProps {
  server: MCPServer;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onTest: () => void;
  onLogout: () => void;
  isTesting: boolean;
  isLoggingOut: boolean;
}

function ServerCard({
  server,
  isExpanded,
  onToggleExpand,
  onEdit,
  onDelete,
  onTest,
  onLogout,
  isTesting,
  isLoggingOut,
}: ServerCardProps) {
  const { data: tools = [] } = useQuery({
    queryKey: ["mcp-tools", server.id],
    queryFn: () => mcpServersApi.listTools(server.id),
    enabled: isExpanded,
  });

  const toolCount = server.capabilities?.tools?.length || 0;
  const resourceCount = server.capabilities?.resources?.length || 0;
  const promptCount = server.capabilities?.prompts?.length || 0;

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <Server className="h-5 w-5 text-muted-foreground flex-shrink-0" />
            <h3 className="text-lg font-semibold">{server.name}</h3>
            <StatusBadge status={server.status} />
            <Badge variant="outline">{server.protocol.toUpperCase()}</Badge>
          </div>

          {server.description && (
            <p className="mt-2 text-sm text-muted-foreground">{server.description}</p>
          )}

          <div className="mt-3 flex flex-wrap gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <strong>URL:</strong> {server.url}
            </span>
            {server.auth_type && server.auth_type !== "none" && (
              <span className="flex items-center gap-1">
                <strong>Auth:</strong> {server.auth_type === "oauth" ? "OAuth" : server.auth_type.toUpperCase()}
              </span>
            )}
            {server.auth_type === "oauth" && server.auth_config?.connected && (
              <Badge variant="outline" className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-green-600" />
                OAuth Connected
              </Badge>
            )}
          </div>

          {server.capabilities && (
            <div className="mt-2 flex gap-4 text-sm text-muted-foreground">
              <span>{toolCount} tools</span>
              <span>{resourceCount} resources</span>
              <span>{promptCount} prompts</span>
            </div>
          )}

          {server.last_test_message && (
            <p className="mt-2 text-sm text-muted-foreground">
              <strong>Last test:</strong> {server.last_test_message}
            </p>
          )}
        </div>

        <div className="flex gap-2 flex-shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={onTest}
            disabled={isTesting}
            title="Test connection and discover capabilities"
          >
            {isTesting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <TestTube className="h-4 w-4" />
            )}
          </Button>
          {server.auth_type === "oauth" && server.status !== "needs_auth" && (
            <Button
              variant="outline"
              size="sm"
              onClick={onLogout}
              disabled={isLoggingOut}
              title="Logout and clear OAuth tokens"
            >
              {isLoggingOut ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4" />
              )}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onEdit} title="Edit server">
            <Edit className="h-4 w-4" />
          </Button>
          <Button variant="destructive" size="sm" onClick={onDelete} title="Delete server">
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Expandable tools list */}
      {toolCount > 0 && (
        <div className="mt-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleExpand}
            className="flex items-center gap-2"
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
            {toolCount} {toolCount === 1 ? "Tool" : "Tools"}
          </Button>

          {isExpanded && (
            <div className="mt-2 space-y-2 pl-6">
              {tools.map((tool) => (
                <div key={tool.id} className="rounded-lg border p-3">
                  <div className="font-medium text-sm">{tool.tool_name}</div>
                  {tool.description && (
                    <div className="text-sm text-muted-foreground mt-1">{tool.description}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// StatusBadge Component
// ============================================================================

function StatusBadge({ status }: { status: string }) {
  const config = {
    connected: { icon: CheckCircle, variant: "default" as const, label: "Connected" },
    error: { icon: AlertCircle, variant: "destructive" as const, label: "Error" },
    untested: { icon: MinusCircle, variant: "secondary" as const, label: "Untested" },
    disconnected: { icon: MinusCircle, variant: "outline" as const, label: "Disconnected" },
    needs_auth: { icon: AlertCircle, variant: "secondary" as const, label: "Needs Auth" },
  }[status] || { icon: MinusCircle, variant: "secondary" as const, label: "Unknown" };

  const Icon = config.icon;

  return (
    <Badge variant={config.variant} className="flex items-center gap-1">
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}

// ============================================================================
// Dialog Component
// ============================================================================

interface MCPServerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  server: MCPServer | null;
  onSave: (data: MCPServerCreate) => void;
  isSaving: boolean;
}

function MCPServerDialog({ open, onOpenChange, server, onSave, isSaving }: MCPServerDialogProps) {
  const [formData, setFormData] = useState<MCPServerCreate>(() => ({
    name: server?.name || "",
    description: server?.description || "",
    protocol: "http", // Always HTTP now
    url: server?.url || "",
    headers: server?.headers || {},
    auth_type: server?.auth_type || "none",
  }));

  // Reset form when dialog opens with different server
  useState(() => {
    if (open) {
      setFormData({
        name: server?.name || "",
        description: server?.description || "",
        protocol: "http", // Always HTTP now
        url: server?.url || "",
        headers: server?.headers || {},
        auth_type: server?.auth_type || "none",
      });
    }
  });

  const handleSubmit = () => {
    // Validate
    if (!formData.name.trim()) {
      toast.error("Server name is required");
      return;
    }

    if (!formData.url?.trim()) {
      toast.error("URL is required");
      return;
    }

    // OAuth connection will be established automatically on first request if needed
    // No need to require connection before saving
    onSave(formData);
  };

  const handleServerOAuthConnect = async (serverUrl: string, serverName: string) => {
    if (!serverUrl?.trim()) {
      toast.error("Please enter a server URL first");
      return;
    }

    try {
      // Normalize the URL
      const baseUrl = serverUrl.trim().replace(/\/$/, '');

      // Open the MCP server's OAuth authorization endpoint
      // This endpoint should immediately redirect to the OAuth provider (e.g., Outreach)
      const oauthAuthorizeUrl = `${baseUrl}/oauth/authorize`;

      const width = 600;
      const height = 700;
      const left = window.screenX + (window.outerWidth - width) / 2;
      const top = window.screenY + (window.outerHeight - height) / 2;

      const popup = window.open(
        oauthAuthorizeUrl,
        'mcp_oauth_authorization',
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no,status=no,resizable=yes,scrollbars=yes`
      );

      if (!popup) {
        toast.error("Please allow popups to authenticate");
        return;
      }

      toast.info(`Connecting to ${serverName || 'MCP server'}...`);

      // Listen for OAuth callback message from popup
      const messageHandler = (event: MessageEvent) => {
        // Verify origin matches server URL for security
        const serverOrigin = new URL(baseUrl).origin;

        // Accept messages from server origin or same origin (for local development)
        if (event.origin !== serverOrigin && event.origin !== window.location.origin) {
          console.warn('Ignoring message from unknown origin:', event.origin);
          return;
        }

        // Handle success message
        if (event.data.type === 'mcp_oauth_success') {
          const { access_token, refresh_token, expires_in, user_info } = event.data;

          // Update form data with connection info
          setFormData({
            ...formData,
            auth_config: {
              access_token,
              refresh_token,
              token_expires_at: expires_in
                ? new Date(Date.now() + expires_in * 1000).toISOString()
                : undefined,
              connected: true,
              user_info: user_info || null,
              connected_at: new Date().toISOString(),
            } as any,
          });

          toast.success(`Successfully connected to ${serverName || 'MCP server'}!`);
          popup?.close();
          window.removeEventListener('message', messageHandler);
        }
        // Handle error message
        else if (event.data.type === 'mcp_oauth_error') {
          const errorMsg = event.data.error_description || event.data.error || 'Authentication failed';
          toast.error(`Connection failed: ${errorMsg}`);
          popup?.close();
          window.removeEventListener('message', messageHandler);
        }
        // Handle cancellation
        else if (event.data.type === 'mcp_oauth_cancel') {
          toast.info('Authentication cancelled');
          popup?.close();
          window.removeEventListener('message', messageHandler);
        }
      };

      window.addEventListener('message', messageHandler);

      // Monitor popup close
      const checkPopup = setInterval(() => {
        if (popup?.closed) {
          clearInterval(checkPopup);
          window.removeEventListener('message', messageHandler);
        }
      }, 500);

      // Cleanup after 5 minutes (timeout)
      setTimeout(() => {
        if (popup && !popup.closed) {
          popup.close();
        }
        window.removeEventListener('message', messageHandler);
      }, 5 * 60 * 1000);

    } catch (error) {
      console.error('OAuth connection error:', error);
      toast.error("Failed to initiate authentication. Please check the server URL.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{server ? "Edit" : "New"} MCP Server</DialogTitle>
          <DialogDescription>
            Connect to a Model Context Protocol server to add tools and capabilities to your agents.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <Label htmlFor="name">Name *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="My MCP Server"
            />
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description || ""}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Optional description of this server"
              rows={2}
            />
          </div>

          {/* HTTP Configuration Only */}
          <div className="space-y-4">
            <div>
              <Label htmlFor="url">URL *</Label>
              <Input
                id="url"
                value={formData.url || ""}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                placeholder="https://mcp-server.example.com"
              />
            </div>

            <div>
              <Label htmlFor="auth_type">Authentication</Label>
              <Select
                value={formData.auth_type || "none"}
                onValueChange={(v) => setFormData({ ...formData, auth_type: v as any })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  <SelectItem value="auto">Automatic (Detect OAuth)</SelectItem>
                  <SelectItem value="bearer">Bearer Token</SelectItem>
                  <SelectItem value="api_key">API Key</SelectItem>
                  <SelectItem value="oauth">OAuth Flow (Manual)</SelectItem>
                </SelectContent>
              </Select>
              {(formData.auth_type as string) === "auto" && (
                <p className="text-xs text-muted-foreground mt-1">
                  OpenCode will automatically detect and handle OAuth authentication when needed.
                </p>
              )}
            </div>

            {formData.auth_type === "bearer" && (
              <div>
                <Label htmlFor="bearer_token">Bearer Token</Label>
                <Input
                  id="bearer_token"
                  type="password"
                  placeholder="Enter bearer token"
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      auth_config: { token: e.target.value },
                    })
                  }
                />
              </div>
            )}

            {formData.auth_type === "api_key" && (
              <>
                <div>
                  <Label htmlFor="key_name">Header Name</Label>
                  <Input
                    id="key_name"
                    defaultValue="X-API-Key"
                    placeholder="X-API-Key"
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        auth_config: {
                          ...formData.auth_config,
                          key_name: e.target.value,
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="api_key">API Key</Label>
                  <Input
                    id="api_key"
                    type="password"
                    placeholder="Enter API key"
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        auth_config: {
                          ...formData.auth_config,
                          key: e.target.value,
                        },
                      })
                    }
                  />
                </div>
              </>
            )}

            {(formData.auth_type === "oauth" || (formData.auth_type as string) === "auto") && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Label>Connection Status</Label>
                    {(formData.auth_config as any)?.connected ? (
                      <Badge variant="default" className="flex items-center gap-1">
                        <CheckCircle className="h-3 w-3" />
                        Connected
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="flex items-center gap-1">
                        <MinusCircle className="h-3 w-3" />
                        {(formData.auth_type as string) === "auto" ? "Will Connect Automatically" : "Not Connected"}
                      </Badge>
                    )}
                  </div>
                </div>

                {(formData.auth_type as string) === "auto" ? (
                  <p className="text-sm text-muted-foreground">
                    OAuth authentication will be automatically initiated when you first connect to this server.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Click Connect to authenticate with the MCP server using your credentials.
                  </p>
                )}

                {formData.auth_type === "oauth" && (
                  <Button
                    type="button"
                    variant={(formData.auth_config as any)?.connected ? 'outline' : 'default'}
                    size="lg"
                    onClick={() => handleServerOAuthConnect(formData.url || '', formData.name || '')}
                    disabled={!formData.url?.trim()}
                    className="w-full"
                  >
                    {(formData.auth_config as any)?.connected ? (
                      <>
                        <CheckCircle className="mr-2 h-4 w-4" />
                        Reconnect
                      </>
                    ) : (
                      <>
                        Connect
                      </>
                    )}
                  </Button>
                )}

                {(formData.auth_config as any)?.connected && (formData.auth_config as any)?.user_info && (
                  <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-md">
                    <div className="font-medium mb-1">Connected Account</div>
                    <div>{(formData.auth_config as any).user_info.email || (formData.auth_config as any).user_info.name || 'User authenticated'}</div>
                  </div>
                )}
              </div>
            )}

            <div>
              <Label htmlFor="headers">Additional Headers (JSON)</Label>
              <Textarea
                id="headers"
                value={JSON.stringify(formData.headers || {})}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    setFormData({ ...formData, headers: parsed });
                  } catch {
                    // Invalid JSON, ignore
                  }
                }}
                placeholder='{"Accept": "application/json"}'
                rows={3}
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {server ? "Update" : "Create"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
