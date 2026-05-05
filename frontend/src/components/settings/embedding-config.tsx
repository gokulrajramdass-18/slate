"use client";

import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface EmbeddingConfigProps {
  chunkSize: number;
  chunkOverlap: number;
  onChange: (config: { chunkSize: number; chunkOverlap: number }) => void;
}

export function EmbeddingConfig({ chunkSize, chunkOverlap, onChange }: EmbeddingConfigProps) {
  const updateChunkSize = (value: number) => {
    onChange({ chunkSize: value, chunkOverlap });
  };

  const updateChunkOverlap = (value: number) => {
    onChange({ chunkSize, chunkOverlap: value });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Embedding Configuration</CardTitle>
        <CardDescription>
          Control how text is chunked before generating embeddings
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="chunk-size">Chunk Size (characters)</Label>
            <span className="text-sm font-medium">{chunkSize}</span>
          </div>
          <Slider
            id="chunk-size"
            min={100}
            max={2000}
            step={100}
            value={[chunkSize]}
            onValueChange={([value]) => updateChunkSize(value)}
          />
          <p className="text-xs text-gray-500">
            Larger chunks preserve more context but reduce granularity. Recommended: 500-1000.
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label htmlFor="chunk-overlap">Chunk Overlap (characters)</Label>
            <span className="text-sm font-medium">{chunkOverlap}</span>
          </div>
          <Slider
            id="chunk-overlap"
            min={0}
            max={Math.min(500, Math.floor(chunkSize * 0.5))}
            step={10}
            value={[chunkOverlap]}
            onValueChange={([value]) => updateChunkOverlap(value)}
          />
          <p className="text-xs text-gray-500">
            Overlap helps preserve context at chunk boundaries. Recommended: 10-20% of chunk size.
          </p>
        </div>

        <div className="p-3 bg-blue-50 dark:bg-blue-950 rounded-lg">
          <p className="text-sm text-blue-700 dark:text-blue-300">
            <strong>Note:</strong> Changing these settings will not affect existing embeddings.
            You'll need to rebuild embeddings for all sources to apply changes.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
