"use client";

import { useState } from "react";
import { useRouter } from "@/lib/routing/navigation";
import { FileText, Link, Type, Youtube, Database, Plug, MoreVertical, RefreshCw, Trash2, Eye, Sparkles, ChevronLeft, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { BookmarkButton } from "@/components/bookmarks/bookmark-button";
import { formatRelativeTime, cn } from "@/lib/utils";
import { getTagColorStyle } from "@/lib/utils/tag-colors";
import type { Source, SourceType } from "@/lib/types";

interface SourcesTableProps {
  sources: Source[];
  onSync?: (id: string) => void;
  onDelete?: (id: string) => void;
  onRegenerateEmbeddings?: (id: string) => void;
  pageSize?: number;
}

const sourceTypeConfig = {
  file: { icon: FileText, color: "text-blue-600 dark:text-blue-400", bgColor: "bg-blue-50 dark:bg-blue-950" },
  url: { icon: Link, color: "text-green-600 dark:text-green-400", bgColor: "bg-green-50 dark:bg-green-950" },
  text: { icon: Type, color: "text-purple-600 dark:text-purple-400", bgColor: "bg-purple-50 dark:bg-purple-950" },
  youtube: { icon: Youtube, color: "text-red-600 dark:text-red-400", bgColor: "bg-red-50 dark:bg-red-950" },
  hana_table: { icon: Database, color: "text-orange-600 dark:text-orange-400", bgColor: "bg-orange-50 dark:bg-orange-950" },
  api: { icon: Plug, color: "text-cyan-600 dark:text-cyan-400", bgColor: "bg-cyan-50 dark:bg-cyan-950" },
};

const syncStatusConfig = {
  idle: { label: "Ready", color: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300" },
  scheduled: { label: "Scheduled", color: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" },
  syncing: { label: "Syncing", color: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300" },
  embedding: { label: "Embedding", color: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300" },
  completed: { label: "Ready", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" },
  success: { label: "Synced", color: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" },
  error: { label: "Error", color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300" },
  failed: { label: "Failed", color: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300" },
};

export function SourcesTable({ sources, onSync, onDelete, onRegenerateEmbeddings, pageSize = 10 }: SourcesTableProps) {
  const router = useRouter();
  const [currentPage, setCurrentPage] = useState(1);

  // Calculate pagination
  const totalPages = Math.ceil(sources.length / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = startIndex + pageSize;
  const paginatedSources = sources.slice(startIndex, endIndex);

  // Reset to page 1 when sources change
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handleView = (sourceId: string) => {
    router.push(`/sources/${sourceId}`);
  };

  return (
    <div className="space-y-4">
      <div className="border rounded-lg overflow-hidden bg-white dark:bg-gray-900">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50 dark:bg-gray-800">
              <TableHead className="w-[40px]"></TableHead>
              <TableHead className="font-semibold">Title</TableHead>
              <TableHead className="font-semibold w-[120px]">Type</TableHead>
              <TableHead className="font-semibold w-[120px]">Status</TableHead>
              <TableHead className="font-semibold w-[100px]">Chunks</TableHead>
              <TableHead className="font-semibold w-[150px]">Last Updated</TableHead>
              <TableHead className="w-[100px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedSources.map((source) => {
              const config = sourceTypeConfig[source.source_type];
              const Icon = config.icon;

              return (
                <TableRow
                  key={source.id}
                  className="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
                  onClick={() => handleView(source.id)}
                >
                  {/* Icon */}
                  <TableCell>
                    <div className={cn("p-2 rounded-md inline-flex", config.bgColor)}>
                      <Icon className={cn("w-4 h-4", config.color)} />
                    </div>
                  </TableCell>

                  {/* Title */}
                  <TableCell>
                    <div className="flex flex-col gap-1">
                      <span className="font-medium">{source.title}</span>
                      {source.full_text && (
                        <span className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
                          {source.full_text}
                        </span>
                      )}
                      {/* Tags */}
                      {source.tags && source.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {source.tags.map((tag) => {
                            const colorStyle = getTagColorStyle(tag);
                            return (
                              <Badge
                                key={tag}
                                className="text-xs px-2 py-0 h-5 border font-medium"
                                style={{
                                  backgroundColor: colorStyle.backgroundColor,
                                  color: colorStyle.color,
                                  borderColor: colorStyle.borderColor,
                                }}
                              >
                                {tag}
                              </Badge>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </TableCell>

                  {/* Type */}
                  <TableCell>
                    <Badge variant="outline" className="text-xs capitalize">
                      {source.source_type.replace("_", " ")}
                    </Badge>
                  </TableCell>

                  {/* Status */}
                  <TableCell>
                    {source.sync_status && syncStatusConfig[source.sync_status] ? (
                      <Badge className={cn("text-xs", syncStatusConfig[source.sync_status].color)}>
                        {syncStatusConfig[source.sync_status].label}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className="text-xs text-gray-500">
                        -
                      </Badge>
                    )}
                  </TableCell>

                  {/* Chunks */}
                  <TableCell>
                    {source.chunk_count !== undefined && source.chunk_count > 0 ? (
                      <div className="flex items-center gap-1 text-sm">
                        <Sparkles className="w-3 h-3 text-purple-500" />
                        <span>{source.chunk_count}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">-</span>
                    )}
                  </TableCell>

                  {/* Last Updated */}
                  <TableCell className="text-sm text-gray-500">
                    {formatRelativeTime(source.updated)}
                  </TableCell>

                  {/* Actions */}
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center gap-1 justify-end">
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
                          <DropdownMenuItem onClick={() => handleView(source.id)}>
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
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-2">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Showing {startIndex + 1}-{Math.min(endIndex, sources.length)} of {sources.length} sources
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
            >
              <ChevronLeft className="w-4 h-4 mr-1" />
              Previous
            </Button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => {
                // Show first page, last page, current page, and pages around current
                const showPage =
                  page === 1 ||
                  page === totalPages ||
                  (page >= currentPage - 1 && page <= currentPage + 1);

                if (!showPage) {
                  // Show ellipsis
                  if (page === currentPage - 2 || page === currentPage + 2) {
                    return (
                      <span key={page} className="px-2 text-gray-400">
                        ...
                      </span>
                    );
                  }
                  return null;
                }

                return (
                  <Button
                    key={page}
                    variant={currentPage === page ? "default" : "outline"}
                    size="sm"
                    onClick={() => handlePageChange(page)}
                    className="min-w-[36px]"
                  >
                    {page}
                  </Button>
                );
              })}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              Next
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
