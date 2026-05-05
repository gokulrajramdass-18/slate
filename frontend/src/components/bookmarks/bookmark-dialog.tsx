"use client";

import { useState } from "react";
import { X, Plus, Tag, FolderOpen } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

interface BookmarkDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (data: {
    custom_note?: string;
    reason?: string;
    tags?: string[];
    category?: string;
  }) => void;
  title?: string;
  isManual?: boolean;
}

const PRESET_CATEGORIES = [
  "Research",
  "Reference",
  "Tutorial",
  "Documentation",
  "Article",
  "Tool",
  "Inspiration",
  "Archive",
  "Important",
  "Review Later",
];

const SUGGESTED_TAGS = [
  "urgent",
  "important",
  "follow-up",
  "idea",
  "bug",
  "feature",
  "design",
  "code",
  "data",
  "analytics",
];

export function BookmarkDialog({
  open,
  onOpenChange,
  onSave,
  title,
  isManual = false,
}: BookmarkDialogProps) {
  const [customNote, setCustomNote] = useState("");
  const [reason, setReason] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");
  const [category, setCategory] = useState<string>();

  const handleSave = () => {
    onSave({
      custom_note: customNote || undefined,
      reason: reason || undefined,
      tags: tags.length > 0 ? tags : undefined,
      category: category || undefined,
    });

    // Reset form
    setCustomNote("");
    setReason("");
    setTags([]);
    setTagInput("");
    setCategory(undefined);
    onOpenChange(false);
  };

  const addTag = (tag: string) => {
    const trimmedTag = tag.trim().toLowerCase();
    if (trimmedTag && !tags.includes(trimmedTag)) {
      setTags([...tags, trimmedTag]);
      setTagInput("");
    }
  };

  const removeTag = (tagToRemove: string) => {
    setTags(tags.filter((tag) => tag !== tagToRemove));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addTag(tagInput);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Tag className="w-5 h-5 text-amber-600" />
            {isManual ? "Create Manual Bookmark" : "Add Bookmark Details"}
          </DialogTitle>
          <DialogDescription>
            {title ? (
              <span className="block mt-1 font-medium text-gray-700 dark:text-gray-300">
                {title}
              </span>
            ) : (
              "Add tags, category, and notes to organize your bookmark"
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-4">
          {/* Category Selection */}
          <div className="space-y-2">
            <Label htmlFor="category" className="flex items-center gap-2">
              <FolderOpen className="w-4 h-4" />
              Category
            </Label>

            <div className="space-y-2">
              {/* Category Input - for manual entry or display selected */}
              <Input
                id="category"
                placeholder="Type custom or select preset..."
                value={category || ""}
                onChange={(e) => setCategory(e.target.value)}
              />

              {/* Preset Category Buttons */}
              <div className="flex flex-wrap gap-1.5">
                <span className="text-xs text-gray-500 w-full mb-1">Presets:</span>
                {PRESET_CATEGORIES.map((cat) => (
                  <Button
                    key={cat}
                    type="button"
                    variant={category?.toLowerCase() === cat.toLowerCase() ? "default" : "ghost"}
                    size="sm"
                    className="h-7 px-2.5 text-xs"
                    onClick={() => setCategory(cat)}
                  >
                    {cat}
                  </Button>
                ))}
              </div>
            </div>
          </div>

          {/* Tags Input */}
          <div className="space-y-2">
            <Label htmlFor="tags" className="flex items-center gap-2">
              <Tag className="w-4 h-4" />
              Tags
            </Label>

            {/* Selected Tags */}
            {tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {tags.map((tag) => (
                  <Badge
                    key={tag}
                    variant="secondary"
                    className="pl-2 pr-1 py-1 text-xs"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-1 hover:bg-gray-300 dark:hover:bg-gray-600 rounded-full p-0.5"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}

            {/* Tag Input */}
            <div className="flex gap-2">
              <Input
                id="tags"
                placeholder="Type and press Enter..."
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => addTag(tagInput)}
                disabled={!tagInput.trim()}
              >
                <Plus className="w-4 h-4" />
              </Button>
            </div>

            {/* Suggested Tags */}
            <div className="flex flex-wrap gap-1.5 mt-2">
              <span className="text-xs text-gray-500 w-full mb-1">Suggested:</span>
              {SUGGESTED_TAGS.filter((tag) => !tags.includes(tag)).map((tag) => (
                <Button
                  key={tag}
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs"
                  onClick={() => addTag(tag)}
                >
                  {tag}
                </Button>
              ))}
            </div>
          </div>

          {/* Custom Note */}
          <div className="space-y-2">
            <Label htmlFor="note">Note</Label>
            <Textarea
              id="note"
              placeholder="Add a note about why you're bookmarking this..."
              value={customNote}
              onChange={(e) => setCustomNote(e.target.value)}
              rows={3}
              className="resize-none"
            />
          </div>

          {/* Reason (Optional) */}
          <div className="space-y-2">
            <Label htmlFor="reason">
              Reason <span className="text-xs text-gray-500">(optional)</span>
            </Label>
            <Input
              id="reason"
              placeholder="e.g., For project X, Reference material, etc."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave}>
            Save Bookmark
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
