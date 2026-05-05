"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { credentialsApi } from "@/lib/api/models";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Key, Plus, Trash2, TestTube, CheckCircle, XCircle, Loader2, Cpu } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { SettingsHeader } from "@/components/settings/settings-header";

interface Credential {
  id: string;
  name: string;
  provider: string;
  model_name: string;
  model_type: string;
  base_url?: string;
  is_active: boolean;
  connection_status: "untested" | "connected" | "failed";
  last_tested?: string;
  created: string;
  updated: string;
}

export default function ApiKeysPage() {
  const queryClient = useQueryClient();
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [deleteCredentialId, setDeleteCredentialId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testingBeforeSave, setTestingBeforeSave] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [showLiteLLMDialog, setShowLiteLLMDialog] = useState(false);
  const [litellmUrl, setLitellmUrl] = useState("http://localhost:6655/litellm/v1");
  const [litellmApiKey, setLitellmApiKey] = useState(
    process.env.NEXT_PUBLIC_HAI_PROXY_KEY || ""
  );
  const [litellmModels, setLitellmModels] = useState<any[]>([]);
  const [loadingLiteLLM, setLoadingLiteLLM] = useState(false);

  // SAP AI Core state
  const [showSAPAICoreDialog, setShowSAPAICoreDialog] = useState(false);
  const [sapAuthUrl, setSapAuthUrl] = useState("");
  const [sapApiUrl, setSapApiUrl] = useState("");
  const [sapClientId, setSapClientId] = useState("");
  const [sapClientSecret, setSapClientSecret] = useState("");
  const [sapResourceGroup, setSapResourceGroup] = useState("default");
  const [sapIdentityZone, setSapIdentityZone] = useState("");
  const [sapIdentityZoneId, setSapIdentityZoneId] = useState("");
  const [sapAICoreModels, setSapAICoreModels] = useState<any[]>([]);
  const [loadingSAPAICore, setLoadingSAPAICore] = useState(false);

  // Model source switch (litellm or sap_ai_core)
  const [modelSource, setModelSource] = useState<"litellm" | "sap_ai_core">(
    () => {
      // Check localStorage for saved preference
      if (typeof window !== "undefined") {
        return (localStorage.getItem("modelSource") as "litellm" | "sap_ai_core") || "litellm";
      }
      return "litellm";
    }
  );
  const [showSwitchConfirmDialog, setShowSwitchConfirmDialog] = useState(false);
  const [pendingModelSource, setPendingModelSource] = useState<"litellm" | "sap_ai_core" | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [modelName, setModelName] = useState("");
  const [modelType, setModelType] = useState<string>("language");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [isActive, setIsActive] = useState(true);

  const { data: credentials, isLoading } = useQuery({
    queryKey: ["credentials"],
    queryFn: () => credentialsApi.list(),
  });

  // Update provider when model source changes and dialog is open
  useEffect(() => {
    if (showCreateDialog) {
      setProvider(modelSource === "sap_ai_core" ? "sap_ai_core" : "openai");
    }
  }, [modelSource, showCreateDialog]);

  const createMutation = useMutation({
    mutationFn: credentialsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credentials"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      toast.success("Credential created successfully");
      setShowCreateDialog(false);
      setTestingBeforeSave(false);
      setTestResult(null);
      resetForm();
    },
    onError: () => {
      toast.error("Failed to create credential");
      setTestingBeforeSave(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: credentialsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credentials"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      toast.success("Credential deleted successfully");
      setDeleteCredentialId(null);
    },
    onError: () => {
      toast.error("Failed to delete credential");
    },
  });

  const testMutation = useMutation({
    mutationFn: credentialsApi.test,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["credentials"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      if (data.success) {
        toast.success(data.message);
      } else {
        toast.error(data.message);
      }
      setTestingId(null);
    },
    onError: () => {
      toast.error("Connection test failed");
      setTestingId(null);
    },
  });

  const updateActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      credentialsApi.update(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["credentials"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      toast.success("Credential status updated");
    },
    onError: () => {
      toast.error("Failed to update credential");
    },
  });

  const resetForm = () => {
    setName("");
    setProvider(modelSource === "sap_ai_core" ? "sap_ai_core" : "openai");
    setModelName("");
    setModelType("language");
    setApiKey("");
    setBaseUrl("");
    setIsActive(true);
    // Reset SAP AI Core fields
    setSapAuthUrl("");
    setSapApiUrl("");
    setSapClientId("");
    setSapClientSecret("");
    setSapResourceGroup("default");
    setSapIdentityZone("");
    setSapIdentityZoneId("");
  };

  const handleCreate = async () => {
    // Validate based on provider type
    if (provider === "sap_ai_core") {
      if (!name || !modelName || !sapAuthUrl || !baseUrl || !sapClientId || !sapClientSecret) {
        toast.error("Please fill in all required SAP AI Core fields");
        return;
      }
    } else {
      if (!name || !modelName || !apiKey) {
        toast.error("Please fill in all required fields");
        return;
      }
    }

    // Test connection first
    setTestingBeforeSave(true);
    setTestResult(null);

    try {
      let result;
      let credentialData;

      if (provider === "sap_ai_core") {
        // For SAP AI Core, test using SAP-specific endpoint
        result = await credentialsApi.testSAPAICore({
          auth_url: sapAuthUrl,
          api_url: baseUrl,
          client_id: sapClientId,
          client_secret: sapClientSecret,
          resource_group: sapResourceGroup,
          identity_zone: sapIdentityZone || undefined,
          identityzoneid: sapIdentityZoneId || undefined,
        });

        // Prepare credential data with SAP AI Core format
        const sapCredentials: any = {
          auth_url: sapAuthUrl,
          api_url: baseUrl,
          client_id: sapClientId,
          client_secret: sapClientSecret,
          resource_group: sapResourceGroup,
        };

        // Add optional fields if provided
        if (sapIdentityZone) {
          sapCredentials.identity_zone = sapIdentityZone;
        }
        if (sapIdentityZoneId) {
          sapCredentials.identityzoneid = sapIdentityZoneId;
        }

        credentialData = {
          name,
          provider,
          model_name: modelName,
          model_type: modelType,
          api_key: JSON.stringify(sapCredentials),
          base_url: baseUrl,
          is_active: isActive,
          modalities: [],
        };
      } else {
        // Standard credential test
        result = await credentialsApi.testConnection({
          provider,
          model_name: modelName,
          model_type: modelType,
          api_key: apiKey,
          base_url: baseUrl || undefined,
        });

        credentialData = {
          name,
          provider,
          model_name: modelName,
          model_type: modelType,
          api_key: apiKey,
          base_url: baseUrl || undefined,
          is_active: isActive,
          modalities: [],
        };
      }

      setTestResult(result);

      if (!result.success) {
        toast.error(result.message);
        setTestingBeforeSave(false);
        return;
      }

      // Connection successful, create credential
      createMutation.mutate(credentialData as any);
    } catch (error) {
      toast.error("Failed to test connection");
      setTestingBeforeSave(false);
    }
  };

  const handleLoadLiteLLMModels = async () => {
    if (!litellmApiKey) {
      toast.error("Please enter an API key");
      return;
    }

    setLoadingLiteLLM(true);
    try {
      const result = await credentialsApi.getLiteLLMModels(litellmUrl, litellmApiKey);

      // Check if the API call was successful
      if (!result.success) {
        toast.error(result.error || "Failed to load models from LiteLLM");
        setLitellmModels([]);
        return;
      }

      // Success - show models
      setLitellmModels(result.models);
      toast.success(`Found ${result.count} models from LiteLLM`);
    } catch (error: any) {
      // Handle actual network/HTTP errors
      const errorMessage = error.response?.data?.error ||
                           error.response?.data?.detail ||
                           error.message ||
                           "Failed to load models from LiteLLM";
      toast.error(errorMessage);
      setLitellmModels([]);
    } finally {
      setLoadingLiteLLM(false);
    }
  };

  const handleSelectLiteLLMModel = (model: any) => {
    setProvider("litellm");
    setModelName(model.id);
    setModelType(model.type);
    setBaseUrl(litellmUrl);
    setApiKey(litellmApiKey); // Pre-fill API key from LiteLLM dialog
    setName(`LiteLLM - ${model.name}`);
    setShowLiteLLMDialog(false);
    setShowCreateDialog(true);
  };

  const handleLoadSAPAICoreModels = async () => {
    if (!sapAuthUrl || !sapApiUrl || !sapClientId || !sapClientSecret) {
      toast.error("Please fill in all required SAP AI Core credentials");
      return;
    }

    setLoadingSAPAICore(true);
    try {
      // Test connection first
      const testResult = await credentialsApi.testSAPAICore({
        auth_url: sapAuthUrl,
        api_url: sapApiUrl,
        client_id: sapClientId,
        client_secret: sapClientSecret,
        resource_group: sapResourceGroup,
        identity_zone: sapIdentityZone || undefined,
        identityzoneid: sapIdentityZoneId || undefined,
      });

      if (!testResult.success) {
        toast.error(testResult.message);
        setLoadingSAPAICore(false);
        return;
      }

      // Discover models
      const result = await credentialsApi.getSAPAICoreModels({
        auth_url: sapAuthUrl,
        api_url: sapApiUrl,
        client_id: sapClientId,
        client_secret: sapClientSecret,
        resource_group: sapResourceGroup,
        identity_zone: sapIdentityZone || undefined,
        identityzoneid: sapIdentityZoneId || undefined,
      });

      if (result.success) {
        setSapAICoreModels(result.models);
        toast.success(`Found ${result.count} models from SAP AI Core`);
      } else {
        toast.error("Failed to discover models from SAP AI Core");
        setSapAICoreModels([]);
      }
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || "Failed to load models from SAP AI Core";
      toast.error(errorMessage);
      setSapAICoreModels([]);
    } finally {
      setLoadingSAPAICore(false);
    }
  };

  const handleSelectSAPAICoreModel = (model: any) => {
    setProvider("sap_ai_core");
    setModelName(model.deployment_id);
    setModelType(model.type);
    setBaseUrl(sapApiUrl); // Keep the base URL separate
    // Don't set apiKey here - keep SAP credentials in their separate state
    setName(`SAP AI Core - ${model.name}`);
    setShowSAPAICoreDialog(false);
    setShowCreateDialog(true);
  };

  const handleModelSourceSwitch = (newSource: "litellm" | "sap_ai_core") => {
    if (newSource === modelSource) return;

    // Check if there are existing credentials
    if (credentials && credentials.length > 0) {
      // Show confirmation dialog
      setPendingModelSource(newSource);
      setShowSwitchConfirmDialog(true);
    } else {
      // No credentials, switch directly
      performModelSourceSwitch(newSource);
    }
  };

  const performModelSourceSwitch = async (newSource: "litellm" | "sap_ai_core") => {
    try {
      // Delete all existing credentials
      if (credentials && credentials.length > 0) {
        const deletePromises = credentials.map((cred) => credentialsApi.delete(cred.id));
        await Promise.all(deletePromises);

        // Invalidate queries
        queryClient.invalidateQueries({ queryKey: ["credentials"] });
        queryClient.invalidateQueries({ queryKey: ["models"] });

        toast.success(`All credentials cleared. Switched to ${newSource === "litellm" ? "LiteLLM" : "SAP AI Core"}`);
      }

      // Update model source
      setModelSource(newSource);

      // Save to localStorage
      if (typeof window !== "undefined") {
        localStorage.setItem("modelSource", newSource);
      }

      // Close confirmation dialog
      setShowSwitchConfirmDialog(false);
      setPendingModelSource(null);
    } catch (error) {
      toast.error("Failed to switch model source");
      console.error(error);
    }
  };

  const handleTest = (credentialId: string) => {
    setTestingId(credentialId);
    testMutation.mutate(credentialId);
  };

  const handleToggleActive = (id: string, currentStatus: boolean) => {
    updateActiveMutation.mutate({ id, is_active: !currentStatus });
  };

  const getStatusBadge = (status: string | undefined) => {
    if (!status) return null;
    switch (status) {
      case "connected":
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            <CheckCircle className="w-3 h-3 mr-1" />
            Connected
          </Badge>
        );
      case "failed":
        return (
          <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
            <XCircle className="w-3 h-3 mr-1" />
            Failed
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="bg-gray-50 text-gray-700 border-gray-200">
            Untested
          </Badge>
        );
    }
  };

  const getTypeBadge = (type: string | undefined) => {
    if (!type) return null;
    const colors = {
      language: "bg-blue-50 text-blue-700 border-blue-200",
      embedding: "bg-purple-50 text-purple-700 border-purple-200",
      speech_to_text: "bg-orange-50 text-orange-700 border-orange-200",
      text_to_speech: "bg-pink-50 text-pink-700 border-pink-200",
    };
    return (
      <Badge variant="outline" className={colors[type as keyof typeof colors] || ""}>
        {type.replace("_", " ")}
      </Badge>
    );
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <SettingsHeader
        title="API Keys"
        description="Configure AI model credentials and endpoints"
      />
      <div className="flex gap-2">
          {modelSource === "litellm" ? (
            <Button onClick={() => setShowLiteLLMDialog(true)} variant="outline">
              <Cpu className="w-4 h-4 mr-2" />
              Import from LiteLLM
            </Button>
          ) : (
            <Button onClick={() => setShowSAPAICoreDialog(true)} variant="outline">
              <Cpu className="w-4 h-4 mr-2" />
              Import from SAP AI Core
            </Button>
          )}
          <Button onClick={() => {
            // Set provider based on model source when opening dialog
            setProvider(modelSource === "sap_ai_core" ? "sap_ai_core" : "openai");
            setShowCreateDialog(true);
          }}>
            <Plus className="w-4 h-4 mr-2" />
            Add Credential
          </Button>
        </div>

      {/* Model Source Switch */}
      <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950 dark:border-blue-800">
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="space-y-1">
              <Label className="text-base font-semibold text-gray-900 dark:text-gray-100">
                Model Source
              </Label>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Choose between LiteLLM proxy or SAP AI Core for model imports.
                {credentials && credentials.length > 0 && (
                  <span className="text-orange-600 dark:text-orange-400 font-medium">
                    {" "}Switching will delete all existing credentials.
                  </span>
                )}
              </p>
            </div>
            <div className="flex items-center">
              {/* Segmented Control Style Switch */}
              <div className="inline-flex rounded-lg border-2 border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 p-1">
                <button
                  onClick={() => handleModelSourceSwitch("litellm")}
                  className={`
                    px-6 py-2 rounded-md font-medium text-sm transition-all
                    ${modelSource === "litellm"
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
                    }
                  `}
                >
                  LiteLLM
                </button>
                <button
                  onClick={() => handleModelSourceSwitch("sap_ai_core")}
                  className={`
                    px-6 py-2 rounded-md font-medium text-sm transition-all
                    ${modelSource === "sap_ai_core"
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200"
                    }
                  `}
                >
                  SAP AI Core
                </button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      ) : credentials && credentials.length > 0 ? (
        <div className="grid gap-4">
          {credentials.map((cred) => (
            <Card key={cred.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <CardTitle className="text-lg">{cred.name}</CardTitle>
                      {getStatusBadge(cred.connection_status)}
                      {getTypeBadge(cred.model_type)}
                    </div>
                    <CardDescription className="mt-2">
                      Provider: {cred.provider} | Model: {cred.model_name}
                      {cred.base_url && ` | Endpoint: ${cred.base_url}`}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor={`active-${cred.id}`} className="text-sm">
                        Active
                      </Label>
                      <Switch
                        id={`active-${cred.id}`}
                        checked={cred.is_active || false}
                        onCheckedChange={() => handleToggleActive(cred.id, cred.is_active || false)}
                      />
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleTest(cred.id)}
                    disabled={testingId === cred.id}
                  >
                    {testingId === cred.id ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin mr-2" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <TestTube className="w-3 h-3 mr-2" />
                        Test Connection
                      </>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => setDeleteCredentialId(cred.id)}
                  >
                    <Trash2 className="w-3 h-3 mr-2" />
                    Delete
                  </Button>
                  {cred.last_tested && (
                    <span className="text-xs text-gray-500 ml-auto">
                      Last tested: {new Date(cred.last_tested).toLocaleString()}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Key className="w-12 h-12 text-gray-400 mb-4" />
            <h3 className="text-lg font-semibold mb-2">No credentials configured</h3>
            <p className="text-gray-500 text-sm mb-4 text-center max-w-md">
              Add your AI provider credentials to start using models in Open Notebook
            </p>
            <Button onClick={() => {
              setProvider(modelSource === "sap_ai_core" ? "sap_ai_core" : "openai");
              setShowCreateDialog(true);
            }}>
              <Plus className="w-4 h-4 mr-2" />
              Add First Credential
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create Credential Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-2xl bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-gray-900 dark:text-gray-100">Add New Credential</DialogTitle>
            <DialogDescription className="text-gray-600 dark:text-gray-400">
              {provider === "sap_ai_core"
                ? "Configure SAP AI Core credentials with OAuth 2.0 authentication"
                : "Configure a new AI model credential with its API key and endpoint"
              }
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-gray-900 dark:text-gray-100">Name *</Label>
              <Input
                id="name"
                placeholder="e.g., OpenAI Production"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="bg-white dark:bg-gray-950"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="provider" className="text-gray-900 dark:text-gray-100">Provider *</Label>
                <Select value={provider} onValueChange={setProvider}>
                  <SelectTrigger id="provider" className="bg-white dark:bg-gray-950">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-950">
                    {modelSource === "litellm" ? (
                      <>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="anthropic">Anthropic</SelectItem>
                        <SelectItem value="google">Google</SelectItem>
                        <SelectItem value="azure">Azure OpenAI</SelectItem>
                        <SelectItem value="groq">Groq</SelectItem>
                        <SelectItem value="ollama">Ollama</SelectItem>
                        <SelectItem value="litellm">LiteLLM</SelectItem>
                        <SelectItem value="custom">Custom</SelectItem>
                      </>
                    ) : (
                      <SelectItem value="sap_ai_core">SAP AI Core</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="model-type" className="text-gray-900 dark:text-gray-100">Model Type *</Label>
                <Select value={modelType} onValueChange={setModelType}>
                  <SelectTrigger id="model-type" className="bg-white dark:bg-gray-950">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-white dark:bg-gray-950">
                    <SelectItem value="language">Language Model</SelectItem>
                    <SelectItem value="embedding">Embedding Model</SelectItem>
                    <SelectItem value="speech_to_text">Speech to Text</SelectItem>
                    <SelectItem value="text_to_speech">Text to Speech</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="model-name" className="text-gray-900 dark:text-gray-100">
                {provider === "sap_ai_core" ? "Deployment ID *" : "Model Name *"}
              </Label>
              <Input
                id="model-name"
                placeholder={provider === "sap_ai_core" ? "Use 'Import from SAP AI Core' to select a deployment" : "e.g., gpt-4, claude-3-opus-20240229"}
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                className="bg-white dark:bg-gray-950"
                disabled={provider === "sap_ai_core"}
              />
              {provider === "sap_ai_core" && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Use the "Import from SAP AI Core" button to discover and select deployments
                </p>
              )}
            </div>

            {/* SAP AI Core specific fields */}
            {provider === "sap_ai_core" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="sap-auth-url-create" className="text-gray-900 dark:text-gray-100">
                    OAuth 2.0 Token URL *
                  </Label>
                  <Input
                    id="sap-auth-url-create"
                    placeholder="https://your-tenant.authentication.sap.hana.ondemand.com/oauth/token"
                    value={sapAuthUrl}
                    onChange={(e) => setSapAuthUrl(e.target.value)}
                    className="bg-white dark:bg-gray-950"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="base-url" className="text-gray-900 dark:text-gray-100">AI Core API URL *</Label>
                  <Input
                    id="base-url"
                    placeholder="https://api.ai.internalprod.eu-central-1.aws.ml.hana.ondemand.com/v2"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    className="bg-white dark:bg-gray-950"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="sap-client-id-create" className="text-gray-900 dark:text-gray-100">
                      Client ID *
                    </Label>
                    <Input
                      id="sap-client-id-create"
                      placeholder="sb-..."
                      value={sapClientId}
                      onChange={(e) => setSapClientId(e.target.value)}
                      className="bg-white dark:bg-gray-950"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="sap-client-secret-create" className="text-gray-900 dark:text-gray-100">
                      Client Secret *
                    </Label>
                    <Input
                      id="sap-client-secret-create"
                      type="password"
                      placeholder="..."
                      value={sapClientSecret}
                      onChange={(e) => setSapClientSecret(e.target.value)}
                      className="bg-white dark:bg-gray-950"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="sap-resource-group-create" className="text-gray-900 dark:text-gray-100">
                    Resource Group
                  </Label>
                  <Input
                    id="sap-resource-group-create"
                    placeholder="default"
                    value={sapResourceGroup}
                    onChange={(e) => setSapResourceGroup(e.target.value)}
                    className="bg-white dark:bg-gray-950"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="sap-identity-zone-create" className="text-gray-900 dark:text-gray-100">
                      Identity Zone (Optional)
                    </Label>
                    <Input
                      id="sap-identity-zone-create"
                      placeholder="sap-production"
                      value={sapIdentityZone}
                      onChange={(e) => setSapIdentityZone(e.target.value)}
                      className="bg-white dark:bg-gray-950"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="sap-identity-zone-id-create" className="text-gray-900 dark:text-gray-100">
                      Identity Zone ID (Optional)
                    </Label>
                    <Input
                      id="sap-identity-zone-id-create"
                      placeholder="uaa-..."
                      value={sapIdentityZoneId}
                      onChange={(e) => setSapIdentityZoneId(e.target.value)}
                      className="bg-white dark:bg-gray-950"
                    />
                  </div>
                </div>
              </>
            ) : (
              <>
                {/* LiteLLM/Standard API Key field */}
                <div className="space-y-2">
                  <Label htmlFor="api-key" className="text-gray-900 dark:text-gray-100">API Key *</Label>
                  <Input
                    id="api-key"
                    type="password"
                    placeholder="sk-..."
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    className="bg-white dark:bg-gray-950"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="base-url" className="text-gray-900 dark:text-gray-100">Base URL / Endpoint (Optional)</Label>
                  <Input
                    id="base-url"
                    placeholder="https://api.openai.com/v1"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    className="bg-white dark:bg-gray-950"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Leave empty to use the provider's default endpoint
                  </p>
                </div>
              </>
            )}

            <div className="flex items-center gap-2">
              <Switch
                id="is-active"
                checked={isActive}
                onCheckedChange={setIsActive}
              />
              <Label htmlFor="is-active" className="text-gray-900 dark:text-gray-100">Make active immediately</Label>
            </div>

            {/* Test Result Display */}
            {testResult && (
              <div className={`p-3 rounded-lg ${testResult.success ? 'bg-green-50 border border-green-200 dark:bg-green-950 dark:border-green-800' : 'bg-red-50 border border-red-200 dark:bg-red-950 dark:border-red-800'}`}>
                <div className="flex items-center gap-2">
                  {testResult.success ? (
                    <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
                  )}
                  <span className={`text-sm font-medium ${testResult.success ? 'text-green-900 dark:text-green-100' : 'text-red-900 dark:text-red-100'}`}>
                    {testResult.message}
                  </span>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowCreateDialog(false);
              resetForm();
            }}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={createMutation.isPending || testingBeforeSave}>
              {testingBeforeSave ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Testing Connection...
                </>
              ) : createMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Creating...
                </>
              ) : (
                "Test & Create"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* LiteLLM Discovery Dialog */}
      <Dialog open={showLiteLLMDialog} onOpenChange={setShowLiteLLMDialog}>
        <DialogContent className="max-w-3xl bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
          <DialogHeader>
            <DialogTitle className="text-gray-900 dark:text-gray-100">Import Models from LiteLLM</DialogTitle>
            <DialogDescription className="text-gray-600 dark:text-gray-400">
              Connect to your LiteLLM endpoint to discover available models
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="litellm-url" className="text-gray-900 dark:text-gray-100">
                LiteLLM Endpoint URL
              </Label>
              <Input
                id="litellm-url"
                placeholder="http://localhost:6655/litellm/v1"
                value={litellmUrl}
                onChange={(e) => setLitellmUrl(e.target.value)}
                className="bg-white dark:bg-gray-950"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="litellm-api-key" className="text-gray-900 dark:text-gray-100">
                API Key *
              </Label>
              <Input
                id="litellm-api-key"
                type="password"
                placeholder="sk-..."
                value={litellmApiKey}
                onChange={(e) => setLitellmApiKey(e.target.value)}
                className="bg-white dark:bg-gray-950"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400">
                This API key will be used to authenticate with LiteLLM and will be pre-filled when you select a model
              </p>
            </div>

            <Button
              onClick={handleLoadLiteLLMModels}
              disabled={loadingLiteLLM || !litellmApiKey}
              className="w-full"
            >
              {loadingLiteLLM ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Discovering Models...
                </>
              ) : (
                <>
                  <Cpu className="w-4 h-4 mr-2" />
                  Discover Models
                </>
              )}
            </Button>

            {litellmModels.length > 0 && (
              <div className="border rounded-lg max-h-96 overflow-y-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-950 sticky top-0">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Provider</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                    {litellmModels.map((model) => (
                      <tr key={model.id} className="hover:bg-gray-50 dark:hover:bg-gray-900">
                        <td className="px-4 py-3 text-sm font-medium">{model.name}</td>
                        <td className="px-4 py-3 text-sm">
                          {getTypeBadge(model.type)}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400">{model.provider}</td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            size="sm"
                            onClick={() => handleSelectLiteLLMModel(model)}
                          >
                            Select
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {litellmModels.length === 0 && !loadingLiteLLM && (
              <div className="text-center py-8 text-gray-500">
                Enter your LiteLLM endpoint URL and API key, then click "Discover Models"
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setShowLiteLLMDialog(false);
              setLitellmApiKey("");
              setLitellmModels([]);
            }}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteCredentialId} onOpenChange={() => setDeleteCredentialId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete credential?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this credential and remove it from the available models list.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteCredentialId && deleteMutation.mutate(deleteCredentialId)}
              disabled={deleteMutation.isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* SAP AI Core Discovery Dialog */}
      <Dialog open={showSAPAICoreDialog} onOpenChange={setShowSAPAICoreDialog}>
        <DialogContent className="max-w-6xl bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-gray-900 dark:text-gray-100">Import Models from SAP AI Core</DialogTitle>
            <DialogDescription className="text-gray-600 dark:text-gray-400">
              Connect to your SAP AI Core instance to discover deployed models
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4 overflow-y-auto">
            <div className="space-y-2">
              <Label htmlFor="sap-auth-url" className="text-gray-900 dark:text-gray-100">
                OAuth 2.0 Token URL *
              </Label>
              <Input
                id="sap-auth-url"
                placeholder="https://your-tenant.authentication.sap.hana.ondemand.com/oauth/token"
                value={sapAuthUrl}
                onChange={(e) => setSapAuthUrl(e.target.value)}
                className="bg-white dark:bg-gray-950"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="sap-api-url" className="text-gray-900 dark:text-gray-100">
                AI Core API URL *
              </Label>
              <Input
                id="sap-api-url"
                placeholder="https://api.ai.internalprod.eu-central-1.aws.ml.hana.ondemand.com/v2"
                value={sapApiUrl}
                onChange={(e) => setSapApiUrl(e.target.value)}
                className="bg-white dark:bg-gray-950"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sap-client-id" className="text-gray-900 dark:text-gray-100">
                  Client ID *
                </Label>
                <Input
                  id="sap-client-id"
                  placeholder="sb-..."
                  value={sapClientId}
                  onChange={(e) => setSapClientId(e.target.value)}
                  className="bg-white dark:bg-gray-950"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="sap-client-secret" className="text-gray-900 dark:text-gray-100">
                  Client Secret *
                </Label>
                <Input
                  id="sap-client-secret"
                  type="password"
                  placeholder="..."
                  value={sapClientSecret}
                  onChange={(e) => setSapClientSecret(e.target.value)}
                  className="bg-white dark:bg-gray-950"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="sap-resource-group" className="text-gray-900 dark:text-gray-100">
                Resource Group
              </Label>
              <Input
                id="sap-resource-group"
                placeholder="default"
                value={sapResourceGroup}
                onChange={(e) => setSapResourceGroup(e.target.value)}
                className="bg-white dark:bg-gray-950"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sap-identity-zone" className="text-gray-900 dark:text-gray-100">
                  Identity Zone (Optional)
                </Label>
                <Input
                  id="sap-identity-zone"
                  placeholder="sap-production"
                  value={sapIdentityZone}
                  onChange={(e) => setSapIdentityZone(e.target.value)}
                  className="bg-white dark:bg-gray-950"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="sap-identity-zone-id" className="text-gray-900 dark:text-gray-100">
                  Identity Zone ID (Optional)
                </Label>
                <Input
                  id="sap-identity-zone-id"
                  placeholder="uaa-..."
                  value={sapIdentityZoneId}
                  onChange={(e) => setSapIdentityZoneId(e.target.value)}
                  className="bg-white dark:bg-gray-950"
                />
              </div>
            </div>

            <Button
              onClick={handleLoadSAPAICoreModels}
              disabled={loadingSAPAICore || !sapAuthUrl || !sapApiUrl || !sapClientId || !sapClientSecret}
              className="w-full"
            >
              {loadingSAPAICore ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Discovering Models...
                </>
              ) : (
                <>
                  <Cpu className="w-4 h-4 mr-2" />
                  Discover Models
                </>
              )}
            </Button>

            {sapAICoreModels.length > 0 && (
              <div className="border rounded-lg overflow-hidden">
                <div className="max-h-96 overflow-y-auto">
                  <table className="w-full table-fixed">
                    <thead className="bg-gray-50 dark:bg-gray-950 sticky top-0">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase w-[35%]">
                          Deployment Name
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase w-[15%]">
                          Type
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase w-[15%]">
                          Status
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase w-[25%]">
                          Scenario ID
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-semibold text-gray-700 dark:text-gray-300 uppercase w-[10%]">
                          Action
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-900">
                      {sapAICoreModels.map((model) => (
                        <tr key={model.id} className="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                          <td className="px-4 py-4">
                            <div className="flex flex-col gap-1">
                              <span className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                                {model.name}
                              </span>
                              <span className="text-xs text-gray-500 dark:text-gray-400 font-mono truncate">
                                {model.deployment_id}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-4">
                            {getTypeBadge(model.type)}
                          </td>
                          <td className="px-4 py-4">
                            <Badge variant="outline" className={
                              model.status === "RUNNING" ? "bg-green-50 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300" :
                              model.status === "STOPPED" ? "bg-red-50 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300" :
                              "bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-300"
                            }>
                              {model.status}
                            </Badge>
                          </td>
                          <td className="px-4 py-4">
                            <span className="text-xs text-gray-600 dark:text-gray-400 font-mono truncate block">
                              {model.scenario_id || '-'}
                            </span>
                          </td>
                          <td className="px-4 py-4 text-right">
                            <Button
                              size="sm"
                              onClick={() => handleSelectSAPAICoreModel(model)}
                              disabled={model.status !== "RUNNING"}
                            >
                              Select
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {sapAICoreModels.length === 0 && !loadingSAPAICore && (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                Enter your SAP AI Core credentials, then click "Discover Models"
              </div>
            )}
          </div>
          <DialogFooter className="border-t pt-4">
            <Button variant="outline" onClick={() => {
              setShowSAPAICoreDialog(false);
              setSapAuthUrl("");
              setSapApiUrl("");
              setSapClientId("");
              setSapClientSecret("");
              setSapResourceGroup("default");
              setSapIdentityZone("");
              setSapIdentityZoneId("");
              setSapAICoreModels([]);
            }}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Switch Confirmation Dialog */}
      <AlertDialog open={showSwitchConfirmDialog} onOpenChange={setShowSwitchConfirmDialog}>
        <AlertDialogContent className="bg-white dark:bg-gray-900">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-gray-900 dark:text-gray-100">
              Switch Model Source?
            </AlertDialogTitle>
            <div className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
              <p>
                Switching from <strong>{modelSource === "litellm" ? "LiteLLM" : "SAP AI Core"}</strong> to{" "}
                <strong>{pendingModelSource === "litellm" ? "LiteLLM" : "SAP AI Core"}</strong> will:
              </p>
              <ul className="list-disc list-inside space-y-1">
                <li>Delete all existing credentials ({credentials?.length || 0} credential{credentials?.length !== 1 ? 's' : ''})</li>
                <li>Clear all model configurations</li>
                <li>Reset default model selections</li>
              </ul>
              <p className="font-semibold text-orange-600 dark:text-orange-400">
                This action cannot be undone.
              </p>
            </div>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => {
              setShowSwitchConfirmDialog(false);
              setPendingModelSource(null);
            }}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => pendingModelSource && performModelSourceSwitch(pendingModelSource)}
              className="bg-orange-600 hover:bg-orange-700"
            >
              Switch & Delete All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
