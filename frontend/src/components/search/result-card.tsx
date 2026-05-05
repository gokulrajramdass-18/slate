"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExternalLink, FileText, Globe, Youtube, Clock } from "lucide-react";
import type { SearchResult } from "@/lib/types";

interface ResultCardProps {
  result: SearchResult;
  onOpen?: (id: string) => void;
}

const sourceIcons = {
  file: FileText,
  url: Globe,
  youtube: Youtube,
  text: FileText,
  hana_table: FileText,
  api: FileText,
};

const sourceTypeLabels = {
  file: "File",
  url: "Web Page",
  youtube: "YouTube",
  text: "Text",
  hana_table: "HANA Table",
  api: "API",
};

export function ResultCard({ result, onOpen }: ResultCardProps) {
  const Icon = sourceIcons[result.source_type] || FileText;
  const typeLabel = sourceTypeLabels[result.source_type] || result.source_type;

  // Format the date
  const formatDate = (dateString?: string) => {
    if (!dateString) return null;
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      });
    } catch {
      return null;
    }
  };

  // Truncate content intelligently
  const truncateContent = (text: string, maxLength: number = 300) => {
    if (text.length <= maxLength) return text;
    const truncated = text.slice(0, maxLength);
    const lastSpace = truncated.lastIndexOf(' ');
    return truncated.slice(0, lastSpace) + '...';
  };

  return (
    <Card className="hover:shadow-md transition-all hover:border-primary/50 cursor-pointer" onClick={() => onOpen?.(result.id)}>
      <CardContent className="p-5">
        {/* Header: Title and Source Type */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-base text-gray-900 dark:text-gray-100 line-clamp-2 mb-2">
              {result.title}
            </h3>
            <div className="flex items-center gap-3 text-xs text-gray-500 dark:text-gray-400">
              <div className="flex items-center gap-1.5">
                <Icon className="w-3.5 h-3.5" />
                <span>{typeLabel}</span>
              </div>
              {result.metadata?.created && (
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5" />
                  <span>{formatDate(result.metadata.created)}</span>
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <span className="text-primary font-medium">
                  {Math.round(result.score * 100)}% match
                </span>
              </div>
            </div>
          </div>
          <Button
            size="sm"
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation();
              onOpen?.(result.id);
            }}
            className="flex-shrink-0"
          >
            <ExternalLink className="w-4 h-4" />
          </Button>
        </div>

        {/* Content Preview */}
        {result.content && (
          <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            {truncateContent(result.content)}
          </p>
        )}

        {/* Highlights */}
        {result.highlights && result.highlights.length > 0 && (
          <div className="space-y-2 mb-3 p-3 bg-yellow-50 dark:bg-yellow-900/10 rounded-md border border-yellow-200 dark:border-yellow-900/30">
            <p className="text-xs font-semibold text-yellow-800 dark:text-yellow-300 uppercase tracking-wide">
              Matched Text:
            </p>
            {result.highlights.slice(0, 2).map((highlight, i) => (
              <div
                key={i}
                className="text-sm text-gray-700 dark:text-gray-300"
                dangerouslySetInnerHTML={{ __html: highlight }}
              />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
