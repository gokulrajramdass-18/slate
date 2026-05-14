import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { observabilitySettingsApi } from '@/lib/api/observability-settings';
import type { ObservabilityConfig } from '@/lib/api/observability-settings';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { Activity, CheckCircle2, XCircle, Loader2, AlertCircle } from 'lucide-react';

export default function SettingsObservabilityPage() {
  const queryClient = useQueryClient();

  // Query for current settings
  const { data: config, isLoading } = useQuery({
    queryKey: ['observability-settings'],
    queryFn: observabilitySettingsApi.get,
  });

  // Query for provider status
  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['observability-status'],
    queryFn: observabilitySettingsApi.getStatus,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Local state for form
  const [provider, setProvider] = useState<'none' | 'langfuse' | 'mlflow' | 'both'>('none');
  const [langfuse, setLangfuse] = useState({
    enabled: false,
    public_key: '',
    secret_key: '',
    host: 'https://cloud.langfuse.com',
  });
  const [mlflow, setMLFlow] = useState({
    enabled: false,
    tracking_uri: 'http://mlflow:5000',
    experiment_name: 'slate-agents',
    username: '',
    password: '',
  });
  const [options, setOptions] = useState({
    trace_level: 'info' as 'debug' | 'info' | 'warn' | 'error',
    log_llm_calls: true,
    log_tool_calls: true,
    log_agent_steps: true,
  });

  // Test connection states
  const [testingLangfuse, setTestingLangfuse] = useState(false);
  const [testingMLFlow, setTestingMLFlow] = useState(false);

  // Sync from server
  useEffect(() => {
    if (config) {
      setProvider(config.provider);
      setLangfuse(config.langfuse);
      setMLFlow(config.mlflow);
      setOptions(config.options);
    }
  }, [config]);

  // Mutation for saving
  const mutation = useMutation({
    mutationFn: observabilitySettingsApi.update,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['observability-settings'] });
      queryClient.invalidateQueries({ queryKey: ['observability-status'] });
      toast.success('Observability settings saved successfully');
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to save settings');
    },
  });

  const handleSave = () => {
    mutation.mutate({
      provider,
      langfuse,
      mlflow,
      options,
    });
  };

  const handleTestConnection = async (providerName: 'langfuse' | 'mlflow') => {
    if (providerName === 'langfuse') {
      setTestingLangfuse(true);
    } else {
      setTestingMLFlow(true);
    }

    try {
      const result = await observabilitySettingsApi.testConnection(providerName);
      if (result.success) {
        toast.success(result.message);
        refetchStatus();
      } else {
        toast.error(result.message);
      }
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Connection test failed');
    } finally {
      if (providerName === 'langfuse') {
        setTestingLangfuse(false);
      } else {
        setTestingMLFlow(false);
      }
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const showLangfuse = provider === 'langfuse' || provider === 'both';
  const showMLFlow = provider === 'mlflow' || provider === 'both';

  return (
    <div className="space-y-6 p-6 max-w-4xl mx-auto">
      <div className="flex items-center space-x-2">
        <Activity className="w-6 h-6" />
        <div>
          <h1 className="text-2xl font-bold">Observability</h1>
          <p className="text-sm text-muted-foreground">
            Configure monitoring and tracing for LLM and agent executions
          </p>
        </div>
      </div>

      {/* Provider Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Provider Selection</CardTitle>
          <CardDescription>
            Choose which observability provider(s) to use for tracing
          </CardDescription>
        </CardHeader>
        <CardContent>
          <RadioGroup value={provider} onValueChange={(value: any) => setProvider(value)}>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="none" id="none" />
              <Label htmlFor="none" className="cursor-pointer">None (Disabled)</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="langfuse" id="langfuse" />
              <Label htmlFor="langfuse" className="cursor-pointer">Langfuse Only</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="mlflow" id="mlflow" />
              <Label htmlFor="mlflow" className="cursor-pointer">MLFlow Only</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="both" id="both" />
              <Label htmlFor="both" className="cursor-pointer">Both (Dual-Mode)</Label>
            </div>
          </RadioGroup>
        </CardContent>
      </Card>

      {/* Langfuse Configuration */}
      {showLangfuse && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Langfuse Configuration</span>
              {status?.langfuse && (
                <div className="flex items-center space-x-2 text-sm">
                  {status.langfuse.connected ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                      <span className="text-green-600">Connected</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4 text-red-500" />
                      <span className="text-red-600">Disconnected</span>
                    </>
                  )}
                </div>
              )}
            </CardTitle>
            <CardDescription>
              Configure Langfuse cloud observability (requires account at cloud.langfuse.com)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center space-x-2">
              <Switch
                checked={langfuse.enabled}
                onCheckedChange={(checked) => setLangfuse({ ...langfuse, enabled: checked })}
              />
              <Label>Enable Langfuse</Label>
            </div>

            {langfuse.enabled && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="langfuse-public-key">Public Key</Label>
                  <Input
                    id="langfuse-public-key"
                    type="text"
                    value={langfuse.public_key}
                    onChange={(e) => setLangfuse({ ...langfuse, public_key: e.target.value })}
                    placeholder="pk-lf-..."
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="langfuse-secret-key">Secret Key</Label>
                  <Input
                    id="langfuse-secret-key"
                    type="password"
                    value={langfuse.secret_key}
                    onChange={(e) => setLangfuse({ ...langfuse, secret_key: e.target.value })}
                    placeholder="sk-lf-..."
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="langfuse-host">Host URL</Label>
                  <Input
                    id="langfuse-host"
                    type="url"
                    value={langfuse.host}
                    onChange={(e) => setLangfuse({ ...langfuse, host: e.target.value })}
                    placeholder="https://cloud.langfuse.com"
                  />
                </div>

                <Button
                  variant="outline"
                  onClick={() => handleTestConnection('langfuse')}
                  disabled={testingLangfuse}
                >
                  {testingLangfuse && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Test Connection
                </Button>

                {status?.langfuse?.error && (
                  <div className="flex items-start space-x-2 p-3 bg-red-50 border border-red-200 rounded-md">
                    <AlertCircle className="w-4 h-4 text-red-600 mt-0.5" />
                    <div className="text-sm text-red-600">{status.langfuse.error}</div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* MLFlow Configuration */}
      {showMLFlow && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>MLFlow Configuration</span>
              {status?.mlflow && (
                <div className="flex items-center space-x-2 text-sm">
                  {status.mlflow.connected ? (
                    <>
                      <CheckCircle2 className="w-4 h-4 text-green-500" />
                      <span className="text-green-600">Connected</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-4 h-4 text-red-500" />
                      <span className="text-red-600">Disconnected</span>
                    </>
                  )}
                </div>
              )}
            </CardTitle>
            <CardDescription>
              Configure MLFlow tracking server (local or remote)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center space-x-2">
              <Switch
                checked={mlflow.enabled}
                onCheckedChange={(checked) => setMLFlow({ ...mlflow, enabled: checked })}
              />
              <Label>Enable MLFlow</Label>
            </div>

            {mlflow.enabled && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="mlflow-tracking-uri">Tracking URI</Label>
                  <Input
                    id="mlflow-tracking-uri"
                    type="text"
                    value={mlflow.tracking_uri}
                    onChange={(e) => setMLFlow({ ...mlflow, tracking_uri: e.target.value })}
                    placeholder="http://mlflow:5000 or sqlite:///data/mlruns.db"
                  />
                  <p className="text-xs text-muted-foreground">
                    Use http://mlflow:5000 for Docker, or sqlite:///path/to/mlruns.db for local storage
                  </p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mlflow-experiment-name">Experiment Name</Label>
                  <Input
                    id="mlflow-experiment-name"
                    type="text"
                    value={mlflow.experiment_name}
                    onChange={(e) => setMLFlow({ ...mlflow, experiment_name: e.target.value })}
                    placeholder="slate-agents"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mlflow-username">Username (optional)</Label>
                  <Input
                    id="mlflow-username"
                    type="text"
                    value={mlflow.username}
                    onChange={(e) => setMLFlow({ ...mlflow, username: e.target.value })}
                    placeholder="For basic auth"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mlflow-password">Password (optional)</Label>
                  <Input
                    id="mlflow-password"
                    type="password"
                    value={mlflow.password}
                    onChange={(e) => setMLFlow({ ...mlflow, password: e.target.value })}
                    placeholder="For basic auth"
                  />
                </div>

                <Button
                  variant="outline"
                  onClick={() => handleTestConnection('mlflow')}
                  disabled={testingMLFlow}
                >
                  {testingMLFlow && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Test Connection
                </Button>

                {status?.mlflow?.connected && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-md">
                    <div className="text-sm text-green-900 space-y-1">
                      <div className="flex items-center space-x-2">
                        <CheckCircle2 className="w-4 h-4" />
                        <span className="font-medium">Connected to MLFlow</span>
                      </div>
                      <div className="pl-6 text-xs text-green-700">
                        {status.mlflow.tracking_uri && <div>URI: {status.mlflow.tracking_uri}</div>}
                        {status.mlflow.experiment_name && <div>Experiment: {status.mlflow.experiment_name}</div>}
                        {status.mlflow.total_runs !== undefined && <div>Total Runs: {status.mlflow.total_runs}</div>}
                        {status.mlflow.last_run_at && <div>Last Run: {new Date(status.mlflow.last_run_at).toLocaleString()}</div>}
                      </div>
                    </div>
                  </div>
                )}

                {status?.mlflow?.error && (
                  <div className="flex items-start space-x-2 p-3 bg-red-50 border border-red-200 rounded-md">
                    <AlertCircle className="w-4 h-4 text-red-600 mt-0.5" />
                    <div className="text-sm text-red-600">{status.mlflow.error}</div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Observability Options */}
      {provider !== 'none' && (
        <Card>
          <CardHeader>
            <CardTitle>Observability Options</CardTitle>
            <CardDescription>
              Configure what to trace and log level
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Trace Level</Label>
              <RadioGroup value={options.trace_level} onValueChange={(value: any) => setOptions({ ...options, trace_level: value })}>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="debug" id="debug" />
                  <Label htmlFor="debug" className="cursor-pointer">Debug</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="info" id="info" />
                  <Label htmlFor="info" className="cursor-pointer">Info</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="warn" id="warn" />
                  <Label htmlFor="warn" className="cursor-pointer">Warn</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="error" id="error" />
                  <Label htmlFor="error" className="cursor-pointer">Error</Label>
                </div>
              </RadioGroup>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                checked={options.log_llm_calls}
                onCheckedChange={(checked) => setOptions({ ...options, log_llm_calls: checked })}
              />
              <Label>Log LLM Calls</Label>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                checked={options.log_tool_calls}
                onCheckedChange={(checked) => setOptions({ ...options, log_tool_calls: checked })}
              />
              <Label>Log Tool Calls</Label>
            </div>

            <div className="flex items-center space-x-2">
              <Switch
                checked={options.log_agent_steps}
                onCheckedChange={(checked) => setOptions({ ...options, log_agent_steps: checked })}
              />
              <Label>Log Agent Steps</Label>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Save Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleSave}
          disabled={mutation.isPending}
          size="lg"
        >
          {mutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          Save Settings
        </Button>
      </div>

      {/* Info Card */}
      <Card className="bg-muted/50">
        <CardHeader>
          <CardTitle className="text-base">About Observability Providers</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <div>
            <strong className="text-foreground">Langfuse:</strong> Cloud-based observability platform with rich UI for exploring traces, analyzing performance, and debugging LLM applications. Requires account at cloud.langfuse.com.
          </div>
          <div>
            <strong className="text-foreground">MLFlow:</strong> Open-source platform for ML lifecycle management with built-in experiment tracking. Can run locally with SQLite or connect to a tracking server. Access UI at http://localhost:5000.
          </div>
          <div>
            <strong className="text-foreground">Dual-Mode:</strong> Run both providers simultaneously for comparison, migration, or using each provider's strengths (e.g., Langfuse for debugging, MLFlow for metrics).
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
