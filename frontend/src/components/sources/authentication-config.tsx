"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Loader2, Plus, X } from "lucide-react";
import type { ConnectionConfig } from "@/lib/types";

interface AuthenticationConfigProps {
  config: ConnectionConfig;
  onChange: (config: ConnectionConfig) => void;
  disabled?: boolean;
}

export function AuthenticationConfig({
  config,
  onChange,
  disabled = false,
}: AuthenticationConfigProps) {
  const [headers, setHeaders] = useState<Array<{ key: string; value: string }>>(
    Object.entries(config.headers || {}).map(([key, value]) => ({ key, value }))
  );

  const updateAuthType = (authType: string) => {
    onChange({
      ...config,
      auth_type: authType as ConnectionConfig["auth_type"],
      ...(authType === "none" && { oauth_config: undefined }),
    });
  };

  const addHeader = () => {
    setHeaders([...headers, { key: "", value: "" }]);
  };

  const removeHeader = (index: number) => {
    const newHeaders = headers.filter((_, i) => i !== index);
    setHeaders(newHeaders);
    updateHeaders(newHeaders);
  };

  const updateHeader = (index: number, field: "key" | "value", value: string) => {
    const newHeaders = headers.map((h, i) => (i === index ? { ...h, [field]: value } : h));
    setHeaders(newHeaders);
    updateHeaders(newHeaders);
  };

  const updateHeaders = (newHeaders: Array<{ key: string; value: string }>) => {
    const headersObj = newHeaders.reduce(
      (acc, { key, value }) => {
        if (key) acc[key] = value;
        return acc;
      },
      {} as Record<string, string>
    );
    onChange({ ...config, headers: headersObj });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Authentication</CardTitle>
        <CardDescription>Configure API authentication method</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Auth Type */}
        <div className="space-y-2">
          <Label>Authentication Type</Label>
          <Select value={config.auth_type || "none"} onValueChange={updateAuthType} disabled={disabled}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
              <SelectItem value="none">None</SelectItem>
              <SelectItem value="basic">Basic Auth</SelectItem>
              <SelectItem value="bearer">Bearer Token</SelectItem>
              <SelectItem value="oauth2_client">OAuth 2.0 Client Credentials</SelectItem>
              <SelectItem value="oauth2_auth_code">OAuth 2.0 Authorization Code</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Basic Auth */}
        {config.auth_type === "basic" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="basic-username">Username</Label>
              <Input
                id="basic-username"
                value={(config.oauth_config as any)?.username || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config, username: e.target.value } as any,
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="basic-password">Password</Label>
              <Input
                id="basic-password"
                type="password"
                value={(config.oauth_config as any)?.password || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config, password: e.target.value } as any,
                  })
                }
                disabled={disabled}
              />
            </div>
          </>
        )}

        {/* Bearer Token */}
        {config.auth_type === "bearer" && (
          <div className="space-y-2">
            <Label htmlFor="bearer-token">Bearer Token</Label>
            <Input
              id="bearer-token"
              type="password"
              placeholder="Enter your API token"
              value={(config.oauth_config as any)?.token || ""}
              onChange={(e) =>
                onChange({
                  ...config,
                  oauth_config: { ...config.oauth_config, token: e.target.value } as any,
                })
              }
              disabled={disabled}
            />
          </div>
        )}

        {/* OAuth 2.0 Client Credentials */}
        {config.auth_type === "oauth2_client" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="oauth-client-id">Client ID</Label>
              <Input
                id="oauth-client-id"
                value={config.oauth_config?.client_id || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, client_id: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-client-secret">Client Secret</Label>
              <Input
                id="oauth-client-secret"
                type="password"
                value={config.oauth_config?.client_secret || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, client_secret: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-token-url">Token URL</Label>
              <Input
                id="oauth-token-url"
                type="url"
                placeholder="https://auth.example.com/oauth/token"
                value={config.oauth_config?.token_url || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, token_url: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-scope">Scope (optional)</Label>
              <Input
                id="oauth-scope"
                placeholder="read write"
                value={config.oauth_config?.scope || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, scope: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
          </>
        )}

        {/* OAuth 2.0 Authorization Code */}
        {config.auth_type === "oauth2_auth_code" && (
          <>
            <div className="space-y-2">
              <Label htmlFor="oauth-auth-client-id">Client ID</Label>
              <Input
                id="oauth-auth-client-id"
                value={config.oauth_config?.client_id || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, client_id: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-auth-client-secret">Client Secret</Label>
              <Input
                id="oauth-auth-client-secret"
                type="password"
                value={config.oauth_config?.client_secret || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, client_secret: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-auth-url">Authorization URL</Label>
              <Input
                id="oauth-auth-url"
                type="url"
                placeholder="https://auth.example.com/oauth/authorize"
                value={config.oauth_config?.auth_url || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, auth_url: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-auth-token-url">Token URL</Label>
              <Input
                id="oauth-auth-token-url"
                type="url"
                placeholder="https://auth.example.com/oauth/token"
                value={config.oauth_config?.token_url || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, token_url: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-auth-scope">Scope (optional)</Label>
              <Input
                id="oauth-auth-scope"
                placeholder="read write"
                value={config.oauth_config?.scope || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, scope: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="oauth-auth-redirect">Redirect URI</Label>
              <Input
                id="oauth-auth-redirect"
                type="url"
                placeholder="https://yourapp.com/oauth/callback"
                value={config.oauth_config?.redirect_uri || ""}
                onChange={(e) =>
                  onChange({
                    ...config,
                    oauth_config: { ...config.oauth_config!, redirect_uri: e.target.value },
                  })
                }
                disabled={disabled}
              />
            </div>
          </>
        )}

        {/* Custom Headers */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Custom Headers</Label>
            <Button type="button" variant="outline" size="sm" onClick={addHeader} disabled={disabled}>
              <Plus className="w-4 h-4 mr-1" />
              Add Header
            </Button>
          </div>
          {headers.length > 0 && (
            <div className="space-y-2">
              {headers.map((header, index) => (
                <div key={index} className="flex gap-2">
                  <Input
                    placeholder="Header name"
                    value={header.key}
                    onChange={(e) => updateHeader(index, "key", e.target.value)}
                    disabled={disabled}
                  />
                  <Input
                    placeholder="Header value"
                    value={header.value}
                    onChange={(e) => updateHeader(index, "value", e.target.value)}
                    disabled={disabled}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeHeader(index)}
                    disabled={disabled}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
