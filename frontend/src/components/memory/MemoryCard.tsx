"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Brain,
  BookOpen,
  Cog,
  Zap,
  Trash2,
  Edit,
  Tag,
  Clock,
  Eye,
} from "lucide-react";
import type { Memory, MemoryType, MemoryPriority } from "@/lib/types";

interface MemoryCardProps {
  memory: Memory;
  onEdit?: (memory: Memory) => void;
  onDelete?: (memoryId: string) => void;
  relevanceScore?: number;
}

const typeConfig: Record<
  MemoryType,
  { icon: React.ElementType; color: string; bgColor: string; label: string }
> = {
  episodic: {
    icon: Clock,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-100 dark:bg-blue-900",
    label: "Episodic",
  },
  semantic: {
    icon: BookOpen,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-100 dark:bg-purple-900",
    label: "Semantic",
  },
  procedural: {
    icon: Cog,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-100 dark:bg-emerald-900",
    label: "Procedural",
  },
  working: {
    icon: Zap,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-100 dark:bg-amber-900",
    label: "Working",
  },
};

const priorityColors: Record<MemoryPriority, string> = {
  low: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  medium: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400",
  high: "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-400",
  critical: "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-400",
};

export function MemoryCard({ memory, onEdit, onDelete, relevanceScore }: MemoryCardProps) {
  const config = typeConfig[memory.memory_type];
  const TypeIcon = config.icon;

  const isExpired = memory.expires_at && new Date(memory.expires_at) < new Date();

  return (
    <Card
      className={`transition-all hover:shadow-sm ${
        isExpired ? "opacity-60 border-dashed" : ""
      }`}
    >
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <div className={`p-1.5 rounded-md ${config.bgColor}`}>
              <TypeIcon className={`h-3.5 w-3.5 ${config.color}`} />
            </div>
            <div>
              <Badge variant="outline" className="text-[10px]">
                {config.label}
              </Badge>
              {relevanceScore !== undefined && (
                <Badge variant="secondary" className="text-[10px] ml-1">
                  {(relevanceScore * 100).toFixed(0)}% match
                </Badge>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Badge className={`${priorityColors[memory.priority]} text-[10px]`}>
              {memory.priority}
            </Badge>
            {onEdit && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0"
                onClick={() => onEdit(memory)}
              >
                <Edit className="h-3.5 w-3.5" />
              </Button>
            )}
            {onDelete && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-red-500 hover:text-red-700"
                onClick={() => onDelete(memory.id)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>

        {/* Summary/Content */}
        {memory.summary && (
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {memory.summary}
          </p>
        )}
        <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3 whitespace-pre-wrap">
          {memory.content}
        </p>

        {/* Tags */}
        {memory.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {memory.tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-[10px] px-1.5 py-0">
                <Tag className="h-2.5 w-2.5 mr-0.5" />
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between text-[10px] text-gray-400 pt-1 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-3">
            {memory.source_agent_name && (
              <span>
                <Brain className="h-3 w-3 inline mr-0.5" />
                {memory.source_agent_name}
              </span>
            )}
            <span>
              <Eye className="h-3 w-3 inline mr-0.5" />
              {memory.access_count} accesses
            </span>
          </div>
          <div className="flex items-center gap-2">
            {isExpired && (
              <Badge variant="destructive" className="text-[9px] px-1 py-0">
                Expired
              </Badge>
            )}
            <span>{new Date(memory.created).toLocaleDateString()}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
