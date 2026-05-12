"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { FileText, Trash2, Download, MoreVertical, Upload as UploadIcon } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";
import { useState } from "react";
import { toast } from "sonner";

interface UploadedDocument {
  id: string;
  title: string;
  description?: string;
  document_type: string; // 'pdf', 'word', 'excel', 'powerpoint'
  file_url: string;
  file_size?: number;
  mime_type?: string;
  metadata?: {
    original_filename?: string;
    manually_uploaded?: boolean;
  };
  created_at: string;
  updated_at: string;
}

interface DocumentCardProps {
  document: UploadedDocument;
  onDelete: (documentId: string) => void;
}

const DocumentTypeIcons: Record<string, { icon: React.ReactNode; color: string }> = {
  pdf: { icon: <FileText className="w-4 h-4" />, color: "text-red-500" },
  word: { icon: <FileText className="w-4 h-4" />, color: "text-blue-500" },
  excel: { icon: <FileText className="w-4 h-4" />, color: "text-green-500" },
  powerpoint: { icon: <FileText className="w-4 h-4" />, color: "text-orange-500" },
};

export function DocumentCard({ document, onDelete }: DocumentCardProps) {
  const [downloading, setDownloading] = useState(false);

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to delete "${document.title}"?`)) {
      onDelete(document.id);
    }
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      // Open the S3 URL in a new tab
      window.open(document.file_url, '_blank');
      toast.success("Download started");
    } catch (error) {
      console.error('Failed to download:', error);
      toast.error("Failed to download document");
    } finally {
      setDownloading(false);
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const docTypeInfo = DocumentTypeIcons[document.document_type] || {
    icon: <FileText className="w-4 h-4" />,
    color: "text-gray-500",
  };

  const isManuallyUploaded = document.metadata?.manually_uploaded === true;

  return (
    <Card
      className="hover:bg-accent/50 transition-colors cursor-pointer border-l-4"
      style={{
        borderLeftColor:
          document.document_type === 'pdf' ? '#ef4444' :
          document.document_type === 'word' ? '#3b82f6' :
          document.document_type === 'excel' ? '#22c55e' :
          document.document_type === 'powerpoint' ? '#f97316' : '#9ca3af'
      }}
      onClick={() => window.open(document.file_url, '_blank')}
    >
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5 flex-1 min-w-0">
            <div className={`mt-1 ${docTypeInfo.color}`}>
              {docTypeInfo.icon}
            </div>
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-medium text-sm truncate">{document.title}</p>
                {isManuallyUploaded && (
                  <Badge className="text-[10px] px-1.5 py-0 h-4 bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300">
                    <UploadIcon className="w-2.5 h-2.5 mr-0.5" />
                    Manually Uploaded
                  </Badge>
                )}
              </div>

              {document.description && (
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {document.description}
                </p>
              )}

              <div className="flex items-center gap-2 flex-wrap text-xs text-muted-foreground">
                <span className="capitalize">{document.document_type}</span>
                {document.file_size && (
                  <>
                    <span>•</span>
                    <span>{formatFileSize(document.file_size)}</span>
                  </>
                )}
                {document.metadata?.original_filename && (
                  <>
                    <span>•</span>
                    <span className="truncate max-w-[200px]">
                      {document.metadata.original_filename}
                    </span>
                  </>
                )}
              </div>

              <p className="text-xs text-muted-foreground">
                Uploaded {formatRelativeTime(document.created_at)}
              </p>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                <MoreVertical className="w-3.5 h-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleDownload} disabled={downloading}>
                <Download className="w-4 h-4 mr-2" />
                {downloading ? "Downloading..." : "Download"}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleDelete}
                className="text-destructive focus:text-destructive"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
}
