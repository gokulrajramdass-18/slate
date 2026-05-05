"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Globe, GlobeLock, Ban, MoreVertical } from "lucide-react";
import type { MicrositeStatus } from "@/lib/types";
import { PublishDialog } from "./PublishDialog";
import { StatusBadge } from "./StatusBadge";

interface PublishControlsProps {
  micrositeId: string;
  status: MicrositeStatus;
  hasUnpublishedChanges: boolean;
  onPublish: (message?: string) => Promise<void>;
  onUnpublish: () => Promise<void>;
  onBlock?: (reason: string) => Promise<void>;
  isOwner: boolean;
  isAdmin?: boolean;
}

export function PublishControls({
  micrositeId,
  status,
  hasUnpublishedChanges,
  onPublish,
  onUnpublish,
  onBlock,
  isOwner,
  isAdmin = false,
}: PublishControlsProps) {
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);

  return (
    <div className="flex items-center gap-3">
      <StatusBadge status={status} />

      {hasUnpublishedChanges && status === "published" && (
        <span className="text-xs text-muted-foreground">
          (Unpublished changes)
        </span>
      )}

      {isOwner && (
        <>
          {status === "draft" && (
            <Button onClick={() => setPublishDialogOpen(true)}>
              <Globe className="h-4 w-4 mr-2" />
              Publish
            </Button>
          )}

          {status === "published" && (
            <>
              <Button
                variant="outline"
                onClick={() => setPublishDialogOpen(true)}
              >
                Update Version
              </Button>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="More actions"
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={() => onUnpublish()}>
                    <GlobeLock className="h-4 w-4 mr-2" />
                    Unpublish
                  </DropdownMenuItem>
                  {isAdmin && onBlock && (
                    <DropdownMenuItem
                      onClick={() => onBlock("Manual block")}
                      className="text-destructive"
                    >
                      <Ban className="h-4 w-4 mr-2" />
                      Block
                    </DropdownMenuItem>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
            </>
          )}
        </>
      )}

      {status === "blocked" && isAdmin && (
        <Button variant="outline" onClick={() => onUnpublish()}>
          Unblock
        </Button>
      )}

      <PublishDialog
        open={publishDialogOpen}
        onOpenChange={setPublishDialogOpen}
        onPublish={onPublish}
        hasUnpublishedChanges={hasUnpublishedChanges}
      />
    </div>
  );
}
