"use client";

import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Cpu, CheckCircle, Loader2 } from "lucide-react";
import type { Model } from "@/lib/types";

interface ModelSelectorProps {
  models: Model[];
  selectedId?: string;
  onSelect: (modelId: string) => void;
  onTest?: (modelId: string) => Promise<void>;
  type: "language" | "embedding";
  label: string;
  description: string;
}

export function ModelSelector({
  models,
  selectedId,
  onSelect,
  onTest,
  type,
  label,
  description,
}: ModelSelectorProps) {
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, boolean>>({});

  const filteredModels = models.filter((m) => m.type === type);
  const selectedModel = filteredModels.find((m) => m.id === selectedId);

  const handleTest = async (modelId: string) => {
    if (!onTest) return;
    setTestingId(modelId);
    try {
      await onTest(modelId);
      setTestResults({ ...testResults, [modelId]: true });
    } catch (error) {
      setTestResults({ ...testResults, [modelId]: false });
    } finally {
      setTestingId(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{label}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor={`model-${type}`}>Model</Label>
          <Select value={selectedId} onValueChange={onSelect}>
            <SelectTrigger id={`model-${type}`}>
              <SelectValue placeholder={`Select ${type} model`} />
            </SelectTrigger>
            <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
              {filteredModels.map((model) => (
                <SelectItem key={model.id} value={model.id}>
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4" />
                    <span>{model.name}</span>
                    <Badge variant="outline" className="text-xs">
                      {model.provider}
                    </Badge>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedModel && (
          <div className="p-3 bg-gray-50 dark:bg-gray-900 rounded-lg space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">{selectedModel.name}</span>
              {testResults[selectedModel.id] === true && (
                <CheckCircle className="w-4 h-4 text-green-600" />
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400">
              <Badge variant="secondary">{selectedModel.provider}</Badge>
              <Badge variant="secondary">{selectedModel.type}</Badge>
            </div>
            {onTest && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleTest(selectedModel.id)}
                disabled={testingId === selectedModel.id}
                className="w-full mt-2"
              >
                {testingId === selectedModel.id ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin mr-2" />
                    Testing...
                  </>
                ) : (
                  "Test Model"
                )}
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
