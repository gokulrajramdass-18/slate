"use client";

import { useState, useRef, useEffect } from "react";
import { Pencil, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

interface ChatTitleEditorProps {
  title: string;
  workspaceName?: string;
  onSave: (newTitle: string) => Promise<void>;
  className?: string;
}

export function ChatTitleEditor({
  title,
  workspaceName,
  onSave,
  className,
}: ChatTitleEditorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedTitle, setEditedTitle] = useState(title);
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Update local state when prop changes
  useEffect(() => {
    setEditedTitle(title);
  }, [title]);

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  const handleSave = async () => {
    if (!editedTitle.trim()) {
      // Reset to original title if empty
      setEditedTitle(title);
      setIsEditing(false);
      return;
    }

    if (editedTitle === title) {
      // No changes, just exit edit mode
      setIsEditing(false);
      return;
    }

    setIsSaving(true);
    try {
      await onSave(editedTitle);
      setIsEditing(false);
    } catch (error) {
      // Reset to original title on error
      setEditedTitle(title);
      console.error("Failed to save title:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedTitle(title);
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  };

  return (
    <div className={cn("flex items-center gap-2 group", className)}>
      {isEditing ? (
        <>
          <div className="flex-1 flex items-center gap-2">
            <Input
              ref={inputRef}
              value={editedTitle}
              onChange={(e) => setEditedTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isSaving}
              className="h-9 text-lg font-bold"
              placeholder="Enter chat title..."
            />
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="ghost"
                onClick={handleSave}
                disabled={isSaving}
                className="h-8 w-8 p-0"
              >
                <Check className="w-4 h-4 text-green-600" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={handleCancel}
                disabled={isSaving}
                className="h-8 w-8 p-0"
              >
                <X className="w-4 h-4 text-red-600" />
              </Button>
            </div>
          </div>
        </>
      ) : (
        <>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setIsEditing(true)}
                className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Edit chat title"
              >
                <Pencil className="w-4 h-4" />
              </Button>
            </div>
            {workspaceName && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                from workspace: <span className="font-medium">{workspaceName}</span>
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
