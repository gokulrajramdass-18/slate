import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, RefreshCw, Eye, Key } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { useToast } from '@/hooks/use-toast';
import { oauthAppsApi, OAuthApp } from '@/lib/api/oauth-apps';
import { CreateAppModal } from '@/components/oauth/CreateAppModal';
import { ClientSecretModal } from '@/components/oauth/ClientSecretModal';
import { AppDetailsModal } from '@/components/oauth/AppDetailsModal';
import { formatDistanceToNow } from 'date-fns';

export default function SettingsOAuthAppsPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedApp, setSelectedApp] = useState<OAuthApp | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [deleteAppId, setDeleteAppId] = useState<string | null>(null);

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ['oauth-apps'],
    queryFn: oauthAppsApi.list,
  });

  const deleteMutation = useMutation({
    mutationFn: oauthAppsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oauth-apps'] });
      toast({
        title: 'Application deleted',
        description: 'OAuth application has been deleted successfully.',
      });
      setDeleteAppId(null);
    },
    onError: (error: Error) => {
      toast({
        title: 'Failed to delete application',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  const regenerateSecretMutation = useMutation({
    mutationFn: oauthAppsApi.regenerateSecret,
    onSuccess: (data) => {
      setClientSecret(data.client_secret);
      queryClient.invalidateQueries({ queryKey: ['oauth-apps'] });
      toast({
        title: 'Secret regenerated',
        description: 'A new client secret has been generated. Make sure to copy it now.',
      });
    },
    onError: (error: Error) => {
      toast({
        title: 'Failed to regenerate secret',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  const handleViewDetails = (app: OAuthApp) => {
    setSelectedApp(app);
    setShowDetailsModal(true);
  };

  const handleRegenerateSecret = (appId: string) => {
    regenerateSecretMutation.mutate(appId);
  };

  const handleDelete = (appId: string) => {
    setDeleteAppId(appId);
  };

  const confirmDelete = () => {
    if (deleteAppId) {
      deleteMutation.mutate(deleteAppId);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading OAuth applications...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">OAuth Applications</h1>
          <p className="text-muted-foreground mt-2">
            Manage API access for external applications
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Application
        </Button>
      </div>

      {apps.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 border border-dashed rounded-lg">
          <Key className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">No OAuth applications</h3>
          <p className="text-muted-foreground mb-4">
            Create your first OAuth application to get started
          </p>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create Application
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Client ID</TableHead>
                <TableHead>Grant Type</TableHead>
                <TableHead>Scopes</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Used</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {apps.map((app) => (
                <TableRow
                  key={app.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => handleViewDetails(app)}
                >
                  <TableCell>
                    <div>
                      <div className="font-medium">{app.name}</div>
                      {app.description && (
                        <div className="text-sm text-muted-foreground">
                          {app.description}
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs bg-muted px-2 py-1 rounded">
                      {app.client_id}
                    </code>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {(() => {
                        const grantTypes = Array.isArray(app.grant_types)
                          ? app.grant_types
                          : JSON.parse(app.grant_types || '["client_credentials"]');

                        return grantTypes.map((grant: string) => (
                          <Badge
                            key={grant}
                            variant={grant === 'authorization_code' ? 'default' : 'secondary'}
                            className="text-xs"
                          >
                            {grant === 'client_credentials' ? 'Client Credentials' : 'Authorization Code'}
                          </Badge>
                        ));
                      })()}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {app.scopes.slice(0, 3).map((scope) => (
                        <Badge key={scope} variant="secondary" className="text-xs">
                          {scope}
                        </Badge>
                      ))}
                      {app.scopes.length > 3 && (
                        <Badge variant="outline" className="text-xs">
                          +{app.scopes.length - 3}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={app.status === 'active' ? 'default' : 'secondary'}
                    >
                      {app.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {app.last_used_at
                      ? formatDistanceToNow(new Date(app.last_used_at), {
                          addSuffix: true,
                        })
                      : 'Never'}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleViewDetails(app);
                        }}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRegenerateSecret(app.id);
                        }}
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(app.id);
                        }}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <CreateAppModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={(secret) => {
          setShowCreateModal(false);
          setClientSecret(secret);
          queryClient.invalidateQueries({ queryKey: ['oauth-apps'] });
        }}
      />

      {selectedApp && (
        <AppDetailsModal
          app={selectedApp}
          open={showDetailsModal}
          onClose={() => {
            setShowDetailsModal(false);
            setSelectedApp(null);
          }}
        />
      )}

      <ClientSecretModal
        secret={clientSecret}
        open={!!clientSecret}
        onClose={() => setClientSecret(null)}
      />

      <AlertDialog open={!!deleteAppId} onOpenChange={() => setDeleteAppId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete OAuth Application</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete the OAuth application and revoke all access
              tokens. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
