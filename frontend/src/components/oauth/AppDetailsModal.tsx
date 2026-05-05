'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Copy, Check, TrendingUp, Clock, AlertTriangle, Edit, Save, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Checkbox } from '@/components/ui/checkbox';
import { useToast } from '@/hooks/use-toast';
import { oauthAppsApi, OAuthApp, OAuthScope } from '@/lib/api/oauth-apps';
import { formatDistanceToNow } from 'date-fns';
import { ApiEndpointReference } from './ApiEndpointReference';

interface AppDetailsModalProps {
  app: OAuthApp;
  open: boolean;
  onClose: () => void;
}

export function AppDetailsModal({ app, open, onClose }: AppDetailsModalProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [copiedClientId, setCopiedClientId] = useState(false);
  const [editingScopes, setEditingScopes] = useState(false);
  const [selectedScopes, setSelectedScopes] = useState<string[]>(app.scopes);

  const { data: usage } = useQuery({
    queryKey: ['oauth-app-usage', app.id],
    queryFn: () => oauthAppsApi.getUsage(app.id),
    enabled: open,
  });

  const { data: availableScopes = [] } = useQuery({
    queryKey: ['oauth-scopes'],
    queryFn: oauthAppsApi.listScopes,
    enabled: open && editingScopes,
  });

  const updateScopesMutation = useMutation({
    mutationFn: (scopes: string[]) => oauthAppsApi.update(app.id, { scopes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oauth-apps'] });
      queryClient.invalidateQueries({ queryKey: ['oauth-app', app.id] });
      setEditingScopes(false);
      toast({
        title: 'Scopes updated',
        description: 'OAuth application scopes have been updated successfully.',
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Failed to update scopes',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  const handleCopyClientId = () => {
    navigator.clipboard.writeText(app.client_id);
    setCopiedClientId(true);
    setTimeout(() => setCopiedClientId(false), 2000);
  };

  const handleSaveScopes = () => {
    if (selectedScopes.length === 0) {
      toast({
        title: 'Scopes required',
        description: 'Please select at least one scope.',
        variant: 'destructive',
      });
      return;
    }
    updateScopesMutation.mutate(selectedScopes);
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  const groupedScopes = availableScopes.reduce((acc, scope) => {
    if (!acc[scope.resource_type]) {
      acc[scope.resource_type] = [];
    }
    acc[scope.resource_type].push(scope);
    return acc;
  }, {} as Record<string, OAuthScope[]>);

  const baseUrl = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
  const apiUrl = baseUrl.replace(':3000', ':5055');

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{app.name}</DialogTitle>
          <DialogDescription>{app.description || 'No description'}</DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="usage">Usage</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
            <TabsTrigger value="api">API Reference</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <div className="grid gap-4">
              <div className="space-y-2">
                <div className="text-sm font-medium text-muted-foreground">
                  Client ID
                </div>
                <div className="flex items-center gap-2">
                  <code className="flex-1 bg-muted px-3 py-2 rounded text-sm">
                    {app.client_id}
                  </code>
                  <Button variant="outline" size="sm" onClick={handleCopyClientId}>
                    {copiedClientId ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium text-muted-foreground">Scopes</div>
                  {!editingScopes ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedScopes(app.scopes);
                        setEditingScopes(true);
                      }}
                    >
                      <Edit className="h-3 w-3 mr-1" />
                      Edit
                    </Button>
                  ) : (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEditingScopes(false)}
                      >
                        <X className="h-3 w-3 mr-1" />
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={handleSaveScopes}
                        disabled={updateScopesMutation.isPending}
                      >
                        <Save className="h-3 w-3 mr-1" />
                        Save
                      </Button>
                    </div>
                  )}
                </div>

                {!editingScopes ? (
                  <div className="flex flex-wrap gap-2">
                    {app.scopes.map((scope) => (
                      <Badge key={scope} variant="outline">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <div className="border rounded-lg p-4 max-h-64 overflow-y-auto">
                    {Object.entries(groupedScopes).map(([resourceType, resourceScopes]) => (
                      <div key={resourceType} className="mb-4 last:mb-0">
                        <div className="font-medium text-sm mb-2 capitalize">
                          {resourceType === 'all' ? 'Administrative' : `${resourceType}s`}
                        </div>
                        <div className="space-y-2">
                          {resourceScopes.map((scope) => (
                            <div key={scope.scope} className="flex items-start gap-3">
                              <Checkbox
                                id={scope.scope}
                                checked={selectedScopes.includes(scope.scope)}
                                onCheckedChange={() => toggleScope(scope.scope)}
                                disabled={scope.is_system_only}
                              />
                              <div className="flex-1">
                                <label
                                  htmlFor={scope.scope}
                                  className="text-sm cursor-pointer"
                                >
                                  <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                                    {scope.scope}
                                  </code>
                                  {scope.is_system_only && (
                                    <Badge variant="outline" className="ml-2 text-xs">
                                      System Only
                                    </Badge>
                                  )}
                                </label>
                                {scope.description && (
                                  <p className="text-xs text-muted-foreground mt-1">
                                    {scope.description}
                                  </p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium text-muted-foreground">Status</div>
                <Badge variant={app.status === 'active' ? 'default' : 'secondary'}>
                  {app.status}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">
                    Created
                  </div>
                  <div className="text-sm">
                    {formatDistanceToNow(new Date(app.created), {
                      addSuffix: true,
                    })}
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">
                    Last Used
                  </div>
                  <div className="text-sm">
                    {app.last_used_at
                      ? formatDistanceToNow(new Date(app.last_used_at), {
                          addSuffix: true,
                        })
                      : 'Never'}
                  </div>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="usage" className="space-y-6">
            {usage ? (
              <>
                <div className="grid grid-cols-3 gap-4">
                  <div className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <TrendingUp className="h-4 w-4" />
                      <span className="text-sm">Total Requests</span>
                    </div>
                    <div className="text-2xl font-bold">
                      {usage.total_requests?.toLocaleString() || 0}
                    </div>
                  </div>

                  <div className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Clock className="h-4 w-4" />
                      <span className="text-sm">Avg Response Time</span>
                    </div>
                    <div className="text-2xl font-bold">
                      {usage.avg_response_time_ms || 0}ms
                    </div>
                  </div>

                  <div className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <AlertTriangle className="h-4 w-4" />
                      <span className="text-sm">Error Rate</span>
                    </div>
                    <div className="text-2xl font-bold">
                      {((usage.error_rate || 0) * 100).toFixed(2)}%
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="text-sm font-medium">Last 24 Hours</div>
                  <div className="border rounded-lg">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Hour</TableHead>
                          <TableHead className="text-right">Requests</TableHead>
                          <TableHead className="text-right">Errors</TableHead>
                          <TableHead className="text-right">Avg Time</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {usage?.last_24h?.length ? (
                          usage.last_24h.map((hour) => (
                            <TableRow key={hour.hour}>
                              <TableCell className="font-mono text-xs">
                                {hour.hour}
                              </TableCell>
                              <TableCell className="text-right">
                                {hour.requests}
                              </TableCell>
                              <TableCell className="text-right">{hour.errors}</TableCell>
                              <TableCell className="text-right">
                                {hour.avg_response_time_ms}ms
                              </TableCell>
                            </TableRow>
                          ))
                        ) : (
                          <TableRow>
                            <TableCell colSpan={4} className="text-center text-muted-foreground">
                              No usage data available
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center h-64 text-muted-foreground">
                Loading usage statistics...
              </div>
            )}
          </TabsContent>

          <TabsContent value="settings" className="space-y-6">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">
                    Rate Limit (Hourly)
                  </div>
                  <div className="text-2xl font-bold">
                    {app.rate_limit_per_hour.toLocaleString()} req/hr
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-medium text-muted-foreground">
                    Rate Limit (Daily)
                  </div>
                  <div className="text-2xl font-bold">
                    {app.rate_limit_per_day.toLocaleString()} req/day
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium text-muted-foreground">
                  Token Expiry
                </div>
                <div className="text-2xl font-bold">
                  {app.token_expiry_seconds} seconds
                </div>
                <div className="text-sm text-muted-foreground">
                  ({Math.floor(app.token_expiry_seconds / 60)} minutes)
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="api" className="space-y-6">
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold mb-2">API Reference</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Complete reference of all available endpoints based on your selected scopes.
                  Click on any endpoint to view detailed request/response schemas and examples.
                </p>
              </div>

              <ApiEndpointReference scopes={app.scopes} apiUrl={apiUrl} />

              <div className="border-t pt-4">
                <h4 className="text-sm font-semibold mb-2">Additional Resources</h4>
                <ul className="space-y-2 text-sm">
                  <li>
                    <a
                      href={`${apiUrl}/api/docs`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Interactive API Documentation (Swagger UI)
                    </a>
                  </li>
                  <li>
                    <a
                      href={`${apiUrl}/api/redoc`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      API Documentation (ReDoc)
                    </a>
                  </li>
                  <li>
                    <a
                      href={`${apiUrl}/api/openapi.json`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      OpenAPI Specification (JSON)
                    </a>
                  </li>
                </ul>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
