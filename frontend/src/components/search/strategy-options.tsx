"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { SearchStrategy } from "@/lib/types";

interface StrategyOptionsProps {
  strategy: SearchStrategy;
  config: Record<string, any>;
  onChange: (config: Record<string, any>) => void;
}

export function StrategyOptions({ strategy, config, onChange }: StrategyOptionsProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const updateConfig = (key: string, value: any) => {
    onChange({ ...config, [key]: value });
  };

  const renderKeywordOptions = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="title-boost">Title Boost (1-10)</Label>
        <div className="flex items-center gap-4">
          <Slider
            id="title-boost"
            min={1}
            max={10}
            step={0.5}
            value={[config.title_boost || 2]}
            onValueChange={([value]) => updateConfig("title_boost", value)}
            className="flex-1"
          />
          <span className="text-sm font-medium w-12 text-right">
            {config.title_boost || 2}x
          </span>
        </div>
        <p className="text-xs text-gray-500">Boost importance of title matches</p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="min-score">Minimum Score (0-1)</Label>
        <div className="flex items-center gap-4">
          <Slider
            id="min-score"
            min={0}
            max={1}
            step={0.05}
            value={[config.min_score || 0.1]}
            onValueChange={([value]) => updateConfig("min_score", value)}
            className="flex-1"
          />
          <span className="text-sm font-medium w-12 text-right">
            {(config.min_score || 0.1).toFixed(2)}
          </span>
        </div>
        <p className="text-xs text-gray-500">Filter out low-relevance results</p>
      </div>
    </div>
  );

  const renderVectorOptions = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="similarity-threshold">Similarity Threshold (0-1)</Label>
        <div className="flex items-center gap-4">
          <Slider
            id="similarity-threshold"
            min={0}
            max={1}
            step={0.05}
            value={[config.similarity_threshold || 0.7]}
            onValueChange={([value]) => updateConfig("similarity_threshold", value)}
            className="flex-1"
          />
          <span className="text-sm font-medium w-12 text-right">
            {(config.similarity_threshold || 0.7).toFixed(2)}
          </span>
        </div>
        <p className="text-xs text-gray-500">Minimum cosine similarity to include result</p>
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="rerank">Enable Reranking</Label>
          <p className="text-xs text-gray-500">Use cross-encoder to rerank results</p>
        </div>
        <Switch
          id="rerank"
          checked={config.rerank || false}
          onCheckedChange={(checked) => updateConfig("rerank", checked)}
        />
      </div>
    </div>
  );

  const renderHybridOptions = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="keyword-weight">Keyword Weight</Label>
        <div className="flex items-center gap-4">
          <Slider
            id="keyword-weight"
            min={0}
            max={1}
            step={0.1}
            value={[config.keyword_weight || 0.5]}
            onValueChange={([value]) => updateConfig("keyword_weight", value)}
            className="flex-1"
          />
          <span className="text-sm font-medium w-16 text-right">
            {((config.keyword_weight || 0.5) * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="vector-weight">Vector Weight</Label>
        <div className="flex items-center gap-4">
          <Slider
            id="vector-weight"
            min={0}
            max={1}
            step={0.1}
            value={[config.vector_weight || 0.5]}
            onValueChange={([value]) => updateConfig("vector_weight", value)}
            className="flex-1"
          />
          <span className="text-sm font-medium w-16 text-right">
            {((config.vector_weight || 0.5) * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      <p className="text-xs text-gray-500">
        Balance between keyword matching and semantic similarity
      </p>
    </div>
  );

  const renderAgenticRAGOptions = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="max-iterations">Max Iterations</Label>
        <Input
          id="max-iterations"
          type="number"
          min={1}
          max={10}
          value={config.max_iterations || 3}
          onChange={(e) => updateConfig("max_iterations", parseInt(e.target.value))}
        />
        <p className="text-xs text-gray-500">Maximum reasoning steps for the AI agent</p>
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="show-reasoning">Show Reasoning Steps</Label>
          <p className="text-xs text-gray-500">Display intermediate thinking process</p>
        </div>
        <Switch
          id="show-reasoning"
          checked={config.show_reasoning !== false}
          onCheckedChange={(checked) => updateConfig("show_reasoning", checked)}
        />
      </div>

      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="include-citations">Include Citations</Label>
          <p className="text-xs text-gray-500">Link answer segments to sources</p>
        </div>
        <Switch
          id="include-citations"
          checked={config.include_citations !== false}
          onCheckedChange={(checked) => updateConfig("include_citations", checked)}
        />
      </div>
    </div>
  );

  const renderOptions = () => {
    switch (strategy) {
      case "keyword":
        return renderKeywordOptions();
      case "vector":
        return renderVectorOptions();
      case "hybrid":
        return renderHybridOptions();
      case "agentic_rag":
        return renderAgenticRAGOptions();
      default:
        return null;
    }
  };

  return (
    <Card>
      <CardHeader
        className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Advanced Options</span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4" />
          ) : (
            <ChevronDown className="w-4 h-4" />
          )}
        </CardTitle>
      </CardHeader>
      {isExpanded && <CardContent>{renderOptions()}</CardContent>}
    </Card>
  );
}
