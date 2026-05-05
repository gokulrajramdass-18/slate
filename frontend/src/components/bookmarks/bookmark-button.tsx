"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToggleBookmark } from "@/lib/hooks/use-api";
import type { BookmarkEntityType } from "@/lib/types";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { BookmarkDialog } from "./bookmark-dialog";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface BookmarkButtonProps {
  entityType: BookmarkEntityType;
  entityId: string;
  entityTitle?: string;
  isBookmarked?: boolean;
  variant?: "ghost" | "outline" | "default";
  size?: "default" | "sm" | "icon";
  className?: string;
  showDialog?: boolean; // Whether to show dialog on bookmark
}

export function BookmarkButton({
  entityType,
  entityId,
  entityTitle,
  isBookmarked = false,
  variant = "ghost",
  size = "icon",
  className,
  showDialog = true, // Default to showing dialog
}: BookmarkButtonProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const toggleBookmark = useToggleBookmark();

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (isBookmarked) {
      // If already bookmarked, remove it without showing dialog
      toggleBookmark.mutate(
        {
          entity_type: entityType,
          entity_id: entityId,
        },
        {
          onSuccess: (data) => {
            toast.success(data.message);
          },
          onError: () => {
            toast.error("Failed to toggle bookmark");
          },
        }
      );
    } else {
      // If not bookmarked, show dialog if enabled
      if (showDialog) {
        setDialogOpen(true);
      } else {
        // Quick bookmark without dialog
        toggleBookmark.mutate(
          {
            entity_type: entityType,
            entity_id: entityId,
          },
          {
            onSuccess: (data) => {
              toast.success(data.message);
            },
            onError: () => {
              toast.error("Failed to toggle bookmark");
            },
          }
        );
      }
    }
  };

  const handleSaveWithDetails = (data: {
    custom_note?: string;
    reason?: string;
    tags?: string[];
    category?: string;
  }) => {
    toggleBookmark.mutate(
      {
        entity_type: entityType,
        entity_id: entityId,
        ...data,
      },
      {
        onSuccess: (response) => {
          toast.success(response.message);
        },
        onError: () => {
          toast.error("Failed to create bookmark");
        },
      }
    );
  };

  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant={variant}
            size={size}
            onClick={handleToggle}
            disabled={toggleBookmark.isPending}
            className={cn("h-8 w-8", className)}
          >
            <Star
              className={cn(
                "h-4 w-4 transition-colors",
                isBookmarked
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-gray-400 hover:text-yellow-400"
              )}
            />
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {isBookmarked ? "Remove bookmark" : "Bookmark"}
        </TooltipContent>
      </Tooltip>

      <BookmarkDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSave={handleSaveWithDetails}
        title={entityTitle}
      />
    </>
  );
}
