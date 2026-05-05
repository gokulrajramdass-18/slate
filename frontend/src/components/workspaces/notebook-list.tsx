"use client";

import { Skeleton } from "@/components/ui/skeleton";
import { NotebookCard } from "./notebook-card";
import type { Notebook } from "@/lib/types";

interface NotebookListProps {
  notebooks: Notebook[];
  isLoading: boolean;
  onEdit?: (notebook: Notebook) => void;
  onDuplicate?: (notebook: Notebook) => void;
}

export function NotebookList({ notebooks, isLoading, onEdit, onDuplicate }: NotebookListProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <NotebookSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (notebooks.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {notebooks.map((notebook) => (
        <NotebookCard
          key={notebook.id}
          notebook={notebook}
          onEdit={onEdit}
          onDuplicate={onDuplicate}
          sourceCount={notebook.source_count || 0}
        />
      ))}
    </div>
  );
}

function NotebookSkeleton() {
  return (
    <div className="border rounded-lg p-6 space-y-4">
      <div className="flex items-start justify-between">
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-8 w-8 rounded" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <div className="flex items-center justify-between pt-4 border-t">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  );
}
