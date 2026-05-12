"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSources, useDeleteSource, useSyncSource } from "@/lib/hooks/use-api";
import { sourcesApi } from "@/lib/api/sources";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { SourcesTable } from "@/components/sources/sources-table";
import { Plus, Search, FileText, FileTextIcon, Link, Type, Youtube, Database, Plug, Star, X, Tag } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { getTagColorStyle } from "@/lib/utils/tag-colors";
import type { SourceType } from "@/lib/types";

// Source type groups configuration
const sourceTypeGroups = {
  file: {
    label: "File Sources",
    icon: FileTextIcon,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-950",
  },
  url: {
    label: "Web Sources",
    icon: Link,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-50 dark:bg-green-950",
  },
  text: {
    label: "Text Sources",
    icon: Type,
    color: "text-purple-600 dark:text-purple-400",
    bgColor: "bg-purple-50 dark:bg-purple-950",
  },
  youtube: {
    label: "YouTube Sources",
    icon: Youtube,
    color: "text-red-600 dark:text-red-400",
    bgColor: "bg-red-50 dark:bg-red-950",
  },
  hana_table: {
    label: "HANA Sources",
    icon: Database,
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-50 dark:bg-orange-950",
  },
  api: {
    label: "API Sources",
    icon: Plug,
    color: "text-cyan-600 dark:text-cyan-400",
    bgColor: "bg-cyan-50 dark:bg-cyan-950",
  },
};

export default function SourcesPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<SourceType | "all">("all");
  const [showBookmarkedOnly, setShowBookmarkedOnly] = useState(false);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 3;

  const { data: sources = [], isLoading, refetch } = useSources();
  const deleteMutation = useDeleteSource();
  const syncMutation = useSyncSource();

  // Check if any sources are currently processing embeddings
  const hasActiveEmbeddings = sources.some(
    (source) => source.sync_status === "embedding" || source.sync_status === "syncing"
  );

  // Poll for updates when embeddings are being generated
  useEffect(() => {
    if (!hasActiveEmbeddings) return;

    const pollInterval = setInterval(() => {
      console.log("🔄 Polling for embedding status updates...");
      refetch();
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(pollInterval);
  }, [hasActiveEmbeddings, refetch]);

  // Get all unique tags from sources
  const allTags = Array.from(
    new Set(sources.flatMap((source) => source.tags || []))
  ).sort();

  const filteredSources = sources.filter((source) => {
    const matchesSearch = source.title.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = activeTab === "all" || source.source_type === activeTab;
    const matchesBookmark = !showBookmarkedOnly || source.is_bookmarked;
    const matchesTags = selectedTags.length === 0 || selectedTags.some((tag) => source.tags?.includes(tag));
    return matchesSearch && matchesType && matchesBookmark && matchesTags;
  });

  // Pagination
  const totalPages = Math.ceil(filteredSources.length / itemsPerPage);
  const paginatedSources = filteredSources.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Reset to page 1 when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, activeTab, showBookmarkedOnly, selectedTags]);

  // Group sources by type
  const groupedSources = sources.reduce((acc, source) => {
    const type = source.source_type;
    if (!acc[type]) {
      acc[type] = [];
    }
    acc[type].push(source);
    return acc;
  }, {} as Record<SourceType, typeof sources>);

  // Calculate counts for each type
  const typeCounts = Object.entries(groupedSources).reduce((acc, [type, sources]) => {
    acc[type as SourceType] = sources.length;
    return acc;
  }, {} as Record<SourceType, number>);

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this source?")) return;

    try {
      await deleteMutation.mutateAsync(id);
      toast.success("Source deleted successfully");
    } catch (error: any) {
      toast.error(error.message || "Failed to delete source");
    }
  };

  const handleSync = async (id: string) => {
    try {
      await syncMutation.mutateAsync(id);
      toast.success("Sync started successfully");
    } catch (error: any) {
      toast.error(error.message || "Failed to start sync");
    }
  };

  const handleRegenerateEmbeddings = async (id: string) => {
    try {
      toast.loading("Starting embedding generation...");
      const result = await sourcesApi.regenerateEmbeddings(id);
      toast.dismiss();
      toast.success(result.message || "Embedding generation started");

      // Immediately refetch to show "embedding" status
      refetch();
    } catch (error: any) {
      toast.dismiss();
      toast.error(error.message || "Failed to start embedding generation");
    }
  };

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between animate-fade-in-up">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
            Sources
            {hasActiveEmbeddings && (
              <span className="inline-flex items-center gap-1 text-sm font-normal text-blue-600 dark:text-blue-400">
                <span className="animate-spin">⚙️</span>
                Processing embeddings...
              </span>
            )}
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            Manage your research sources from multiple types
          </p>
        </div>
        <Button onClick={() => router.push("/sources/new")} className="transition-all hover:scale-105 hover:shadow-lg">
          <Plus className="w-4 h-4 mr-2" />
          Add Source
        </Button>
      </div>

      {/* Filters */}
      <div className="space-y-3 animate-fade-in-up animation-delay-200">
        <div className="flex gap-4 flex-col sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              placeholder="Search sources..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Button
            variant={showBookmarkedOnly ? "default" : "outline"}
            size="default"
            onClick={() => setShowBookmarkedOnly(!showBookmarkedOnly)}
          >
            <Star className={cn("w-4 h-4 mr-2", showBookmarkedOnly && "fill-current")} />
            {showBookmarkedOnly ? "Bookmarked" : "All"}
          </Button>
        </div>

        {/* Tag Filter */}
        {allTags.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <Tag className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-500 dark:text-gray-400">Filter by tags:</span>
            {allTags.map((tag) => {
              const isSelected = selectedTags.includes(tag);
              const colorStyle = getTagColorStyle(tag);
              return (
                <Badge
                  key={tag}
                  className={cn(
                    "cursor-pointer hover:scale-105 transition-all border font-medium",
                    isSelected && "ring-2 ring-offset-2 ring-offset-background"
                  )}
                  style={{
                    backgroundColor: colorStyle.backgroundColor,
                    color: colorStyle.color,
                    borderColor: colorStyle.borderColor,
                  }}
                  onClick={() => {
                    setSelectedTags((prev) =>
                      prev.includes(tag)
                        ? prev.filter((t) => t !== tag)
                        : [...prev, tag]
                    );
                  }}
                >
                  {tag}
                  {isSelected && (
                    <X className="w-3 h-3 ml-1" />
                  )}
                </Badge>
              );
            })}
            {selectedTags.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedTags([])}
                className="h-6 text-xs"
              >
                Clear filters
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Tab-based Sources List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="p-6">
                <div className="space-y-3">
                  <Skeleton className="h-6 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as SourceType | "all")}>
          <TabsList className="w-full justify-start overflow-x-auto bg-gray-100 dark:bg-gray-900 p-1 rounded-lg h-12">
            <TabsTrigger value="all" className="flex items-center gap-2 text-sm font-semibold">
              <FileText className="w-4 h-4" />
              All
              {sources.length > 0 && (
                <span className="ml-1 inline-flex items-center justify-center rounded-full bg-gray-500 px-2 py-0.5 text-xs font-semibold text-white">
                  {sources.length}
                </span>
              )}
            </TabsTrigger>
            {Object.entries(sourceTypeGroups).map(([type, config]) => {
              const Icon = config.icon;
              const count = typeCounts[type as SourceType] || 0;
              if (count === 0) return null;

              // Define badge colors for each source type
              const badgeColors: Record<string, string> = {
                file: "bg-gray-500",
                url: "bg-gray-500",
                text: "bg-gray-500",
                youtube: "bg-gray-500",
                hana_table: "bg-gray-500",
                api: "bg-gray-500",
              };

              return (
                <TabsTrigger key={type} value={type} className="flex items-center gap-2 text-sm font-semibold">
                  <Icon className={cn("w-4 h-4", config.color)} />
                  {config.label}
                  <span className={cn(
                    "ml-1 inline-flex items-center justify-center rounded-full px-2 py-0.5 text-xs font-semibold text-white",
                    badgeColors[type] || "bg-gray-500"
                  )}>
                    {count}
                  </span>
                </TabsTrigger>
              );
            })}
          </TabsList>

          {/* All Tab */}
          <TabsContent value="all" className="mt-6">
            {filteredSources.length > 0 ? (
              <div className="space-y-4">
                <SourcesTable
                  sources={paginatedSources}
                  onSync={handleSync}
                  onDelete={handleDelete}
                  onRegenerateEmbeddings={handleRegenerateEmbeddings}
                />

                {/* Pagination Controls */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between border-t pt-4">
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      Showing {(currentPage - 1) * itemsPerPage + 1} to{" "}
                      {Math.min(currentPage * itemsPerPage, filteredSources.length)} of{" "}
                      {filteredSources.length} results
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                      >
                        Previous
                      </Button>
                      {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                        <Button
                          key={page}
                          variant={currentPage === page ? "default" : "outline"}
                          size="sm"
                          onClick={() => setCurrentPage(page)}
                          className="w-10"
                        >
                          {page}
                        </Button>
                      ))}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <Card>
                <CardContent className="flex flex-col items-center justify-center py-16">
                  <FileText className="w-16 h-16 text-gray-400 mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                    {searchQuery || showBookmarkedOnly ? "No sources found" : "No sources yet"}
                  </h3>
                  <p className="text-gray-500 dark:text-gray-400 text-center mb-6 max-w-md">
                    {searchQuery || showBookmarkedOnly
                      ? "No sources match your filters. Try adjusting your search or filter."
                      : "Add your first source to start building your research library."}
                  </p>
                  {!searchQuery && !showBookmarkedOnly && (
                    <Button onClick={() => router.push("/sources/new")}>
                      <Plus className="w-4 h-4 mr-2" />
                      Add Source
                    </Button>
                  )}
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Individual Type Tabs */}
          {Object.entries(sourceTypeGroups).map(([type, config]) => {
            const Icon = config.icon;
            const sourcesForType = filteredSources.filter((s) => s.source_type === type);
            const totalPagesForType = Math.ceil(sourcesForType.length / itemsPerPage);
            const paginatedSourcesForType = sourcesForType.slice(
              (currentPage - 1) * itemsPerPage,
              currentPage * itemsPerPage
            );

            return (
              <TabsContent key={type} value={type} className="mt-6">
                {sourcesForType.length > 0 ? (
                  <div className="space-y-4">
                    <SourcesTable
                      sources={paginatedSourcesForType}
                      onSync={handleSync}
                      onDelete={handleDelete}
                      onRegenerateEmbeddings={handleRegenerateEmbeddings}
                    />

                    {/* Pagination Controls */}
                    {totalPagesForType > 1 && (
                      <div className="flex items-center justify-between border-t pt-4">
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          Showing {(currentPage - 1) * itemsPerPage + 1} to{" "}
                          {Math.min(currentPage * itemsPerPage, sourcesForType.length)} of{" "}
                          {sourcesForType.length} results
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                            disabled={currentPage === 1}
                          >
                            Previous
                          </Button>
                          {Array.from({ length: totalPagesForType }, (_, i) => i + 1).map((page) => (
                            <Button
                              key={page}
                              variant={currentPage === page ? "default" : "outline"}
                              size="sm"
                              onClick={() => setCurrentPage(page)}
                              className="w-10"
                            >
                              {page}
                            </Button>
                          ))}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage((p) => Math.min(totalPagesForType, p + 1))}
                            disabled={currentPage === totalPagesForType}
                          >
                            Next
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <Card>
                    <CardContent className="flex flex-col items-center justify-center py-16">
                      <Icon className={cn("w-16 h-16 mb-4", config.color)} />
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
                        {searchQuery || showBookmarkedOnly ? "No sources found" : `No ${config.label.toLowerCase()} yet`}
                      </h3>
                      <p className="text-gray-500 dark:text-gray-400 text-center mb-6 max-w-md">
                        {searchQuery || showBookmarkedOnly
                          ? `No ${config.label.toLowerCase()} match your filters.`
                          : `Add your first ${config.label.toLowerCase().replace(" sources", "")} source.`}
                      </p>
                      {!searchQuery && !showBookmarkedOnly && (
                        <Button onClick={() => router.push("/sources/new")}>
                          <Plus className="w-4 h-4 mr-2" />
                          Add Source
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}
      </div>
    </div>
  );
}
