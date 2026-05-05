"use client";

import { useRouter } from "next/navigation";
import { FileText, Link, Type, Youtube, Database, Plug, MoreVertical, RefreshCw, Trash2, Eye, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { BookmarkButton } from "@/components/bookmarks/bookmark-button";
import { formatRelativeTime, cn } from "@/lib/utils";
import type { Source, SourceType } from "@/lib/types";

interface SourceCardProps {
  source: Source;
  onSync?: (id: string) => void;
  onDelete?: (id: string) => void;
  onRegenerateEmbeddings?: (id: string) => void;
}

const sourceTypeConfig = {
  file: { icon: FileText, color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
  url: { icon: Link, color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" },
  text: { icon: Type, color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300" },
  youtube: { icon: Youtube, color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300" },
  hana_table: { icon: Database, color: "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300" },
  api: { icon: Plug, color: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-300" },
};

const syncStatusConfig = {
  idle: { label: "Ready", color: "bg-gray-100 text-gray-700" },
  scheduled: { label: "Scheduled", color: "bg-blue-100 text-blue-700" },
  syncing: { label: "Syncing...", color: "bg-yellow-100 text-yellow-700" },
  embedding: { label: "Embedding...", color: "bg-purple-100 text-purple-700" },
  completed: { label: "Ready", color: "bg-green-100 text-green-700" },
  success: { label: "Synced", color: "bg-green-100 text-green-700" },
  error: { label: "Error", color: "bg-red-100 text-red-700" },
  failed: { label: "Failed", color: "bg-red-100 text-red-700" },
};

export function SourceCard({ source, onSync, onDelete, onRegenerateEmbeddings }: SourceCardProps) {
  const router = useRouter();
  const config = sourceTypeConfig[source.source_type];
  const Icon = config.icon;

  const handleView = () => {
    router.push(`/sources/${source.id}`);
  };

  return (
    <Card className="hover:shadow-xl hover:scale-[1.02] transition-all duration-300 hover:border-blue-500/30">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <div className={cn("p-2 rounded-md transition-transform hover:scale-110", config.color)}>
                <Icon className="w-4 h-4" />
              </div>
              <h3 className="text-lg font-semibold">{source.title}</h3>
              <Badge className={config.color}>{source.source_type}</Badge>

              {/* Embedding Status Badge */}
              {source.sync_status && syncStatusConfig[source.sync_status] && (
                <Badge className={cn(syncStatusConfig[source.sync_status].color, "animate-pulse-slow")}>
                  {syncStatusConfig[source.sync_status].label}
                </Badge>
              )}

              {/* Chunk Count Badge */}
              {source.chunk_count !== undefined && source.chunk_count > 0 && (
                <Badge variant="outline" className="text-xs transition-all hover:scale-105">
                  <Sparkles className="w-3 h-3 mr-1" />
                  {source.chunk_count} chunks
                </Badge>
              )}

              {/* No Embeddings Badge */}
              {(!source.sync_status || source.sync_status === null) && source.source_type !== "hana_table" && source.source_type !== "api" && (
                <Badge variant="outline" className="text-xs text-gray-500">
                  No embeddings
                </Badge>
              )}
            </div>

            {source.full_text && (
              <p className="text-gray-600 dark:text-gray-400 line-clamp-2 mb-3">
                {source.full_text}
              </p>
            )}

            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span>Updated {formatRelativeTime(source.updated)}</span>
              {source.last_synced && (
                <span>Last sync: {formatRelativeTime(source.last_synced)}</span>
              )}
              {source.tags && source.tags.length > 0 && (
                <div className="flex gap-1">
                  {source.tags.slice(0, 3).map((tag, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs">
                      {tag}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {source.error_message && (
              <p className="text-sm text-red-600 mt-2">{source.error_message}</p>
            )}
          </div>

          <div className="flex items-center gap-1">
            <BookmarkButton
              entityType="source"
              entityId={source.id}
              isBookmarked={source.is_bookmarked}
            />
            <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm">
                <MoreVertical className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
              <DropdownMenuItem onClick={handleView}>
                <Eye className="w-4 h-4 mr-2" />
                View Details
              </DropdownMenuItem>
              {(source.source_type === "hana_table" || source.source_type === "api") && onSync && (
                <DropdownMenuItem onClick={() => onSync(source.id)}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Sync Now
                </DropdownMenuItem>
              )}
              {onRegenerateEmbeddings && (
                <DropdownMenuItem onClick={() => onRegenerateEmbeddings(source.id)}>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Regenerate Embeddings
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              {onDelete && (
                <DropdownMenuItem
                  onClick={() => onDelete(source.id)}
                  className="text-red-600 dark:text-red-400"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
