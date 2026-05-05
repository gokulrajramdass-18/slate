"use client";

import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Brain,
  Search,
  Plus,
  Loader2,
  Trash2,
  BookOpen,
  Clock,
  Cog,
  Zap,
  BarChart3,
  RefreshCw,
} from "lucide-react";
import { MemoryCard } from "./MemoryCard";
import { MemoryEditor } from "./MemoryEditor";
import {
  useMemories,
  useDeleteMemory,
  useMemorySearch,
  useMemoryStats,
  useMemoryTags,
  useClearExpiredMemories,
} from "@/lib/hooks/use-api";
import type { Memory, MemoryType } from "@/lib/types";

export function MemoryBrowser() {
  const [selectedType, setSelectedType] = useState<MemoryType | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingMemory, setEditingMemory] = useState<Memory | undefined>();

  const memoryParams = useMemo(
    () =>
      selectedType !== "all" ? { memory_type: selectedType as MemoryType } : undefined,
    [selectedType]
  );

  const { data: memories, isLoading } = useMemories(memoryParams);
  const { data: stats } = useMemoryStats();
  const { data: allTags } = useMemoryTags();
  const deleteMutation = useDeleteMemory();
  const clearExpiredMutation = useClearExpiredMemories();
  const { data: searchResults, isLoading: searchLoading } = useMemorySearch(
    { query: searchQuery, limit: 20 },
    isSearching && searchQuery.length > 0
  );

  const handleSearch = () => {
    if (searchQuery.trim()) {
      setIsSearching(true);
    }
  };

  const handleEdit = (memory: Memory) => {
    setEditingMemory(memory);
    setEditorOpen(true);
  };

  const handleCreate = () => {
    setEditingMemory(undefined);
    setEditorOpen(true);
  };

  const handleDelete = async (memoryId: string) => {
    await deleteMutation.mutateAsync(memoryId);
  };

  const handleCloseEditor = () => {
    setEditorOpen(false);
    setEditingMemory(undefined);
  };

  const typeFilters: { value: MemoryType | "all"; label: string; icon: React.ElementType }[] = [
    { value: "all", label: "All", icon: Brain },
    { value: "episodic", label: "Episodic", icon: Clock },
    { value: "semantic", label: "Semantic", icon: BookOpen },
    { value: "procedural", label: "Procedural", icon: Cog },
    { value: "working", label: "Working", icon: Zap },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-purple-100 dark:bg-purple-900">
            <Brain className="h-5 w-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Memory System</h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Browse and manage agent memories
            </p>
          </div>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="h-4 w-4 mr-2" />
          New Memory
        </Button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Card>
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold">{stats.total}</p>
              <p className="text-xs text-gray-500">Total</p>
            </CardContent>
          </Card>
          {(Object.entries(stats.by_type) as [MemoryType, number][]).map(([type, count]) => {
            const filterItem = typeFilters.find((f) => f.value === type);
            const Icon = filterItem?.icon || Brain;
            return (
              <Card key={type}>
                <CardContent className="p-3 text-center">
                  <div className="flex items-center justify-center gap-1">
                    <Icon className="h-3.5 w-3.5 text-gray-400" />
                    <p className="text-2xl font-bold">{count}</p>
                  </div>
                  <p className="text-xs text-gray-500 capitalize">{type}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Tabs defaultValue="browse">
        <TabsList>
          <TabsTrigger value="browse">Browse</TabsTrigger>
          <TabsTrigger value="search">
            <Search className="h-3.5 w-3.5 mr-1" />
            Search
          </TabsTrigger>
        </TabsList>

        {/* Browse Tab */}
        <TabsContent value="browse" className="space-y-4">
          <div className="flex items-center gap-3">
            {/* Type filter */}
            <Select
              value={selectedType}
              onValueChange={(v) => setSelectedType(v as MemoryType | "all")}
            >
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {typeFilters.map((f) => (
                  <SelectItem key={f.value} value={f.value}>
                    <div className="flex items-center gap-2">
                      <f.icon className="h-3.5 w-3.5" />
                      {f.label}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Clear expired button */}
            {stats && stats.expired > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => clearExpiredMutation.mutate()}
                disabled={clearExpiredMutation.isPending}
              >
                {clearExpiredMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5 mr-1" />
                )}
                Clear {stats.expired} expired
              </Button>
            )}
          </div>

          {/* Tags */}
          {allTags && allTags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {allTags.slice(0, 20).map((tag) => (
                <Badge key={tag} variant="outline" className="text-xs cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800">
                  {tag}
                </Badge>
              ))}
            </div>
          )}

          {/* Memory List */}
          {isLoading ? (
            <div className="flex items-center justify-center p-8">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : memories && memories.length > 0 ? (
            <ScrollArea className="h-[600px]">
              <div className="space-y-3 pr-4">
                {memories.map((mem) => (
                  <MemoryCard
                    key={mem.id}
                    memory={mem}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </ScrollArea>
          ) : (
            <Card>
              <CardContent className="py-8 text-center text-sm text-gray-500">
                <Brain className="h-8 w-8 mx-auto mb-2 text-gray-300 dark:text-gray-700" />
                No memories found.{" "}
                <button
                  onClick={handleCreate}
                  className="text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Create one
                </button>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Search Tab */}
        <TabsContent value="search" className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Search memories semantically..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setIsSearching(false);
              }}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1"
            />
            <Button onClick={handleSearch} disabled={!searchQuery.trim()}>
              <Search className="h-4 w-4 mr-2" />
              Search
            </Button>
          </div>

          {searchLoading ? (
            <div className="flex items-center justify-center p-8">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : searchResults && searchResults.length > 0 ? (
            <ScrollArea className="h-[600px]">
              <div className="space-y-3 pr-4">
                {searchResults.map((result) => (
                  <MemoryCard
                    key={result.memory.id}
                    memory={result.memory}
                    relevanceScore={result.relevance_score}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </ScrollArea>
          ) : isSearching ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-gray-500">
                No matching memories found
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>
      </Tabs>

      {/* Editor Dialog */}
      <MemoryEditor
        memory={editingMemory}
        open={editorOpen}
        onClose={handleCloseEditor}
      />
    </div>
  );
}
