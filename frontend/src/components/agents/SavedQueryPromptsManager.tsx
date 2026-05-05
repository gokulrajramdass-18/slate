"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userQueryPromptsApi, type UserQueryPrompt } from "@/lib/api/user-query-prompts";
import { queryKeys } from "@/lib/query-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Loader2,
  Library,
  Pencil,
  Trash2,
  Star,
  Plus,
  Save,
  X,
} from "lucide-react";
import { toast } from "sonner";

export function SavedQueryPromptsManager() {
  const queryClient = useQueryClient();
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<UserQueryPrompt | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch all saved prompts
  const { data: prompts = [], isLoading } = useQuery({
    queryKey: queryKeys.userQueryPrompts,
    queryFn: () => userQueryPromptsApi.list(),
  });

  // Mutations
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      userQueryPromptsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.userQueryPrompts });
      setShowEditDialog(false);
      setEditingPrompt(null);
      toast.success("Prompt updated");
    },
    onError: () => {
      toast.error("Failed to update prompt");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => userQueryPromptsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.userQueryPrompts });
      toast.success("Prompt deleted");
    },
    onError: () => {
      toast.error("Failed to delete prompt");
    },
  });

  const toggleFavoriteMutation = useMutation({
    mutationFn: (id: string) => userQueryPromptsApi.toggleFavorite(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.userQueryPrompts });
    },
  });

  // Filter prompts
  const filteredPrompts = prompts.filter((prompt) => {
    const matchesSearch =
      !searchQuery ||
      prompt.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prompt.query_text.toLowerCase().includes(searchQuery.toLowerCase()) ||
      prompt.description?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory =
      filterCategory === "all" ||
      (filterCategory === "favorites" && prompt.is_favorite) ||
      prompt.category === filterCategory;

    return matchesSearch && matchesCategory;
  });

  // Get unique categories
  const categories = Array.from(
    new Set(prompts.map((p) => p.category).filter(Boolean))
  );

  const handleEdit = (prompt: UserQueryPrompt) => {
    setEditingPrompt(prompt);
    setShowEditDialog(true);
  };

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Delete prompt "${name}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleSaveEdit = () => {
    if (!editingPrompt) return;

    updateMutation.mutate({
      id: editingPrompt.id,
      data: {
        name: editingPrompt.name,
        query_text: editingPrompt.query_text,
        description: editingPrompt.description,
        category: editingPrompt.category,
        tags: editingPrompt.tags,
      },
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header and Filters */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 space-y-2">
          <Input
            placeholder="Search prompts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-sm"
          />
        </div>
        <Select value={filterCategory} onValueChange={setFilterCategory}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Filter by category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Prompts</SelectItem>
            <SelectItem value="favorites">Favorites</SelectItem>
            {categories.map((cat) => (
              <SelectItem key={cat} value={cat!}>
                {cat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Prompts List */}
      {filteredPrompts.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center space-y-4">
            <Library className="w-12 h-12 mx-auto text-muted-foreground" />
            <div className="space-y-1">
              <p className="font-medium text-lg">
                {searchQuery || filterCategory !== "all"
                  ? "No prompts found"
                  : "No saved prompts yet"}
              </p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                {searchQuery || filterCategory !== "all"
                  ? "Try adjusting your search or filter"
                  : "Save query prompts from the Execute tab to reuse them later"}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {filteredPrompts.map((prompt) => (
            <Card key={prompt.id} className="hover:bg-accent/50 transition-colors">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <CardTitle className="text-base truncate">
                        {prompt.name}
                      </CardTitle>
                      {prompt.category && (
                        <Badge variant="outline" className="text-xs">
                          {prompt.category}
                        </Badge>
                      )}
                      {prompt.is_favorite && (
                        <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                      )}
                    </div>
                    {prompt.description && (
                      <p className="text-sm text-muted-foreground">
                        {prompt.description}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => toggleFavoriteMutation.mutate(prompt.id)}
                      title={prompt.is_favorite ? "Remove from favorites" : "Add to favorites"}
                    >
                      <Star
                        className={`h-4 w-4 ${
                          prompt.is_favorite ? "text-yellow-500 fill-yellow-500" : ""
                        }`}
                      />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleEdit(prompt)}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-destructive"
                      onClick={() => handleDelete(prompt.id, prompt.name)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  <div className="p-3 bg-muted rounded-md">
                    <p className="text-sm font-mono whitespace-pre-wrap line-clamp-3">
                      {prompt.query_text}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    {prompt.use_count > 0 && (
                      <span>
                        Used {prompt.use_count} {prompt.use_count === 1 ? "time" : "times"}
                      </span>
                    )}
                    {prompt.last_used && (
                      <span>Last used: {new Date(prompt.last_used).toLocaleDateString()}</span>
                    )}
                    <span>Created: {new Date(prompt.created).toLocaleDateString()}</span>
                    {prompt.tags && prompt.tags.length > 0 && (
                      <div className="flex gap-1">
                        {prompt.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Info Card */}
      <Card className="border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30">
        <CardContent className="py-4 text-sm text-gray-600 dark:text-gray-400 space-y-2">
          <p className="font-medium text-gray-700 dark:text-gray-300">
            About Saved Query Prompts
          </p>
          <p>
            These are your personal saved queries that you can quickly load in the Execute tab.
            Each prompt remembers the query text and which system prompt template was selected.
          </p>
          <p>
            To create new saved prompts, go to the Execute tab and click the bookmark button (🔖+)
            after entering a query.
          </p>
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog open={showEditDialog} onOpenChange={setShowEditDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Saved Prompt</DialogTitle>
            <DialogDescription>
              Update the details of your saved query prompt
            </DialogDescription>
          </DialogHeader>

          {editingPrompt && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="edit-name">Name *</Label>
                <Input
                  id="edit-name"
                  value={editingPrompt.name}
                  onChange={(e) =>
                    setEditingPrompt({ ...editingPrompt, name: e.target.value })
                  }
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-query">Query Text *</Label>
                <Textarea
                  id="edit-query"
                  value={editingPrompt.query_text}
                  onChange={(e) =>
                    setEditingPrompt({ ...editingPrompt, query_text: e.target.value })
                  }
                  rows={4}
                  className="font-mono text-sm"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-description">Description</Label>
                <Textarea
                  id="edit-description"
                  value={editingPrompt.description || ""}
                  onChange={(e) =>
                    setEditingPrompt({ ...editingPrompt, description: e.target.value })
                  }
                  rows={2}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-category">Category</Label>
                <Input
                  id="edit-category"
                  value={editingPrompt.category || ""}
                  onChange={(e) =>
                    setEditingPrompt({ ...editingPrompt, category: e.target.value })
                  }
                />
              </div>

              <div className="space-y-1">
                <Label className="text-sm text-muted-foreground">System Prompt</Label>
                <p className="text-sm bg-muted p-2 rounded">
                  {editingPrompt.prompt_role || "Not specified"}
                </p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowEditDialog(false);
                setEditingPrompt(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={
                !editingPrompt?.name.trim() ||
                !editingPrompt?.query_text.trim() ||
                updateMutation.isPending
              }
            >
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4 mr-2" />
                  Save Changes
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
