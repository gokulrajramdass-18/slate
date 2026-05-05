"use client";

import { useState, useMemo } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { BookmarkButton } from "@/components/bookmarks/bookmark-button";
import { BookmarkDialog } from "@/components/bookmarks/bookmark-dialog";
import { useBookmarks, useToggleBookmark } from "@/lib/hooks/use-api";
import Link from "next/link";
import {
  FileText,
  Folder,
  StickyNote,
  Star,
  Link as LinkIcon,
  Type,
  Youtube,
  Database,
  Plug,
  Search,
  Sparkles,
  ExternalLink,
  Plus,
  Tag,
  FolderOpen,
} from "lucide-react";
import type { BookmarkEntityType, EnrichedBookmark, SourceType } from "@/lib/types";
import { formatRelativeTime, cn } from "@/lib/utils";
import { toast } from "sonner";

const sourceTypeConfig = {
  file: {
    icon: FileText,
    label: "File",
    color: "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400"
  },
  url: {
    icon: LinkIcon,
    label: "URL",
    color: "bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400"
  },
  text: {
    icon: Type,
    label: "Text",
    color: "bg-purple-50 text-purple-700 dark:bg-purple-900/20 dark:text-purple-400"
  },
  youtube: {
    icon: Youtube,
    label: "YouTube",
    color: "bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400"
  },
  hana_table: {
    icon: Database,
    label: "HANA Table",
    color: "bg-orange-50 text-orange-700 dark:bg-orange-900/20 dark:text-orange-400"
  },
  api: {
    icon: Plug,
    label: "API",
    color: "bg-cyan-50 text-cyan-700 dark:bg-cyan-900/20 dark:text-cyan-400"
  },
};

const entityTypeConfig = {
  source: {
    icon: FileText,
    label: "Source",
    color: "bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400"
  },
  notebook: {
    icon: Folder,
    label: "Notebook",
    color: "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/20 dark:text-indigo-400"
  },
  note: {
    icon: StickyNote,
    label: "Note",
    color: "bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
  },
};

function getEntityLink(bookmark: EnrichedBookmark): string {
  switch (bookmark.entity_type) {
    case "source":
      return `/sources/${bookmark.entity_id}`;
    case "notebook":
      return `/workspaces/${bookmark.entity_id}`;
    case "note":
      return `/notes/${bookmark.entity_id}`;
    default:
      return "#";
  }
}

function getEntityIconAndColor(bookmark: EnrichedBookmark) {
  if (bookmark.entity_type === "source" && bookmark.source_type) {
    const config = sourceTypeConfig[bookmark.source_type] || sourceTypeConfig.file;
    return { Icon: config.icon, color: config.color, label: config.label };
  }

  const config = entityTypeConfig[bookmark.entity_type] || entityTypeConfig.source;
  return { Icon: config.icon, color: config.color, label: config.label };
}

function BookmarkCard({ bookmark }: { bookmark: EnrichedBookmark }) {
  const { Icon, color, label } = getEntityIconAndColor(bookmark);

  return (
    <Card className="group hover:shadow-md hover:border-gray-300 dark:hover:border-gray-600 transition-all duration-200 overflow-hidden">
      <CardContent className="p-5">
        {/* Header with Icon and Title */}
        <div className="flex items-start gap-3 mb-3">
          <div className={cn("p-2.5 rounded-lg shrink-0", color)}>
            <Icon className="w-5 h-5" />
          </div>

          <div className="flex-1 min-w-0">
            <Link href={getEntityLink(bookmark)}>
              <h3 className="font-semibold text-base text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors line-clamp-2 mb-1 group/title">
                {bookmark.entity_title}
                <ExternalLink className="inline-block w-3.5 h-3.5 ml-1.5 opacity-0 group-hover/title:opacity-100 transition-opacity" />
              </h3>
            </Link>

            {/* Entity Type & Category */}
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <Badge variant="secondary" className="text-xs font-medium">
                {entityTypeConfig[bookmark.entity_type]?.label || bookmark.entity_type}
              </Badge>
              {bookmark.source_type && (
                <Badge variant="outline" className="text-xs">
                  {sourceTypeConfig[bookmark.source_type]?.label || bookmark.source_type}
                </Badge>
              )}
              {bookmark.category && (
                <Badge variant="outline" className="text-xs flex items-center gap-1">
                  <FolderOpen className="w-3 h-3" />
                  {bookmark.category}
                </Badge>
              )}
            </div>
          </div>

          {/* Bookmark Button */}
          <BookmarkButton
            entityType={bookmark.entity_type}
            entityId={bookmark.entity_id}
            isBookmarked={true}
            size="sm"
          />
        </div>

        {/* Tags */}
        {bookmark.tags && bookmark.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {bookmark.tags.map((tag) => (
              <Badge
                key={tag}
                variant="outline"
                className="text-xs bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/30 dark:text-blue-400 dark:border-blue-800/30"
              >
                <Tag className="w-3 h-3 mr-1" />
                {tag}
              </Badge>
            ))}
          </div>
        )}

        {/* Description */}
        {bookmark.entity_description && (
          <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 mb-3">
            {bookmark.entity_description}
          </p>
        )}

        {/* Custom Note */}
        {bookmark.custom_note && (
          <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/30 rounded-lg p-3 mb-3">
            <p className="text-sm text-amber-900 dark:text-amber-200">
              💡 {bookmark.custom_note}
            </p>
          </div>
        )}

        {/* Metadata Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2 flex-wrap">
            {bookmark.chunk_count !== undefined && bookmark.chunk_count > 0 && (
              <Badge variant="outline" className="text-xs">
                <Sparkles className="w-3 h-3 mr-1" />
                {bookmark.chunk_count}
              </Badge>
            )}
            {bookmark.source_count !== undefined && bookmark.source_count > 0 && (
              <Badge variant="outline" className="text-xs">
                <FileText className="w-3 h-3 mr-1" />
                {bookmark.source_count}
              </Badge>
            )}
            {bookmark.note_count !== undefined && bookmark.note_count > 0 && (
              <Badge variant="outline" className="text-xs">
                <StickyNote className="w-3 h-3 mr-1" />
                {bookmark.note_count}
              </Badge>
            )}
          </div>

          <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
            {formatRelativeTime(bookmark.bookmarked_at)}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function EmptyState({ searchQuery }: { searchQuery?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <div className="w-20 h-20 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-4">
        <Star className="w-10 h-10 text-gray-400" />
      </div>
      <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
        {searchQuery ? "No bookmarks found" : "No bookmarks yet"}
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 text-center max-w-md">
        {searchQuery
          ? `No bookmarks match "${searchQuery}". Try a different search term.`
          : "Click the star icon on sources, notes, or notebooks to save them here for quick access."
        }
      </p>
    </div>
  );
}

function BookmarkGrid({
  bookmarks,
  isLoading,
  searchQuery,
}: {
  bookmarks: EnrichedBookmark[];
  isLoading: boolean;
  searchQuery?: string;
}) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <Card key={i} className="overflow-hidden">
            <CardContent className="p-5">
              <div className="flex items-start gap-3 mb-3">
                <Skeleton className="h-11 w-11 rounded-lg" />
                <div className="flex-1">
                  <Skeleton className="h-5 w-3/4 mb-2" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              </div>
              <Skeleton className="h-4 w-full mb-2" />
              <Skeleton className="h-4 w-2/3" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (bookmarks.length === 0) {
    return <EmptyState searchQuery={searchQuery} />;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
      {bookmarks.map((bookmark) => (
        <BookmarkCard key={bookmark.id} bookmark={bookmark} />
      ))}
    </div>
  );
}

export default function BookmarksPage() {
  const [activeTab, setActiveTab] = useState<BookmarkEntityType | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedTag, setSelectedTag] = useState<string>("all");
  const [manualDialogOpen, setManualDialogOpen] = useState(false);

  const { data, isLoading } = useBookmarks({
    entity_type: activeTab === "all" ? undefined : activeTab,
  });
  const toggleBookmark = useToggleBookmark();

  const allBookmarks = data?.bookmarks ?? [];
  const total = data?.total ?? 0;

  // Extract unique categories and tags
  const { uniqueCategories, uniqueTags } = useMemo(() => {
    const categories = new Set<string>();
    const tags = new Set<string>();

    allBookmarks.forEach((bookmark) => {
      if (bookmark.category) {
        categories.add(bookmark.category);
      }
      if (bookmark.tags) {
        bookmark.tags.forEach((tag) => tags.add(tag));
      }
    });

    return {
      uniqueCategories: Array.from(categories).sort(),
      uniqueTags: Array.from(tags).sort(),
    };
  }, [allBookmarks]);

  // Filter bookmarks based on search query, category, and tag
  const filteredBookmarks = useMemo(() => {
    let filtered = allBookmarks;

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter((bookmark) => {
        const titleMatch = bookmark.entity_title?.toLowerCase().includes(query);
        const descriptionMatch = bookmark.entity_description?.toLowerCase().includes(query);
        const customNoteMatch = bookmark.custom_note?.toLowerCase().includes(query);
        const typeMatch = bookmark.entity_type.toLowerCase().includes(query);
        const sourceTypeMatch = bookmark.source_type?.toLowerCase().includes(query);

        return titleMatch || descriptionMatch || customNoteMatch || typeMatch || sourceTypeMatch;
      });
    }

    // Filter by category
    if (selectedCategory !== "all") {
      filtered = filtered.filter((bookmark) => bookmark.category === selectedCategory);
    }

    // Filter by tag
    if (selectedTag !== "all") {
      filtered = filtered.filter((bookmark) => bookmark.tags?.includes(selectedTag));
    }

    return filtered;
  }, [allBookmarks, searchQuery, selectedCategory, selectedTag]);

  // Count by type for tabs
  const counts = useMemo(() => {
    return {
      all: allBookmarks.length,
      source: allBookmarks.filter(b => b.entity_type === "source").length,
      notebook: allBookmarks.filter(b => b.entity_type === "notebook").length,
      note: allBookmarks.filter(b => b.entity_type === "note").length,
    };
  }, [allBookmarks]);

  const handleCreateManualBookmark = async (data: {
    custom_note?: string;
    reason?: string;
    tags?: string[];
    category?: string;
  }) => {
    // For manual bookmarks, we'll create a text source first
    // This is a placeholder - you might want to create a dedicated endpoint
    toast.info("Manual bookmark creation coming soon!");
    setManualDialogOpen(false);
  };

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="space-y-6 pb-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between animate-fade-in-up">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
            Bookmarks
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Your saved sources, notes, and notebooks
          </p>
        </div>

        {/* Create Manual Bookmark Button */}
        <Button onClick={() => setManualDialogOpen(true)} className="gap-2 transition-all hover:scale-105 hover:shadow-lg">
          <Plus className="w-4 h-4" />
          New Bookmark
        </Button>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            type="text"
            placeholder="Search bookmarks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 h-10"
          />
        </div>

        {/* Category Filter */}
        {uniqueCategories.length > 0 && (
          <div className="flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-gray-500 shrink-0" />
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="h-10 px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            >
              <option value="all">All Categories</option>
              {uniqueCategories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Tag Filter */}
        {uniqueTags.length > 0 && (
          <div className="flex items-center gap-2">
            <Tag className="w-4 h-4 text-gray-500 shrink-0" />
            <select
              value={selectedTag}
              onChange={(e) => setSelectedTag(e.target.value)}
              className="h-10 px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            >
              <option value="all">All Tags</option>
              {uniqueTags.map((tag) => (
                <option key={tag} value={tag}>
                  {tag}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Clear Filters */}
        {(selectedCategory !== "all" || selectedTag !== "all") && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setSelectedCategory("all");
              setSelectedTag("all");
            }}
            className="h-10"
          >
            Clear Filters
          </Button>
        )}
      </div>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as BookmarkEntityType | "all")}
        className="space-y-6"
      >
        <TabsList className="bg-gray-100 dark:bg-gray-800 p-1">
          <TabsTrigger value="all" className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-900">
            All
            {counts.all > 0 && (
              <Badge variant="secondary" className="ml-2 bg-gray-200 dark:bg-gray-700">
                {counts.all}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="source" className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-900">
            Sources
            {counts.source > 0 && (
              <Badge variant="secondary" className="ml-2 bg-gray-200 dark:bg-gray-700">
                {counts.source}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="notebook" className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-900">
            Notebooks
            {counts.notebook > 0 && (
              <Badge variant="secondary" className="ml-2 bg-gray-200 dark:bg-gray-700">
                {counts.notebook}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="note" className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-900">
            Notes
            {counts.note > 0 && (
              <Badge variant="secondary" className="ml-2 bg-gray-200 dark:bg-gray-700">
                {counts.note}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value={activeTab} className="mt-6 focus-visible:outline-none focus-visible:ring-0">
          <BookmarkGrid
            bookmarks={filteredBookmarks}
            isLoading={isLoading}
            searchQuery={searchQuery}
          />
        </TabsContent>
      </Tabs>

      {/* Manual Bookmark Dialog */}
      <BookmarkDialog
        open={manualDialogOpen}
        onOpenChange={setManualDialogOpen}
        onSave={handleCreateManualBookmark}
        isManual={true}
      />
      </div>
    </div>
  );
}
