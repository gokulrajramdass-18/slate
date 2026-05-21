import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Database, Settings, Trash2, TestTube, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog";
import { apiConnectionsApi } from "@/lib/api/api-connections";
import { toast } from "sonner";
import { SettingsHeader } from "@/components/settings/settings-header";

export default function SettingsApiConnectionsPage() {
  const queryClient = useQueryClient();
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingConnection, setEditingConnection] = useState<any | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<any | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    endpoint: "",
    auth_type: "none",
    method: "GET",
    headers: "{}",
    query_params: "{}",
    request_body: "",
    data_path: "",
    id_field: "id",
    content_fields: "[]",
    auth_config: "{}",
  });

  // Fetch connections
  const { data: connections, isLoading } = useQuery({
    queryKey: ["api-connections"],
    queryFn: apiConnectionsApi.list,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      return await apiConnectionsApi.create({
        ...data,
        headers: JSON.parse(data.headers || "{}"),
        query_params: JSON.parse(data.query_params || "{}"),
        request_body: data.request_body ? JSON.parse(data.request_body) : null,
        content_fields: JSON.parse(data.content_fields || "[]"),
        auth_config: JSON.parse(data.auth_config || "{}"),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-connections"] });
      setIsCreateOpen(false);
      resetForm();
      toast.success("API connection created successfully");
    },
    onError: (error: any) => {
      toast.error(error.message || "Failed to create connection");
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: any) => {
      return await apiConnectionsApi.update(id, {
        ...data,
        headers: JSON.parse(data.headers || "{}"),
        query_params: JSON.parse(data.query_params || "{}"),
        request_body: data.request_body ? JSON.parse(data.request_body) : null,
        content_fields: JSON.parse(data.content_fields || "[]"),
        auth_config: JSON.parse(data.auth_config || "{}"),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-connections"] });
      setEditingConnection(null);
      resetForm();
      toast.success("API connection updated successfully");
    },
    onError: (error: any) => {
      toast.error(error.message || "Failed to update connection");
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: apiConnectionsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-connections"] });
      toast.success("API connection deleted successfully");
    },
    onError: (error: any) => {
      toast.error(error.message || "Failed to delete connection");
    },
  });

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
    } finally {
      setTestingId(null);
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      description: "",
      endpoint: "",
      auth_type: "none",
      method: "GET",
      headers: "{}",
      query_params: "{}",
      request_body: "",
      data_path: "",
      id_field: "id",
      content_fields: "[]",
      auth_config: "{}",
    });
  };

  const handleEdit = (connection: any) => {
    setFormData({
      name: connection.name,
      description: connection.description || "",
      endpoint: connection.endpoint,
      auth_type: connection.auth_type,
      method: connection.method,
      headers: JSON.stringify(connection.headers, null, 2),
      query_params: JSON.stringify(connection.query_params, null, 2),
      request_body: connection.request_body ? JSON.stringify(connection.request_body, null, 2) : "",
      data_path: connection.data_path || "",
      id_field: connection.id_field,
      content_fields: JSON.stringify(connection.content_fields, null, 2),
      auth_config: "{}",
    });
    setEditingConnection(connection);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (editingConnection) {
      updateMutation.mutate({ id: editingConnection.id, data: formData });
    } else {
      createMutation.mutate(formData);
    }
  };

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="API Connections"
        description="Manage reusable API connection configurations"
      />

      <Dialog open={isCreateOpen || !!editingConnection} onOpenChange={(open) => {
          if (!open) {
            setIsCreateOpen(false);
            setEditingConnection(null);
            resetForm();
          } else {
            setIsCreateOpen(true);
          }
        }}>
        <DialogTrigger asChild>
          <Button>
            <Plus className="w-4 h-4 mr-2" />
            New Connection
          </Button>
        </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingConnection ? "Edit" : "Create"} API Connection</DialogTitle>
              <DialogDescription>
                Configure a reusable API connection for easy source creation
              </DialogDescription>
            </DialogHeader>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Basic Info */}
              <div className="space-y-2">
                <Label htmlFor="name">Connection Name *</Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="My API Connection"
                  required
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Description of this connection"
                />
              </div>

              {/* Endpoint */}
              <div className="space-y-2">
                <Label htmlFor="endpoint">Endpoint URL *</Label>
                <Input
                  id="endpoint"
                  value={formData.endpoint}
                  onChange={(e) => setFormData({ ...formData, endpoint: e.target.value })}
                  placeholder="https://api.example.com/data"
                  required
                />
              </div>

              {/* Method */}
              <div className="space-y-2">
                <Label htmlFor="method">HTTP Method</Label>
                <Select value={formData.method} onValueChange={(value) => setFormData({ ...formData, method: value })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                    <SelectItem value="GET">GET</SelectItem>
                    <SelectItem value="POST">POST</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Authentication */}
              <div className="space-y-2">
                <Label htmlFor="auth_type">Authentication Type</Label>
                <Select value={formData.auth_type} onValueChange={(value) => setFormData({ ...formData, auth_type: value })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                    <SelectItem value="none">None</SelectItem>
                    <SelectItem value="bearer">Bearer Token</SelectItem>
                    <SelectItem value="api_key">API Key</SelectItem>
                    <SelectItem value="basic">Basic Auth</SelectItem>
                    <SelectItem value="client_credentials">Client Credentials (OAuth 2.0)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {formData.auth_type === "client_credentials" ? (
                <ClientCredentialsForm
                  value={formData.auth_config}
                  onChange={(next) => setFormData({ ...formData, auth_config: next })}
                />
              ) : formData.auth_type !== "none" && (
                <div className="space-y-2">
                  <Label htmlFor="auth_config">Auth Config (JSON)</Label>
                  <Textarea
                    id="auth_config"
                    value={formData.auth_config}
                    onChange={(e) => setFormData({ ...formData, auth_config: e.target.value })}
                    placeholder='{"token": "your-token"} or {"key": "api-key", "value": "key-value", "location": "header"}'
                    rows={3}
                  />
                </div>
              )}

              {/* Headers */}
              <div className="space-y-2">
                <Label htmlFor="headers">Headers (JSON)</Label>
                <Textarea
                  id="headers"
                  value={formData.headers}
                  onChange={(e) => setFormData({ ...formData, headers: e.target.value })}
                  placeholder='{"Content-Type": "application/json"}'
                  rows={3}
                />
              </div>

              {/* Query Params */}
              <div className="space-y-2">
                <Label htmlFor="query_params">Query Parameters (JSON)</Label>
                <Textarea
                  id="query_params"
                  value={formData.query_params}
                  onChange={(e) => setFormData({ ...formData, query_params: e.target.value })}
                  placeholder='{"limit": 100}'
                  rows={2}
                />
              </div>

              {/* Request Body (for POST) */}
              {formData.method === "POST" && (
                <div className="space-y-2">
                  <Label htmlFor="request_body">Request Body (JSON)</Label>
                  <Textarea
                    id="request_body"
                    value={formData.request_body}
                    onChange={(e) => setFormData({ ...formData, request_body: e.target.value })}
                    placeholder='{"query": "..."}'
                    rows={3}
                  />
                </div>
              )}

              {/* Data Extraction */}
              <div className="space-y-2">
                <Label htmlFor="data_path">Data Path (JSONPath)</Label>
                <Input
                  id="data_path"
                  value={formData.data_path}
                  onChange={(e) => setFormData({ ...formData, data_path: e.target.value })}
                  placeholder="data.items (leave empty if root is array)"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="id_field">ID Field</Label>
                  <Input
                    id="id_field"
                    value={formData.id_field}
                    onChange={(e) => setFormData({ ...formData, id_field: e.target.value })}
                    placeholder="id"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="content_fields">Content Fields (JSON Array)</Label>
                  <Input
                    id="content_fields"
                    value={formData.content_fields}
                    onChange={(e) => setFormData({ ...formData, content_fields: e.target.value })}
                    placeholder='["title", "description"]'
                  />
                </div>
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setIsCreateOpen(false);
                    setEditingConnection(null);
                    resetForm();
                  }}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                  {(createMutation.isPending || updateMutation.isPending) && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingConnection ? "Update" : "Create"}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>

      {/* Connections List */}
      {isLoading ? (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
              <p className="text-sm text-gray-500">Loading connections...</p>
            </div>
          </CardContent>
        </Card>
      ) : connections && connections.length > 0 ? (
        <div className="grid gap-4">
          {connections.map((connection: any) => (
            <Card key={connection.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="flex items-center gap-2">
                      <Database className="h-5 w-5" />
                      {connection.name}
                    </CardTitle>
                    <CardDescription className="mt-1">{connection.description || connection.endpoint}</CardDescription>
                    <div className="flex flex-wrap gap-2 mt-3">
                      <span className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
                        {connection.method}
                      </span>
                      <span className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 px-2 py-1 rounded">
                        {connection.auth_type}
                      </span>
                      {connection.test_status && (
                        <span className={`text-xs px-2 py-1 rounded flex items-center gap-1 ${
                          connection.test_status === "success"
                            ? "bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200"
                            : "bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200"
                        }`}>
                          {connection.test_status === "success" ? (
                            <CheckCircle className="h-3 w-3" />
                          ) : (
                            <XCircle className="h-3 w-3" />
                          )}
                          {connection.test_status}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleTest(connection.id)}
                      disabled={testingId === connection.id}
                    >
                      {testingId === connection.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <TestTube className="h-4 w-4" />
                      )}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleEdit(connection)}>
                      <Settings className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (confirm("Are you sure you want to delete this connection?")) {
                          deleteMutation.mutate(connection.id);
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-red-600" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="py-12">
            <div className="text-center">
              <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500 mb-4">No API connections configured</p>
              <Button onClick={() => setIsCreateOpen(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create First Connection
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Test Result */}
      {testResult && (
        <Card className={testResult.success ? "border-green-500" : "border-red-500"}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {testResult.success ? (
                <CheckCircle className="h-5 w-5 text-green-600" />
              ) : (
                <XCircle className="h-5 w-5 text-red-600" />
              )}
              Test Result
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm mb-4">{testResult.message}</p>
            {testResult.preview && (
              <pre className="text-xs bg-gray-50 dark:bg-gray-900 p-4 rounded overflow-auto max-h-64">
                {JSON.stringify(testResult.preview, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ============================================================================
// Client Credentials Sub-Form
// ============================================================================

interface ClientCredentialsFormProps {
  /** JSON string holding {token_url, client_id, client_secret, scope, audience} */
  value: string;
  onChange: (next: string) => void;
}

function ClientCredentialsForm({ value, onChange }: ClientCredentialsFormProps) {
  let parsed: Record<string, string> = {};
  try {
    parsed = JSON.parse(value || "{}") || {};
  } catch {
    parsed = {};
  }

  const update = (key: string, val: string) => {
    const next = { ...parsed, [key]: val };
    // Strip empty optional fields so we don't send '' for scope/audience
    if (!val) delete next[key];
    onChange(JSON.stringify(next));
  };

  return (
    <div className="space-y-3 rounded-md border border-gray-200 dark:border-gray-800 p-3">
      <div className="space-y-2">
        <Label htmlFor="cc-token-url">Token URL *</Label>
        <Input
          id="cc-token-url"
          value={parsed.token_url || ""}
          onChange={(e) => update("token_url", e.target.value)}
          placeholder="https://auth.example.com/oauth/token"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="cc-client-id">Client ID *</Label>
          <Input
            id="cc-client-id"
            value={parsed.client_id || ""}
            onChange={(e) => update("client_id", e.target.value)}
            autoComplete="off"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cc-client-secret">Client Secret *</Label>
          <Input
            id="cc-client-secret"
            type="password"
            value={parsed.client_secret || ""}
            onChange={(e) => update("client_secret", e.target.value)}
            autoComplete="off"
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="cc-scope">Scope (optional)</Label>
          <Input
            id="cc-scope"
            value={parsed.scope || ""}
            onChange={(e) => update("scope", e.target.value)}
            placeholder="read:data write:data"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cc-audience">Audience (optional)</Label>
          <Input
            id="cc-audience"
            value={parsed.audience || ""}
            onChange={(e) => update("audience", e.target.value)}
            placeholder="https://api.example.com"
          />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        At execution time, Slate exchanges these credentials for an access token at the
        token URL and sends it as <code className="font-mono">Authorization: Bearer ...</code>.
      </p>
    </div>
  );
}
