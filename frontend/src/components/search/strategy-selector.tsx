"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, Target, Zap, Sparkles } from "lucide-react";
import type { SearchStrategy } from "@/lib/types";

const strategies = [
  {
    value: "keyword" as SearchStrategy,
    label: "Keyword",
    icon: Search,
    description: "Fast full-text search with BM25 ranking",
  },
  {
    value: "vector" as SearchStrategy,
    label: "Vector",
    icon: Target,
    description: "Semantic similarity search with embeddings",
  },
  {
    value: "hybrid" as SearchStrategy,
    label: "Hybrid",
    icon: Zap,
    description: "Combines keyword + vector with RRF",
  },
  {
    value: "agentic_rag" as SearchStrategy,
    label: "Agentic RAG",
    icon: Sparkles,
    description: "Multi-step reasoning with AI agent",
  },
];

interface StrategySelectorProps {
  value: SearchStrategy;
  onChange: (value: SearchStrategy) => void;
  disabled?: boolean;
  showDescription?: boolean;
}

export function StrategySelector({
  value,
  onChange,
  disabled,
  showDescription = false,
}: StrategySelectorProps) {
  const currentStrategy = strategies.find((s) => s.value === value);
  const Icon = currentStrategy?.icon || Search;

  return (
    <div className="space-y-1">
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className="w-[180px]">
          <div className="flex items-center gap-2">
            <Icon className="w-4 h-4" />
            <SelectValue />
          </div>
        </SelectTrigger>
        <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
          {strategies.map((strategy) => {
            const StrategyIcon = strategy.icon;
            return (
              <SelectItem key={strategy.value} value={strategy.value}>
                <div className="flex items-center gap-2">
                  <StrategyIcon className="w-4 h-4" />
                  <span>{strategy.label}</span>
                </div>
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
      {showDescription && currentStrategy && (
        <p className="text-xs text-gray-500">{currentStrategy.description}</p>
      )}
    </div>
  );
}

export function StrategyGrid({
  value,
  onChange,
}: {
  value: SearchStrategy;
  onChange: (value: SearchStrategy) => void;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {strategies.map((strategy) => {
        const Icon = strategy.icon;
        const isActive = value === strategy.value;
        return (
          <button
            key={strategy.value}
            onClick={() => onChange(strategy.value)}
            className={`p-4 rounded-lg border-2 transition-all text-left ${
              isActive
                ? "border-primary-600 bg-primary-50 dark:bg-primary-950"
                : "border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700"
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon className={`w-5 h-5 ${isActive ? "text-primary-600" : "text-gray-600"}`} />
              <span className="font-semibold">{strategy.label}</span>
            </div>
            <p className="text-xs text-gray-500">{strategy.description}</p>
          </button>
        );
      })}
    </div>
  );
}
