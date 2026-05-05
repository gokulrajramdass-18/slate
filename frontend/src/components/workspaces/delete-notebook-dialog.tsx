"use client";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useDeleteNotebook } from "@/lib/hooks/use-api";
import { toast } from "sonner";
import type { Notebook } from "@/lib/types";
import { Loader2 } from "lucide-react";

interface DeleteNotebookDialogProps {
  notebook: Notebook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteNotebookDialog({
  notebook,
  open,
  onOpenChange,
}: DeleteNotebookDialogProps) {
  const deleteMutation = useDeleteNotebook();

  const handleDelete = async () => {
    try {
      await deleteMutation.mutateAsync(notebook.id);
      toast.success(`"${notebook.name}" has been deleted`);
      onOpenChange(false);
    } catch (error) {
      toast.error("Failed to delete workspace");
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete Workspace?</AlertDialogTitle>
          <AlertDialogDescription>
            Are you sure you want to delete <strong>"{notebook.name}"</strong>? This action cannot
            be undone. All sources, notes, and chat sessions associated with this workspace will be
            removed.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={deleteMutation.isPending}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleDelete}
            disabled={deleteMutation.isPending}
            className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
          >
            {deleteMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
