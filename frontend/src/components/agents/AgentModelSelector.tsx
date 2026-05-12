"use client";

import { useQuery } from "@tanstack/react-query";
import { Cpu, Loader2, AlertCircle } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { modelsApi } from "@/lib/api/models";
import type { Model } from "@/lib/types";

interface AgentModelSelectorProps {
  selectedModelName?: string;
  onSelect: (model: Model) => void;
  label?: string;
  description?: string;
}

export function AgentModelSelector({
  selectedModelName,
  onSelect,
  label = "Language Model",
  description,
}: AgentModelSelectorProps) {
  const { data: models = [], isLoading, error } = useQuery({
    queryKey: ["models", "language"],
    queryFn: () => modelsApi.list("language"),
  });

  // Find by model name (since backend uses model_name field)
  const selectedModel = models.find((m) => m.name === selectedModelName);

  // Use a special value for "no selection" instead of empty string
  const UNSELECTED = "__unselected__";
  const selectValue = selectedModel?.id || UNSELECTED;

  return (
    <div className="space-y-3">
      <div>
        <Label className="text-sm font-medium">{label}</Label>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </div>

      <Select
        value={selectValue}
        onValueChange={(id) => {
          if (id === UNSELECTED) {
            // Clear selection - pass an empty model object to trigger clearing
            onSelect({ id: "", name: "", provider: "", type: "language" } as Model);
          } else {
            const model = models.find((m) => m.id === id);
            if (model) onSelect(model);
          }
        }}
        disabled={isLoading || !!error}
      >
        <SelectTrigger>
          <SelectValue
            placeholder={
              isLoading
                ? "Loading models..."
                : error
                ? "Error loading models"
                : "Select a model (optional)"
            }
          />
        </SelectTrigger>
        <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
          {isLoading ? (
            <div className="p-4 text-center">
              <Loader2 className="h-5 w-5 animate-spin mx-auto text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="p-4 text-center">
              <AlertCircle className="h-5 w-5 mx-auto text-destructive mb-2" />
              <p className="text-xs text-muted-foreground">
                Failed to load models
              </p>
            </div>
          ) : models.length === 0 ? (
            <div className="p-4 text-center">
              <p className="text-sm text-muted-foreground">
                No models configured
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Add API keys in Settings to see available models
              </p>
            </div>
          ) : (
            <>
              {/* Clear selection option */}
              <SelectItem value={UNSELECTED}>
                <span className="text-muted-foreground italic">
                  Use default model
                </span>
              </SelectItem>
              {models.map((model) => (
                <SelectItem key={model.id} value={model.id}>
                  <div className="flex items-center gap-2">
                    <Cpu className="w-4 h-4 shrink-0" />
                    <span>{model.name}</span>
                    <Badge variant="outline" className="text-xs">
                      {model.provider}
                    </Badge>
                  </div>
                </SelectItem>
              ))}
            </>
          )}
        </SelectContent>
      </Select>

      {/* Selected Model Details */}
      {selectedModel && (
        <div className="p-3 bg-muted rounded-lg border">
          <div className="flex items-start gap-2">
            <Cpu className="w-4 h-4 mt-0.5 text-muted-foreground" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium">{selectedModel.name}</div>
              <div className="flex flex-wrap gap-1.5 mt-2">
                <Badge variant="secondary" className="text-xs">
                  {selectedModel.provider}
                </Badge>
                <Badge variant="secondary" className="text-xs">
                  {selectedModel.type}
                </Badge>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
