"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Loader2, Plus, X } from "lucide-react";
import { useCreateMemory, useUpdateMemory } from "@/lib/hooks/use-api";
import type { Memory, MemoryCreate, MemoryType, MemoryPriority } from "@/lib/types";

interface MemoryEditorProps {
  memory?: Memory;
  open: boolean;
  onClose: () => void;
}

const memoryTypes: { value: MemoryType; label: string; description: string }[] = [
  { value: "episodic", label: "Episodic", description: "Specific events and experiences" },
  { value: "semantic", label: "Semantic", description: "Facts and general knowledge" },
  { value: "procedural", label: "Procedural", description: "How to do things (procedures)" },
  { value: "working", label: "Working", description: "Temporary, currently relevant info" },
];

const priorities: { value: MemoryPriority; label: string }[] = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

export function MemoryEditor({ memory, open, onClose }: MemoryEditorProps) {
  const isEditing = !!memory;
  const createMutation = useCreateMemory();
  const updateMutation = useUpdateMemory();

  const [formData, setFormData] = useState<{
    memory_type: MemoryType;
    content: string;
    summary: string;
    tags: string[];
    priority: MemoryPriority;
    expires_at: string;
  }>({
    memory_type: "semantic",
    content: "",
    summary: "",
    tags: [],
    priority: "medium",
    expires_at: "",
  });
  const [tagInput, setTagInput] = useState("");

  useEffect(() => {
    if (memory) {
      setFormData({
        memory_type: memory.memory_type,
        content: memory.content,
        summary: memory.summary || "",
        tags: memory.tags || [],
        priority: memory.priority,
        expires_at: memory.expires_at
          ? new Date(memory.expires_at).toISOString().split("T")[0]
          : "",
      });
    } else {
      setFormData({
        memory_type: "semantic",
        content: "",
        summary: "",
        tags: [],
        priority: "medium",
        expires_at: "",
      });
    }
  }, [memory, open]);

  const addTag = () => {
    const tag = tagInput.trim();
    if (tag && !formData.tags.includes(tag)) {
      setFormData((prev) => ({ ...prev, tags: [...prev.tags, tag] }));
      setTagInput("");
    }
  };

  const removeTag = (tag: string) => {
    setFormData((prev) => ({
      ...prev,
      tags: prev.tags.filter((t) => t !== tag),
    }));
  };

  const handleSubmit = async () => {
    const payload: MemoryCreate = {
      memory_type: formData.memory_type,
      content: formData.content,
      summary: formData.summary || undefined,
      tags: formData.tags.length > 0 ? formData.tags : undefined,
      priority: formData.priority,
      expires_at: formData.expires_at || undefined,
    };

    if (isEditing && memory) {
      await updateMutation.mutateAsync({ id: memory.id, data: payload });
    } else {
      await createMutation.mutateAsync(payload);
    }

    onClose();
  };

  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit Memory" : "Create Memory"}</DialogTitle>
          <DialogDescription>
            {isEditing
              ? "Update this memory entry."
              : "Add a new memory to the system."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Type */}
          <div className="space-y-1.5">
            <Label>Type</Label>
            <Select
              value={formData.memory_type}
              onValueChange={(v) =>
                setFormData((prev) => ({ ...prev, memory_type: v as MemoryType }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                {memoryTypes.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    <div>
                      <span className="font-medium">{t.label}</span>
                      <span className="text-xs text-gray-500 ml-2">{t.description}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Summary */}
          <div className="space-y-1.5">
            <Label>Summary (optional)</Label>
            <Input
              value={formData.summary}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, summary: e.target.value }))
              }
              placeholder="Brief summary of this memory"
            />
          </div>

          {/* Content */}
          <div className="space-y-1.5">
            <Label>Content</Label>
            <Textarea
              value={formData.content}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, content: e.target.value }))
              }
              placeholder="The memory content..."
              rows={4}
            />
          </div>

          {/* Priority */}
          <div className="space-y-1.5">
            <Label>Priority</Label>
            <Select
              value={formData.priority}
              onValueChange={(v) =>
                setFormData((prev) => ({ ...prev, priority: v as MemoryPriority }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800">
                {priorities.map((p) => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Tags */}
          <div className="space-y-1.5">
            <Label>Tags</Label>
            <div className="flex gap-2">
              <Input
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                placeholder="Add a tag..."
                className="flex-1"
              />
              <Button type="button" variant="outline" size="sm" onClick={addTag}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {formData.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1.5">
                {formData.tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="ml-1 hover:text-red-500"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {/* Expiration */}
          <div className="space-y-1.5">
            <Label>Expires (optional)</Label>
            <Input
              type="date"
              value={formData.expires_at}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, expires_at: e.target.value }))
              }
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={isSubmitting || !formData.content.trim()}
          >
            {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            {isEditing ? "Update" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
