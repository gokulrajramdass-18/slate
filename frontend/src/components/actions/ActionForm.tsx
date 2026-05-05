"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/hooks/use-toast";
import { actionsApi, type ActionCreate, type ActionResponse } from "@/lib/api/actions";

interface ActionFormProps {
  action?: ActionResponse | null;
  onSuccess: () => void;
  onCancel: () => void;
}

export function ActionForm({ action, onSuccess, onCancel }: ActionFormProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [actionType, setActionType] = useState(action?.action_type || "webhook");
  const [authType, setAuthType] = useState(action?.auth_type || "none");

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ActionCreate>({
    defaultValues: action
      ? {
          name: action.name,
          description: action.description,
          action_type: action.action_type as any,
          endpoint: action.endpoint,
          method: action.method || "POST",
          auth_type: action.auth_type as any,
          headers: action.headers,
          query_params: action.query_params,
          body_template: action.body_template,
          condition_expression: action.condition_expression,
          retry_policy: action.retry_policy,
        }
      : {
          method: "POST",
          auth_type: "none",
          headers: {},
          query_params: {},
        },
  });

  // Create/Update mutation
  const mutation = useMutation({
    mutationFn: (data: ActionCreate) =>
      action ? actionsApi.update(action.id, data) : actionsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      toast({
        title: "Success",
        description: action ? "Action updated successfully" : "Action created successfully",
      });
      onSuccess();
    },
    onError: (error: Error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  // Test mutation
  const testMutation = useMutation({
    mutationFn: (data: ActionCreate) => actionsApi.testConfig(data, "test-user"),
    onSuccess: (result) => {
      toast({
        title: result.success ? "Test Passed ✓" : "Test Failed ✗",
        description: result.message,
        variant: result.success ? "default" : "destructive",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Test Error",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: ActionCreate) => {
    mutation.mutate(data);
  };

  const onTest = () => {
    const data = watch() as ActionCreate;
    testMutation.mutate(data);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      <Tabs defaultValue="basic" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="basic">Basic</TabsTrigger>
          <TabsTrigger value="auth">Authentication</TabsTrigger>
          <TabsTrigger value="template">Template</TabsTrigger>
          <TabsTrigger value="advanced">Advanced</TabsTrigger>
        </TabsList>

        {/* Basic Tab */}
        <TabsContent value="basic" className="space-y-4">
          <div>
            <Label htmlFor="name">Action Name *</Label>
            <Input
              id="name"
              {...register("name", { required: "Name is required" })}
              placeholder="send_slack_notification"
            />
            {errors.name && (
              <p className="text-sm text-red-500 mt-1">{errors.name.message}</p>
            )}
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              {...register("description")}
              placeholder="Send notification to Slack channel"
              rows={2}
            />
          </div>

          <div>
            <Label htmlFor="action_type">Action Type *</Label>
            <Select
              value={actionType}
              onValueChange={(value) => {
                setActionType(value);
                setValue("action_type", value as any);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="webhook">Webhook (HTTP)</SelectItem>
                <SelectItem value="email">Email (SMTP)</SelectItem>
                <SelectItem value="hana_operation">HANA Operation</SelectItem>
                <SelectItem value="workflow_trigger">Workflow Trigger</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="endpoint">
              {actionType === "email"
                ? "Email Address *"
                : actionType === "hana_operation"
                ? "Table Name *"
                : actionType === "workflow_trigger"
                ? "Workflow ID"
                : "Endpoint URL *"}
            </Label>
            <Input
              id="endpoint"
              {...register("endpoint", { required: "Endpoint is required" })}
              placeholder={
                actionType === "email"
                  ? "notifications@company.com"
                  : actionType === "hana_operation"
                  ? "table_name"
                  : actionType === "workflow_trigger"
                  ? "workflow-id-123"
                  : "https://api.example.com/webhook"
              }
            />
            {errors.endpoint && (
              <p className="text-sm text-red-500 mt-1">{errors.endpoint.message}</p>
            )}
          </div>

          {actionType === "webhook" && (
            <div>
              <Label htmlFor="method">HTTP Method</Label>
              <Select
                defaultValue={action?.method || "POST"}
                onValueChange={(value) => setValue("method", value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GET">GET</SelectItem>
                  <SelectItem value="POST">POST</SelectItem>
                  <SelectItem value="PUT">PUT</SelectItem>
                  <SelectItem value="DELETE">DELETE</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </TabsContent>

        {/* Authentication Tab */}
        <TabsContent value="auth" className="space-y-4">
          <div>
            <Label htmlFor="auth_type">Authentication Type</Label>
            <Select
              value={authType}
              onValueChange={(value) => {
                setAuthType(value);
                setValue("auth_type", value as any);
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                <SelectItem value="basic">Basic Auth</SelectItem>
                <SelectItem value="bearer">Bearer Token</SelectItem>
                <SelectItem value="api_key">API Key</SelectItem>
                <SelectItem value="oauth2_client">OAuth 2.0 Client</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {authType === "basic" && (
            <>
              <div>
                <Label htmlFor="auth_username">Username</Label>
                <Input
                  id="auth_username"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      username: e.target.value,
                    })
                  }
                  defaultValue={(action as any)?.auth_config?.username}
                />
              </div>
              <div>
                <Label htmlFor="auth_password">Password</Label>
                <Input
                  id="auth_password"
                  type="password"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      password: e.target.value,
                    })
                  }
                />
              </div>
            </>
          )}

          {authType === "bearer" && (
            <div>
              <Label htmlFor="auth_token">Bearer Token</Label>
              <Input
                id="auth_token"
                type="password"
                onChange={(e) =>
                  setValue("auth_config", { token: e.target.value })
                }
              />
            </div>
          )}

          {authType === "api_key" && (
            <>
              <div>
                <Label htmlFor="auth_key">API Key Name</Label>
                <Input
                  id="auth_key"
                  placeholder="X-API-Key"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      key: e.target.value,
                    })
                  }
                  defaultValue={(action as any)?.auth_config?.key}
                />
              </div>
              <div>
                <Label htmlFor="auth_value">API Key Value</Label>
                <Input
                  id="auth_value"
                  type="password"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      value: e.target.value,
                    })
                  }
                />
              </div>
              <div>
                <Label htmlFor="auth_location">Location</Label>
                <Select
                  defaultValue={(action as any)?.auth_config?.location || "header"}
                  onValueChange={(value) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      location: value,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="header">Header</SelectItem>
                    <SelectItem value="query">Query Parameter</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          )}

          {authType === "oauth2_client" && (
            <>
              <div>
                <Label htmlFor="oauth_client_id">Client ID</Label>
                <Input
                  id="oauth_client_id"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      client_id: e.target.value,
                    })
                  }
                  defaultValue={(action as any)?.auth_config?.client_id}
                />
              </div>
              <div>
                <Label htmlFor="oauth_client_secret">Client Secret</Label>
                <Input
                  id="oauth_client_secret"
                  type="password"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      client_secret: e.target.value,
                    })
                  }
                />
              </div>
              <div>
                <Label htmlFor="oauth_token_url">Token URL</Label>
                <Input
                  id="oauth_token_url"
                  placeholder="https://oauth.example.com/token"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      token_url: e.target.value,
                    })
                  }
                  defaultValue={(action as any)?.auth_config?.token_url}
                />
              </div>
              <div>
                <Label htmlFor="oauth_scope">Scope (optional)</Label>
                <Input
                  id="oauth_scope"
                  placeholder="read write"
                  onChange={(e) =>
                    setValue("auth_config", {
                      ...watch("auth_config"),
                      scope: e.target.value,
                    })
                  }
                  defaultValue={(action as any)?.auth_config?.scope}
                />
              </div>
            </>
          )}
        </TabsContent>

        {/* Template Tab */}
        <TabsContent value="template" className="space-y-4">
          <div>
            <Label htmlFor="body_template">Body Template (JSON)</Label>
            <Textarea
              id="body_template"
              {...register("body_template")}
              placeholder='{\n  "text": "Result: {{result}}",\n  "status": "{{status}}"\n}'
              rows={10}
              className="font-mono text-sm"
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  setValue("body_template", parsed);
                } catch {
                  // Invalid JSON, keep as string
                }
              }}
              defaultValue={
                action?.body_template
                  ? JSON.stringify(action.body_template, null, 2)
                  : ""
              }
            />
            <p className="text-sm text-muted-foreground mt-1">
              Use &#123;&#123;variable&#125;&#125; for placeholders (Jinja2 syntax)
            </p>
          </div>

          <div>
            <Label htmlFor="headers">Headers (JSON, optional)</Label>
            <Textarea
              id="headers"
              placeholder='{\n  "Content-Type": "application/json"\n}'
              rows={4}
              className="font-mono text-sm"
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  setValue("headers", parsed);
                } catch {
                  // Invalid JSON
                }
              }}
              defaultValue={
                action?.headers && Object.keys(action.headers).length > 0
                  ? JSON.stringify(action.headers, null, 2)
                  : ""
              }
            />
          </div>
        </TabsContent>

        {/* Advanced Tab */}
        <TabsContent value="advanced" className="space-y-4">
          <div>
            <Label htmlFor="condition_expression">Condition Expression (optional)</Label>
            <Input
              id="condition_expression"
              {...register("condition_expression")}
              placeholder='status == "completed" and confidence > 0.8'
            />
            <p className="text-sm text-muted-foreground mt-1">
              Python expression - action only executes if this evaluates to True
            </p>
          </div>

          <div>
            <Label htmlFor="retry_policy">Retry Policy (JSON, optional)</Label>
            <Textarea
              id="retry_policy"
              placeholder='{\n  "max_retries": 3,\n  "backoff": "exponential",\n  "initial_delay": 1.0\n}'
              rows={5}
              className="font-mono text-sm"
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  setValue("retry_policy", parsed);
                } catch {
                  // Invalid JSON
                }
              }}
              defaultValue={
                action?.retry_policy
                  ? JSON.stringify(action.retry_policy, null, 2)
                  : ""
              }
            />
          </div>
        </TabsContent>
      </Tabs>

      <div className="flex justify-between pt-4 border-t">
        <div className="space-x-2">
          <Button
            type="button"
            variant="outline"
            onClick={onTest}
            disabled={testMutation.isPending}
          >
            {testMutation.isPending ? "Testing..." : "Test"}
          </Button>
        </div>
        <div className="space-x-2">
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending
              ? "Saving..."
              : action
              ? "Update Action"
              : "Create Action"}
          </Button>
        </div>
      </div>
    </form>
  );
}
