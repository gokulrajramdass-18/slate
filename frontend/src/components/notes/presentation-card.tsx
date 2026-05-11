"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Presentation, Download, Trash2 } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";
import { useState } from "react";
import { toast } from "sonner";

interface PresentationDocument {
  id: string;
  title: string;
  description?: string;
  document_type: string;
  file_url?: string;
  file_size?: number;
  metadata?: {
    slide_count?: number;
    presentation_id?: string;
  };
  created_at: string;
  updated_at: string;
}

interface PresentationCardProps {
  document: PresentationDocument;
  onDelete?: (documentId: string) => void;
}

export function PresentationCard({ document, onDelete }: PresentationCardProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to delete "${document.title}"?`)) {
      onDelete?.(document.id);
    }
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      // Open download URL in new tab
      window.open(`/api/documents/${document.id}/download`, '_blank');
      toast.success("Presentation download started");
    } catch (error) {
      console.error('Failed to download presentation:', error);
      toast.error("Failed to download presentation");
    } finally {
      setDownloading(false);
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '';
    const kb = bytes / 1024;
    const mb = kb / 1024;
    if (mb >= 1) return `${mb.toFixed(1)} MB`;
    return `${kb.toFixed(0)} KB`;
  };

  return (
    <div
      className="group relative border-b last:border-b-0 hover:bg-blue-50/30 dark:hover:bg-blue-950/10 transition-colors border-gray-200 dark:border-gray-800"
    >
      {/* Single Row Compact Layout */}
      <div className="flex items-center gap-3 py-2.5 px-3">
        {/* Left: Icon + Title + Metadata */}
        <div className="flex-1 min-w-0 flex items-center gap-3">
          <div className="shrink-0">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center">
              <Presentation className="w-4 h-4 text-white" />
            </div>
          </div>

          <div className="flex-1 min-w-0 space-y-0.5">
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-sm truncate">{document.title}</h3>
              <Badge variant="outline" className="text-xs px-1.5 py-0 h-4 shrink-0 bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800">
                Presentation
              </Badge>
            </div>

            {/* Inline Metadata */}
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
              <span className="shrink-0">{formatRelativeTime(document.updated_at)}</span>
              {document.metadata?.slide_count && (
                <span className="shrink-0">• {document.metadata.slide_count} slides</span>
              )}
              {document.file_size && (
                <span className="shrink-0">• {formatFileSize(document.file_size)}</span>
              )}
              {document.description && (
                <span className="truncate opacity-75">
                  • {document.description}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            title="Download presentation"
            className="h-7 w-7 p-0"
            disabled={downloading}
          >
            <Download className="w-3.5 h-3.5" />
          </Button>

          {onDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              className="h-7 w-7 p-0 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
