"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { hanaConnectionsApi, type HANAConnection, type HANAConnectionCreate } from "@/lib/api/hana-connections";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Database, Plus, Pencil, Trash2, CheckCircle, XCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { SettingsHeader } from "@/components/settings/settings-header";

export default function HANAConnectionsPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingConnection, setEditingConnection] = useState<HANAConnection | null>(null);
  const queryClient = useQueryClient();

  // Fetch connections
  const { data: connections, isLoading } = useQuery({
    queryKey: ["hana-connections"],
    queryFn: hanaConnectionsApi.list,
  });

  // Create mutation
  const createMutation = useMutation({
    mutationFn: hanaConnectionsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hana-connections"] });
      setDialogOpen(false);
      toast.success("Connection created successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to create connection");
    },
  });

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      hanaConnectionsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hana-connections"] });
      setDialogOpen(false);
      setEditingConnection(null);
      toast.success("Connection updated successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to update connection");
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: hanaConnectionsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["hana-connections"] });
      toast.success("Connection deleted successfully");
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to delete connection");
    },
  });

  // Test mutation
  const testMutation = useMutation({
    mutationFn: hanaConnectionsApi.test,
    onSuccess: (data) => {
      if (data.success) {
        toast.success(`Connection successful! ${data.server_version || ""} (${data.latency_ms}ms)`);
      } else {
        toast.error(data.message);
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || "Failed to test connection");
    },
  });

  const handleOpenDialog = (connection?: HANAConnection) => {
    setEditingConnection(connection || null);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingConnection(null);
  };

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="HANA Connections"
        description="Manage saved HANA database connections for reuse across sources"
      />

      {/* Connection Dialog in Header */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogTrigger asChild>
          <Button onClick={() => handleOpenDialog()}>
            <Plus className="w-4 h-4 mr-2" />
            Add Connection
          </Button>
        </DialogTrigger>
        <ConnectionDialog
            connection={editingConnection}
            onSubmit={(data) => {
              if (editingConnection) {
                updateMutation.mutate({ id: editingConnection.id, data });
              } else {
                createMutation.mutate(data);
              }
            }}
            onCancel={handleCloseDialog}
            isSubmitting={createMutation.isPending || updateMutation.isPending}
          />
      </Dialog>

      {/* Connections List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <Skeleton className="h-6 w-48 mb-2" />
                <Skeleton className="h-4 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : connections && connections.length > 0 ? (
        <div className="grid gap-4">
          {connections.map((connection) => (
            <Card key={connection.id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-100 dark:bg-blue-900 rounded-lg">
                      <Database className="w-5 h-5 text-blue-600 dark:text-blue-300" />
                    </div>
                    <div>
                      <CardTitle>{connection.name}</CardTitle>
                      <CardDescription className="mt-1">
                        {connection.description || "No description"}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => testMutation.mutate(connection.id)}
                      disabled={testMutation.isPending}
                    >
                      {testMutation.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        "Test"
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleOpenDialog(connection)}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Connection</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete "{connection.name}"? This will not
                            affect existing sources using this connection.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => deleteMutation.mutate(connection.id)}
                            className="bg-red-600 hover:bg-red-700"
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                  <div className="md:col-span-2 lg:col-span-1">
                    <div className="text-gray-500 dark:text-gray-400 text-xs mb-1">Host</div>
                    <div className="font-mono text-sm break-all">{connection.host}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 dark:text-gray-400 text-xs mb-1">Port</div>
                    <div className="font-medium">{connection.port}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 dark:text-gray-400 text-xs mb-1">Database</div>
                    <div className="font-medium truncate">{connection.database}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 dark:text-gray-400 text-xs mb-1">User</div>
                    <div className="font-medium truncate">{connection.user}</div>
                  </div>
                  {connection.schema && (
                    <div>
                      <div className="text-gray-500 dark:text-gray-400 text-xs mb-1">Schema</div>
                      <div className="font-medium truncate">{connection.schema}</div>
                    </div>
                  )}
                  <div>
                    <div className="text-gray-500 dark:text-gray-400 text-xs mb-1">Encryption</div>
                    <Badge variant={connection.encrypt ? "default" : "secondary"}>
                      {connection.encrypt ? "Enabled" : "Disabled"}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Database className="w-12 h-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-medium mb-2">No HANA Connections</h3>
            <p className="text-gray-500 dark:text-gray-400 text-center mb-4">
              Create a connection to reuse it across multiple HANA table sources
            </p>
            <Button onClick={() => handleOpenDialog()}>
              <Plus className="w-4 h-4 mr-2" />
              Add Your First Connection
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Connection Dialog Component
function ConnectionDialog({
  connection,
  onSubmit,
  onCancel,
  isSubmitting,
}: {
  connection: HANAConnection | null;
  onSubmit: (data: HANAConnectionCreate) => void;
  onCancel: () => void;
  isSubmitting: boolean;
}) {
  const [formData, setFormData] = useState<HANAConnectionCreate>({
    name: connection?.name || "",
    host: connection?.host || "",
    port: connection?.port || 443,
    database: connection?.database || "",
    user: connection?.user || "",
    password: "",
    encrypt: connection?.encrypt ?? true,
    schema: connection?.schema || "",
    description: connection?.description || "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
      <DialogHeader>
        <DialogTitle>{connection ? "Edit Connection" : "Add HANA Connection"}</DialogTitle>
        <DialogDescription>
          {connection
            ? "Update connection details. Leave password empty to keep current password."
            : "Create a new HANA database connection that can be reused across sources."}
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Label htmlFor="name">Connection Name *</Label>
            <Input
              id="name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Production HANA"
              required
            />
          </div>

          <div className="col-span-2 md:col-span-1">
            <Label htmlFor="host">Host *</Label>
            <Input
              id="host"
              value={formData.host}
              onChange={(e) => setFormData({ ...formData, host: e.target.value })}
              placeholder="example.hanacloud.ondemand.com"
              required
            />
          </div>

          <div className="col-span-2 md:col-span-1">
            <Label htmlFor="port">Port *</Label>
            <Input
              id="port"
              type="number"
              value={formData.port}
              onChange={(e) => setFormData({ ...formData, port: parseInt(e.target.value) })}
              placeholder="443"
              required
            />
          </div>

          <div className="col-span-2 md:col-span-1">
            <Label htmlFor="database">Database *</Label>
            <Input
              id="database"
              value={formData.database}
              onChange={(e) => setFormData({ ...formData, database: e.target.value })}
              placeholder="SYSTEMDB"
              required
            />
          </div>

          <div className="col-span-2 md:col-span-1">
            <Label htmlFor="schema">Default Schema</Label>
            <Input
              id="schema"
              value={formData.schema}
              onChange={(e) => setFormData({ ...formData, schema: e.target.value })}
              placeholder="Optional"
            />
          </div>

          <div className="col-span-2 md:col-span-1">
            <Label htmlFor="user">Username *</Label>
            <Input
              id="user"
              value={formData.user}
              onChange={(e) => setFormData({ ...formData, user: e.target.value })}
              placeholder="DBADMIN"
              required
            />
          </div>

          <div className="col-span-2 md:col-span-1">
            <Label htmlFor="password">
              Password {connection ? "(leave empty to keep current)" : "*"}
            </Label>
            <Input
              id="password"
              type="password"
              value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              placeholder={connection ? "••••••••" : "Enter password"}
              required={!connection}
            />
          </div>

          <div className="col-span-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Optional description"
              rows={2}
            />
          </div>

          <div className="col-span-2 flex items-center space-x-2">
            <Switch
              id="encrypt"
              checked={formData.encrypt}
              onCheckedChange={(checked) => setFormData({ ...formData, encrypt: checked })}
            />
            <Label htmlFor="encrypt" className="cursor-pointer">
              Use encrypted connection (SSL/TLS)
            </Label>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>{connection ? "Update" : "Create"} Connection</>
            )}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}
