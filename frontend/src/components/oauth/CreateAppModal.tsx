'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { useToast } from '@/hooks/use-toast';
import { oauthAppsApi, OAuthAppCreate, OAuthScope } from '@/lib/api/oauth-apps';

interface CreateAppModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (clientSecret: string) => void;
}

export function CreateAppModal({ open, onClose, onSuccess }: CreateAppModalProps) {
  const { toast } = useToast();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [selectedGrantTypes, setSelectedGrantTypes] = useState<string[]>(['client_credentials']);
  const [redirectUris, setRedirectUris] = useState<string>('');
  const [rateLimitHour, setRateLimitHour] = useState(1000);
  const [rateLimitDay, setRateLimitDay] = useState(10000);
  const [tokenExpiry, setTokenExpiry] = useState(3600);

  const { data: scopes = [] } = useQuery({
    queryKey: ['oauth-scopes'],
    queryFn: oauthAppsApi.listScopes,
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: (data: OAuthAppCreate) => oauthAppsApi.create(data),
    onSuccess: (data) => {
      onSuccess(data.client_secret);
      resetForm();
    },
    onError: (error: Error) => {
      toast({
        title: 'Failed to create application',
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  const resetForm = () => {
    setName('');
    setDescription('');
    setSelectedScopes([]);
    setSelectedGrantTypes(['client_credentials']);
    setRedirectUris('');
    setRateLimitHour(1000);
    setRateLimitDay(10000);
    setTokenExpiry(3600);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleSubmit = () => {
    if (!name.trim()) {
      toast({
        title: 'Name required',
        description: 'Please enter an application name.',
        variant: 'destructive',
      });
      return;
    }

    if (selectedScopes.length === 0) {
      toast({
        title: 'Scopes required',
        description: 'Please select at least one scope.',
        variant: 'destructive',
      });
      return;
    }

    createMutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
      scopes: selectedScopes,
      grant_types: selectedGrantTypes,
      redirect_uris: selectedGrantTypes.includes('authorization_code')
        ? redirectUris.split('\n').map(uri => uri.trim()).filter(uri => uri)
        : undefined,
      rate_limit_per_hour: rateLimitHour,
      rate_limit_per_day: rateLimitDay,
      token_expiry_seconds: tokenExpiry,
    });
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scope)
        ? prev.filter((s) => s !== scope)
        : [...prev, scope]
    );
  };

  const groupedScopes = scopes.reduce((acc, scope) => {
    if (!acc[scope.resource_type]) {
      acc[scope.resource_type] = [];
    }
    acc[scope.resource_type].push(scope);
    return acc;
  }, {} as Record<string, OAuthScope[]>);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create OAuth Application</DialogTitle>
          <DialogDescription>
            Create a new OAuth application to access Agent APIs. You will receive a
            client ID and secret to authenticate your requests.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="name">Application Name *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Application"
              maxLength={255}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description of your application"
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label>Grant Types *</Label>
            <div className="space-y-2">
              <div className="flex items-start gap-3">
                <Checkbox
                  id="grant-client-credentials"
                  checked={selectedGrantTypes.includes('client_credentials')}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      setSelectedGrantTypes([...selectedGrantTypes, 'client_credentials']);
                    } else {
                      setSelectedGrantTypes(selectedGrantTypes.filter(g => g !== 'client_credentials'));
                    }
                  }}
                />
                <div className="flex-1">
                  <label htmlFor="grant-client-credentials" className="text-sm cursor-pointer font-medium">
                    Client Credentials
                  </label>
                  <p className="text-xs text-muted-foreground mt-1">
                    Server-to-server authentication. App acts on its own behalf.
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3">
                <Checkbox
                  id="grant-authorization-code"
                  checked={selectedGrantTypes.includes('authorization_code')}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      setSelectedGrantTypes([...selectedGrantTypes, 'authorization_code']);
                    } else {
                      setSelectedGrantTypes(selectedGrantTypes.filter(g => g !== 'authorization_code'));
                    }
                  }}
                />
                <div className="flex-1">
                  <label htmlFor="grant-authorization-code" className="text-sm cursor-pointer font-medium">
                    Authorization Code (with PKCE)
                  </label>
                  <p className="text-xs text-muted-foreground mt-1">
                    User authorization flow. App acts on behalf of a specific user.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {selectedGrantTypes.includes('authorization_code') && (
            <div className="space-y-2">
              <Label htmlFor="redirectUris">Redirect URIs * (one per line)</Label>
              <Textarea
                id="redirectUris"
                value={redirectUris}
                onChange={(e) => setRedirectUris(e.target.value)}
                placeholder="https://myapp.com/oauth/callback&#10;https://myapp.com/auth/callback"
                rows={3}
              />
              <p className="text-xs text-muted-foreground">
                Required for Authorization Code flow. Users will be redirected here after authorization.
              </p>
            </div>
          )}

          <div className="space-y-2">
            <Label>Scopes * ({selectedScopes.length} selected)</Label>
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
          </div>

          <Accordion type="single" collapsible>
            <AccordionItem value="advanced">
              <AccordionTrigger>Advanced Settings</AccordionTrigger>
              <AccordionContent className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label htmlFor="rateLimitHour">Rate Limit (per hour)</Label>
                  <Input
                    id="rateLimitHour"
                    type="number"
                    value={rateLimitHour}
                    onChange={(e) => setRateLimitHour(parseInt(e.target.value))}
                    min={1}
                    max={10000}
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum requests per hour (1-10,000)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="rateLimitDay">Rate Limit (per day)</Label>
                  <Input
                    id="rateLimitDay"
                    type="number"
                    value={rateLimitDay}
                    onChange={(e) => setRateLimitDay(parseInt(e.target.value))}
                    min={1}
                    max={100000}
                  />
                  <p className="text-xs text-muted-foreground">
                    Maximum requests per day (1-100,000)
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="tokenExpiry">Token Expiry (seconds)</Label>
                  <Input
                    id="tokenExpiry"
                    type="number"
                    value={tokenExpiry}
                    onChange={(e) => setTokenExpiry(parseInt(e.target.value))}
                    min={300}
                    max={86400}
                  />
                  <p className="text-xs text-muted-foreground">
                    Access token lifetime (300-86,400 seconds / 5 min - 24 hours)
                  </p>
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={createMutation.isPending}>
            {createMutation.isPending ? 'Creating...' : 'Create Application'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
