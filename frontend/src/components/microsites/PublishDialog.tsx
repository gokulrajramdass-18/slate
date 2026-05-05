"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { AlertCircle } from "lucide-react";

interface PublishDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPublish: (message?: string) => Promise<void>;
  hasUnpublishedChanges: boolean;
}

export function PublishDialog({
  open,
  onOpenChange,
  onPublish,
  hasUnpublishedChanges,
}: PublishDialogProps) {
  const [versionMessage, setVersionMessage] = useState("");
  const [isPublishing, setIsPublishing] = useState(false);

  const handlePublish = async () => {
    setIsPublishing(true);
    try {
      await onPublish(versionMessage || undefined);
      setVersionMessage("");
      onOpenChange(false);
    } catch (error) {
      console.error("Publish failed:", error);
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Publish Microsite</DialogTitle>
          <DialogDescription>
            This will create a new version and make your microsite publicly
            accessible.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {!hasUnpublishedChanges && (
            <div className="flex items-start gap-3 rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800 dark:border-yellow-800 dark:bg-yellow-950 dark:text-yellow-200">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <p>
                No changes since last publish. Publishing will create a new
                version with the same content.
              </p>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="version-message">Version Message (Optional)</Label>
            <Textarea
              id="version-message"
              placeholder="Describe what changed in this version..."
              value={versionMessage}
              onChange={(e) => setVersionMessage(e.target.value)}
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPublishing}
          >
            Cancel
          </Button>
          <Button onClick={handlePublish} disabled={isPublishing}>
            {isPublishing ? "Publishing..." : "Publish"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
