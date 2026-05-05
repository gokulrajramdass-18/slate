"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { modelsApi, embeddingApi } from "@/lib/api/models";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Cpu, RefreshCw, Save } from "lucide-react";
import { toast } from "sonner";
import { ModelSelector } from "@/components/settings/model-selector";
import { EmbeddingConfig } from "@/components/settings/embedding-config";
import { SettingsHeader } from "@/components/settings/settings-header";

export default function ModelsSettingsPage() {
  const queryClient = useQueryClient();
  const [showRebuildDialog, setShowRebuildDialog] = useState(false);

  const { data: models } = useQuery({
    queryKey: ["models"],
    queryFn: () => modelsApi.list(),
  });

  const { data: defaults } = useQuery({
    queryKey: ["models-defaults"],
    queryFn: modelsApi.getDefaults,
  });

  const { data: embeddingConfig } = useQuery({
    queryKey: ["embedding-config"],
    queryFn: embeddingApi.getConfig,
  });

  const [selectedLanguageModel, setSelectedLanguageModel] = useState<string>();
  const [selectedEmbeddingModel, setSelectedEmbeddingModel] = useState<string>();
  const [chunkSize, setChunkSize] = useState(500);
  const [chunkOverlap, setChunkOverlap] = useState(50);

  // Update local state when data loads
  useState(() => {
    if (defaults) {
      setSelectedLanguageModel(defaults.language_model_id);
      setSelectedEmbeddingModel(defaults.embedding_model_id);
    }
  });

  useState(() => {
    if (embeddingConfig) {
      setChunkSize(embeddingConfig.chunk_size);
      setChunkOverlap(embeddingConfig.chunk_overlap);
    }
  });

  const updateDefaultsMutation = useMutation({
    mutationFn: modelsApi.updateDefaults,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["models-defaults"] });
      toast.success("Model defaults updated successfully");
    },
    onError: () => {
      toast.error("Failed to update model defaults");
    },
  });

  const updateEmbeddingConfigMutation = useMutation({
    mutationFn: embeddingApi.updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["embedding-config"] });
      toast.success("Embedding configuration updated");
    },
    onError: () => {
      toast.error("Failed to update embedding configuration");
    },
  });

  const rebuildEmbeddingsMutation = useMutation({
    mutationFn: embeddingApi.rebuild,
    onSuccess: (data) => {
      toast.success(data.message);
      setShowRebuildDialog(false);
    },
    onError: () => {
      toast.error("Failed to rebuild embeddings");
    },
  });

  const testModelMutation = useMutation({
    mutationFn: modelsApi.test,
    onSuccess: (data) => {
      toast.success(data.message);
    },
    onError: () => {
      toast.error("Model test failed");
    },
  });

  const handleSaveDefaults = () => {
    updateDefaultsMutation.mutate({
      language_model_id: selectedLanguageModel,
      embedding_model_id: selectedEmbeddingModel,
    });
  };

  const handleSaveEmbeddingConfig = () => {
    updateEmbeddingConfigMutation.mutate({
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
    });
  };

  const handleTestModel = async (modelId: string) => {
    await testModelMutation.mutateAsync(modelId);
  };

  const handleRebuildEmbeddings = () => {
    rebuildEmbeddingsMutation.mutate();
  };

  const hasChanges =
    selectedLanguageModel !== defaults?.language_model_id ||
    selectedEmbeddingModel !== defaults?.embedding_model_id;

  const hasEmbeddingChanges =
    chunkSize !== embeddingConfig?.chunk_size ||
    chunkOverlap !== embeddingConfig?.chunk_overlap;

  return (
    <div className="space-y-6 max-w-4xl">
      <SettingsHeader
        title="AI Models"
        description="Configure AI models for chat, embeddings, and transformations"
      />

      {/* Language Model Selector */}
      <ModelSelector
        models={models || []}
        selectedId={selectedLanguageModel || defaults?.language_model_id}
        onSelect={setSelectedLanguageModel}
        onTest={handleTestModel}
        type="language"
        label="Language Model"
        description="Used for chat, summarization, and text generation"
      />

      {/* Embedding Model Selector */}
      <ModelSelector
        models={models || []}
        selectedId={selectedEmbeddingModel || defaults?.embedding_model_id}
        onSelect={setSelectedEmbeddingModel}
        onTest={handleTestModel}
        type="embedding"
        label="Embedding Model"
        description="Used for semantic search and vector similarity"
      />

      {/* Save Defaults Button */}
      {hasChanges && (
        <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950">
          <CardContent className="flex items-center justify-between pt-4">
            <p className="text-sm text-blue-700 dark:text-blue-300">
              You have unsaved model changes
            </p>
            <Button
              onClick={handleSaveDefaults}
              disabled={updateDefaultsMutation.isPending}
              className="flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              Save Changes
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Embedding Configuration */}
      <EmbeddingConfig
        chunkSize={chunkSize}
        chunkOverlap={chunkOverlap}
        onChange={({ chunkSize: newSize, chunkOverlap: newOverlap }) => {
          setChunkSize(newSize);
          setChunkOverlap(newOverlap);
        }}
      />

      {/* Save Embedding Config Button */}
      {hasEmbeddingChanges && (
        <Card className="border-blue-200 bg-blue-50 dark:bg-blue-950">
          <CardContent className="flex items-center justify-between pt-4">
            <p className="text-sm text-blue-700 dark:text-blue-300">
              You have unsaved embedding configuration changes
            </p>
            <Button
              onClick={handleSaveEmbeddingConfig}
              disabled={updateEmbeddingConfigMutation.isPending}
              className="flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              Save Configuration
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Rebuild Embeddings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="w-5 h-5" />
            Rebuild Embeddings
          </CardTitle>
          <CardDescription>
            Regenerate all embeddings with the current model and configuration
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="outline"
            onClick={() => setShowRebuildDialog(true)}
            disabled={rebuildEmbeddingsMutation.isPending}
          >
            Rebuild All Embeddings
          </Button>
          <p className="text-xs text-gray-500 mt-2">
            This will regenerate embeddings for all sources. This may take several minutes depending
            on the number of sources.
          </p>
        </CardContent>
      </Card>

      {/* Rebuild Confirmation Dialog */}
      <AlertDialog open={showRebuildDialog} onOpenChange={setShowRebuildDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rebuild all embeddings?</AlertDialogTitle>
            <AlertDialogDescription>
              This will regenerate embeddings for all sources using the current embedding model and
              configuration. This process may take several minutes and cannot be cancelled once
              started.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRebuildEmbeddings}
              disabled={rebuildEmbeddingsMutation.isPending}
            >
              Rebuild Embeddings
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
