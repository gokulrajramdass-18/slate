/**
 * MCP Servers Settings Page
 *
 * UI for managing MCP (Model Context Protocol) server connections.
 * Users can connect to stdio or HTTP-based MCP servers, test connections,
 * and view available tools/resources/prompts.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  mcpServersApi,
  MCPServer,
  MCPServerCreate,
  MCPServerSession,
} from "@/lib/api/mcp-servers";
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  Users,
  ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";
import { SettingsHeader } from "@/components/settings/settings-header";
import { useAuthStore } from "@/lib/stores/auth-store";
import type { QueryClient } from "@tanstack/react-query";

/**
 * Run the per-user OAuth popup flow for a server.
 *
 * Browser popup blockers require `window.open()` to fire synchronously
 * from the click handler. So we open a placeholder popup first, then ask
 * the backend (using the user's JWT) for the signed authorization URL,
 * and finally point the popup at it. The signed `state` parameter
 * contains the user_id, which the backend recovers in /oauth/callback.
 */
async function openOAuthPopup(
  serverId: string,
  queryClient: QueryClient,
): Promise<void> {
  const width = 600;
  const height = 700;
  const left = window.screenX + (window.outerWidth - width) / 2;
  const top = window.screenY + (window.outerHeight - height) / 2;

  // Open a blank popup synchronously to satisfy popup-blocker rules.
  const popup = window.open(
    "about:blank",
    "mcp_oauth_authorization",
    `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no,location=no,status=no,resizable=yes,scrollbars=yes`,
  );

  if (!popup) {
    toast.error("Please allow popups to authenticate");
    return;
  }

  let authUrl: string;
  try {
    const { authorization_url } = await mcpServersApi.startOAuth(serverId);
    authUrl = authorization_url;
  } catch (e: any) {
    popup.close();
    // 403 here means this is a system-mode server and the caller is
    // not an admin. Surface a clear message instead of a generic error.
    if (e?.response?.status === 403) {
      toast.info(
        "This server uses a shared system account. Ask an administrator to sign in once — everyone will then be able to use it.",
      );
    } else {
      toast.error(e?.response?.data?.detail || "Failed to start OAuth");
    }
    return;
  }

  // Navigate the placeholder to the signed provider URL.
  popup.location.href = authUrl;

  // Listen for the success/error postMessage from the callback page and
  // poll for popup close so we can clean up.
  await new Promise<void>((resolve) => {
    const cleanup = () => {
      window.removeEventListener("message", handler);
      clearInterval(checkClosed);
      clearTimeout(timeout);
      resolve();
    };

    const handler = (event: MessageEvent) => {
      if (event.data?.type === "mcp_oauth_success") {
        toast.success("OAuth authentication successful!");
        // Refetch the server list (now status='connected', has capabilities)
        // *and* every cached per-server tool query so the freshly
        // discovered tools render without a manual Test click.
        queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
        queryClient.invalidateQueries({ queryKey: ["mcp-tools"] });
        if (!popup.closed) popup.close();
        cleanup();
      } else if (event.data?.type === "mcp_oauth_error") {
        toast.error(
          event.data.error_description ||
            event.data.error ||
            "Authentication failed",
        );
        if (!popup.closed) popup.close();
        cleanup();
      }
    };

    window.addEventListener("message", handler);

    // If the user closes the popup, drop the listener.
    const checkClosed = setInterval(() => {
      if (popup.closed) cleanup();
    }, 500);

    // Hard cutoff at 5 minutes — matches backend state TTL.
    const timeout = setTimeout(
      () => {
        if (!popup.closed) popup.close();
        cleanup();
      },
      5 * 60 * 1000,
    );
  });
}

export default function SettingsMcpServersPage() {
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

            // Per-user OAuth: open the popup synchronously, then navigate
            // it once the authenticated /oauth/start endpoint returns the
            // signed authorization URL with the user's identity baked in.
            await openOAuthPopup(createdServer.id, queryClient);
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
    onSuccess: async (result, serverId) => {
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });

      // Check if OAuth is required
      if (!result.success && (result as any).capabilities?.needs_oauth) {
        // Check if manual setup is required
        if ((result as any).capabilities.manual_setup_required) {
          toast.error(
            "OAuth required but automatic setup not supported. Please configure OAuth manually."
          );
          return;
        }

        toast.info("OAuth authentication required");
        // Per-user popup flow — see openOAuthPopup() below
        await openOAuthPopup(serverId, queryClient);
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
      toast.success("Signed out. Your tokens have been cleared.");
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

      <Tabs defaultValue="servers" className="w-full">
        <TabsList>
          <TabsTrigger value="servers" className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            Servers
          </TabsTrigger>
          <TabsTrigger value="sessions" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            User Sessions
          </TabsTrigger>
        </TabsList>

        <TabsContent value="servers" className="space-y-4">
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
                    const isSystem = server.oauth_mode === "system";
                    const message = isSystem
                      ? `Sign all users out of "${server.name}"? This is a shared system account — every user will need to wait for an admin to sign in again.`
                      : `Sign out of "${server.name}"? Only your session is cleared — other users keep theirs.`;
                    if (confirm(message)) {
                      logoutMutation.mutate(server.id);
                    }
                  }}
                  isTesting={testMutation.isPending}
                  isLoggingOut={logoutMutation.isPending}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="sessions" className="space-y-4">
          <UserSessionsTab servers={servers} isLoadingServers={isLoading} />
        </TabsContent>
      </Tabs>

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
// UserSessionsTab Component
// ============================================================================
//
// Lists who is authenticated against each OAuth-enabled MCP server, with
// a one-click revoke action. Backed by GET/DELETE /sessions endpoints.
//
// Visibility rules (enforced server-side; we mirror them in the UI for
// clarity):
//   - Non-admin: sees only their own session per server.
//   - Admin:     sees every user's session, including the shared
//                `__system__` row that backs system-mode servers.

interface UserSessionsTabProps {
  servers: MCPServer[];
  isLoadingServers: boolean;
}

function UserSessionsTab({ servers, isLoadingServers }: UserSessionsTabProps) {
  const isAdmin = useAuthStore((s) => s.user?.is_superadmin ?? false);

  // We only show OAuth-enabled servers — non-OAuth servers don't have
  // user-scoped sessions to manage.
  const oauthServers = servers.filter((s) => s.auth_type === "oauth");

  if (isLoadingServers) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (oauthServers.length === 0) {
    return (
      <Card className="p-12 text-center">
        <Users className="mx-auto h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">No OAuth servers</h3>
        <p className="text-muted-foreground">
          User sessions are only tracked for servers that use OAuth.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {!isAdmin && (
        <Card className="flex items-start gap-3 border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900/40 dark:bg-amber-950/30">
          <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-600" />
          <div className="text-amber-900 dark:text-amber-200">
            You can only see and disconnect <strong>your own</strong> sessions.
            Administrators can manage every user's session.
          </div>
        </Card>
      )}

      {oauthServers.map((server) => (
        <ServerSessionsCard key={server.id} server={server} isAdmin={isAdmin} />
      ))}
    </div>
  );
}

interface ServerSessionsCardProps {
  server: MCPServer;
  isAdmin: boolean;
}

function ServerSessionsCard({ server, isAdmin }: ServerSessionsCardProps) {
  const queryClient = useQueryClient();

  const {
    data: sessions = [],
    isLoading,
    isError,
    error,
  } = useQuery<MCPServerSession[]>({
    queryKey: ["mcp-server-sessions", server.id],
    queryFn: () => mcpServersApi.listSessions(server.id),
    // Refresh whenever the user comes back to this tab — sessions are
    // long-lived, so a manual refresh on focus is enough.
    refetchOnWindowFocus: true,
  });

  const revokeMutation = useMutation({
    mutationFn: ({ userId }: { userId: string }) =>
      mcpServersApi.revokeSession(server.id, userId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["mcp-server-sessions", server.id],
      });
      // Also refresh the servers list — if the calling user revoked
      // themselves, their `current_user_status` should flip to needs_auth.
      queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
      const isSystem = variables.userId === "__system__";
      toast.success(
        isSystem
          ? "System session revoked. All users are now signed out."
          : "Session revoked.",
      );
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || "Failed to revoke session");
    },
  });

  const isSystemMode = server.oauth_mode === "system";

  const handleRevoke = (session: MCPServerSession) => {
    let message: string;
    if (session.is_system) {
      message = `Revoke the shared system session for "${server.name}"? Every user will be signed out and an admin will need to re-authenticate.`;
    } else if (session.is_current_user) {
      message = `Sign yourself out of "${server.name}"?`;
    } else {
      const who =
        session.email ||
        session.username ||
        session.provider_email ||
        session.user_id;
      message = `Revoke ${who}'s session for "${server.name}"? They will need to sign in again.`;
    }
    if (confirm(message)) {
      revokeMutation.mutate({ userId: session.user_id });
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <Server className="h-5 w-5 text-muted-foreground" />
            <h3 className="text-lg font-semibold">{server.name}</h3>
            <Badge
              variant="outline"
              className="text-xs"
              title={
                isSystemMode
                  ? "Shared system account — one OAuth token used by all users."
                  : "Each user signs in with their own identity."
              }
            >
              {isSystemMode ? "Shared" : "Per-user"}
            </Badge>
          </div>
          {server.url && (
            <p className="mt-1 text-sm text-muted-foreground">{server.url}</p>
          )}
        </div>
        <Badge variant="secondary" className="flex-shrink-0">
          {sessions.length} {sessions.length === 1 ? "session" : "sessions"}
        </Badge>
      </div>

      <div className="mt-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : isError ? (
          <div className="text-sm text-destructive">
            Failed to load sessions:{" "}
            {(error as any)?.response?.data?.detail ||
              (error as any)?.message ||
              "unknown error"}
          </div>
        ) : sessions.length === 0 ? (
          <div className="rounded-md border border-dashed py-6 text-center text-sm text-muted-foreground">
            {isAdmin
              ? "No users have authenticated to this server yet."
              : "You haven't authenticated to this server yet."}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Authenticated as</TableHead>
                <TableHead>Last updated</TableHead>
                <TableHead>Expires</TableHead>
                <TableHead className="w-[1%]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((session) => (
                <SessionRow
                  key={session.user_id}
                  session={session}
                  isAdmin={isAdmin}
                  onRevoke={() => handleRevoke(session)}
                  isRevoking={
                    revokeMutation.isPending &&
                    revokeMutation.variables?.userId === session.user_id
                  }
                />
              ))}
            </TableBody>
          </Table>
        )}
      </div>
    </Card>
  );
}

interface SessionRowProps {
  session: MCPServerSession;
  isAdmin: boolean;
  onRevoke: () => void;
  isRevoking: boolean;
}

function SessionRow({ session, isAdmin, onRevoke, isRevoking }: SessionRowProps) {
  // Display name resolution — prefer the local user's full name/username,
  // fall back to provider-side identity (e.g. Outreach), and finally to
  // the raw user_id (which is `__system__` for shared rows).
  const displayName = session.is_system
    ? "Shared system account"
    : session.full_name ||
      session.username ||
      session.provider_name ||
      session.email ||
      session.provider_email ||
      session.user_id;

  const email = session.email || session.provider_email || null;

  // A non-admin can only revoke their own session. An admin can revoke
  // anyone, including the `__system__` row.
  const canRevoke = isAdmin || session.is_current_user;

  const formatDate = (iso?: string | null) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  // Highlight expired tokens — they still need cleanup, but the UI should
  // surface that the row isn't actually granting access anymore.
  const isExpired =
    !!session.expires_at && new Date(session.expires_at).getTime() < Date.now();

  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-2">
          <span className="font-medium">{displayName}</span>
          {session.is_current_user && (
            <Badge variant="outline" className="text-xs">
              You
            </Badge>
          )}
          {session.is_system && (
            <Badge variant="secondary" className="text-xs">
              System
            </Badge>
          )}
        </div>
      </TableCell>
      <TableCell className="text-muted-foreground">{email || "—"}</TableCell>
      <TableCell className="text-muted-foreground">
        {session.provider_email || session.provider_name || "—"}
      </TableCell>
      <TableCell className="text-muted-foreground text-sm">
        {formatDate(session.updated_at)}
      </TableCell>
      <TableCell className="text-sm">
        {session.expires_at ? (
          <span
            className={
              isExpired ? "text-destructive font-medium" : "text-muted-foreground"
            }
            title={session.expires_at}
          >
            {isExpired ? "Expired" : formatDate(session.expires_at)}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell>
        <Button
          variant="destructive"
          size="sm"
          onClick={onRevoke}
          disabled={!canRevoke || isRevoking}
          title={
            !canRevoke
              ? "Only administrators can revoke other users' sessions"
              : session.is_current_user
                ? "Sign yourself out"
                : session.is_system
                  ? "Revoke the shared system session (signs all users out)"
                  : "Revoke this user's session"
          }
        >
          {isRevoking ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <>
              <LogOut className="mr-1 h-4 w-4" />
              {session.is_current_user ? "Sign out" : "Disconnect"}
            </>
          )}
        </Button>
      </TableCell>
    </TableRow>
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

  // Used to gate system-mode-only controls (Logout, Connect popup) so
  // non-admins can't accidentally affect every user's shared session.
  const isAdmin = useAuthStore((s) => s.user?.is_superadmin ?? false);
  const isSystemMode = server.oauth_mode === "system";

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
            {/* For OAuth servers, the badge reflects *this user's* state.
                For other servers it falls back to the global status. */}
            <StatusBadge status={server.current_user_status || server.status} />
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
            {/* OAuth scope badge: who shares this server's identity. */}
            {server.auth_type === "oauth" && (
              <Badge
                variant="outline"
                className="text-xs"
                title={
                  server.oauth_mode === "system"
                    ? "Shared system account — one OAuth token used by all users (admin-managed)."
                    : "Each user signs in with their own identity."
                }
              >
                {server.oauth_mode === "system" ? "Shared" : "Per-user"}
              </Badge>
            )}
            {server.auth_type === "oauth" && server.current_user_status === "connected" && (
              <Badge variant="outline" className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-green-600" />
                {server.oauth_mode === "system" ? "Connected" : "Signed in"}
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
          {server.auth_type === "oauth" && server.current_user_status === "connected" && (
            // Logout in system-mode revokes the shared token for everyone,
            // so only admins see the button there. In user-mode every
            // signed-in user can sign themselves out.
            (!isSystemMode || isAdmin) && (
              <Button
                variant="outline"
                size="sm"
                onClick={onLogout}
                disabled={isLoggingOut}
                title={
                  isSystemMode
                    ? "Sign all users out (admin)"
                    : "Sign out (only affects you)"
                }
              >
                {isLoggingOut ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <LogOut className="h-4 w-4" />
                )}
              </Button>
            )
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
  const isAdmin = useAuthStore((s) => s.user?.is_superadmin ?? false);
  const isEditing = !!server;

  const [formData, setFormData] = useState<MCPServerCreate>(() => ({
    name: server?.name || "",
    description: server?.description || "",
    protocol: "http", // Always HTTP now
    url: server?.url || "",
    headers: server?.headers || {},
    auth_type: server?.auth_type || "none",
    oauth_mode: server?.oauth_mode || "user",
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
        oauth_mode: server?.oauth_mode || "user",
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
                {/* OAuth scope mode: per-user vs shared system token.
                    Locked at creation — read-only when editing. The
                    'system' option is admin-only because it grants every
                    user access to a single shared identity. */}
                <div className="space-y-2 rounded-md border p-3">
                  <Label className="text-sm font-semibold">OAuth scope</Label>
                  <p className="text-xs text-muted-foreground">
                    {isEditing
                      ? "Locked at creation. Recreate the server to change the OAuth scope."
                      : "How users will authenticate with this server."}
                  </p>
                  <div className="flex flex-col gap-2 pt-1">
                    <label className="flex items-start gap-2 text-sm">
                      <input
                        type="radio"
                        name="oauth_mode"
                        value="user"
                        className="mt-1"
                        checked={(formData.oauth_mode || "user") === "user"}
                        disabled={isEditing}
                        onChange={() =>
                          setFormData({ ...formData, oauth_mode: "user" })
                        }
                      />
                      <span>
                        <strong>Each user signs in</strong>
                        <span className="block text-xs text-muted-foreground">
                          Per-user tokens. Each user authenticates with
                          their own identity. Recommended.
                        </span>
                      </span>
                    </label>
                    <label
                      className={`flex items-start gap-2 text-sm ${
                        !isAdmin ? "opacity-50" : ""
                      }`}
                      title={
                        !isAdmin
                          ? "Only administrators can create system-mode servers"
                          : undefined
                      }
                    >
                      <input
                        type="radio"
                        name="oauth_mode"
                        value="system"
                        className="mt-1"
                        checked={(formData.oauth_mode || "user") === "system"}
                        disabled={isEditing || !isAdmin}
                        onChange={() =>
                          setFormData({ ...formData, oauth_mode: "system" })
                        }
                      />
                      <span>
                        <strong>Shared system account</strong>{" "}
                        <Badge variant="outline" className="ml-1 align-middle text-xs">
                          Admin only
                        </Badge>
                        <span className="block text-xs text-muted-foreground">
                          One admin authenticates once; the resulting
                          token is shared across all users.
                        </span>
                      </span>
                    </label>
                  </div>
                </div>

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
