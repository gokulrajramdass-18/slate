/**
 * Example Component: Notebook Manager
 *
 * This component demonstrates how to use the API client layer:
 * - Fetching data with useNotebooks hook
 * - Creating notebooks with useCreateNotebook mutation
 * - Deleting notebooks with useDeleteNotebook mutation
 * - Accessing auth state with useAuthStore
 * - Loading and error states
 * - Optimistic UI updates
 */

"use client";

import { useState } from "react";
import {
  useNotebooks,
  useCreateNotebook,
  useDeleteNotebook,
} from "@/lib/hooks";
import { useAuthStore } from "@/lib/stores";
import type { Notebook } from "@/lib/types";

export function NotebookManager() {
  const [newNotebookName, setNewNotebookName] = useState("");

  // Zustand store for auth
  const { user } = useAuthStore();

  // React Query hooks for data fetching
  const {
    data: notebooks,
    isLoading,
    error,
    refetch,
  } = useNotebooks({ archived: false });

  // React Query mutation hooks
  const createMutation = useCreateNotebook();
  const deleteMutation = useDeleteNotebook();

  // Create notebook handler
  const handleCreate = async () => {
    if (!newNotebookName.trim()) return;

    try {
      await createMutation.mutateAsync({
        name: newNotebookName,
        description: "Created via example component",
        goal: "",
      });
      setNewNotebookName(""); // Clear input on success
    } catch (error) {
      console.error("Failed to create notebook:", error);
    }
  };

  // Delete notebook handler
  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this notebook?")) return;

    try {
      await deleteMutation.mutateAsync(id);
    } catch (error) {
      console.error("Failed to delete notebook:", error);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
        <span className="ml-2">Loading notebooks...</span>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-md">
        <h3 className="text-red-800 font-semibold">Error loading notebooks</h3>
        <p className="text-red-600">{error.message}</p>
        <button
          onClick={() => refetch()}
          className="mt-2 px-4 py-2 bg-destructive text-destructive-foreground rounded hover:bg-destructive/90"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">My Notebooks</h1>
          <p className="text-gray-600">Welcome, {user?.username}!</p>
        </div>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-gray-100 rounded hover:bg-gray-200"
        >
          Refresh
        </button>
      </div>

      {/* Create Notebook Form */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newNotebookName}
          onChange={(e) => setNewNotebookName(e.target.value)}
          placeholder="Enter notebook name..."
          className="flex-1 px-4 py-2 border rounded-md"
          disabled={createMutation.isPending}
          onKeyPress={(e) => e.key === "Enter" && handleCreate()}
        />
        <button
          onClick={handleCreate}
          disabled={createMutation.isPending || !newNotebookName.trim()}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {createMutation.isPending ? "Creating..." : "Create Notebook"}
        </button>
      </div>

      {/* Mutation Errors */}
      {createMutation.isError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700">
          Failed to create notebook: {(createMutation.error as Error).message}
        </div>
      )}
      {deleteMutation.isError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700">
          Failed to delete notebook: {(deleteMutation.error as Error).message}
        </div>
      )}

      {/* Empty State */}
      {(!notebooks || notebooks.length === 0) && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <p className="text-gray-500 text-lg">No notebooks yet</p>
          <p className="text-gray-400">Create your first notebook to get started</p>
        </div>
      )}

      {/* Notebooks List */}
      {notebooks && notebooks.length > 0 && (
        <div className="space-y-3">
          {notebooks.map((notebook: Notebook) => (
            <div
              key={notebook.id}
              className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
            >
              <div className="flex-1">
                <h3 className="font-semibold text-lg">{notebook.name}</h3>
                {notebook.description && (
                  <p className="text-gray-600 text-sm">{notebook.description}</p>
                )}
                <p className="text-gray-400 text-xs mt-1">
                  Created: {new Date(notebook.created).toLocaleDateString()}
                </p>
              </div>
              <button
                onClick={() => handleDelete(notebook.id)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 bg-destructive text-destructive-foreground rounded hover:bg-destructive/90 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Stats */}
      <div className="text-sm text-gray-500 text-center">
        Total notebooks: {notebooks?.length || 0}
      </div>
    </div>
  );
}

/**
 * Alternative Example: Using the API client directly (without hooks)
 *
 * This is useful for:
 * - Server-side operations
 * - One-off API calls
 * - Non-React contexts
 */

import { workspacesApi } from "@/lib/api";

export async function fetchNotebooksDirectly() {
  try {
    const notebooks = await workspacesApi.list({ archived: false });
    return notebooks;
  } catch (error) {
    console.error("Failed to fetch notebooks:", error);
    throw error;
  }
}

/**
 * Advanced Example: Optimistic Updates
 *
 * This demonstrates how to update the UI immediately before the API responds,
 * then rollback if the API call fails.
 */

import { useQueryClient, useMutation } from "@tanstack/react-query";
import { queryKeys } from "@/lib/query-client";
import { useUpdateNotebook } from "@/lib/hooks";

export function useOptimisticNotebookUpdate() {
  const queryClient = useQueryClient();
  const updateMutation = useUpdateNotebook();

  const optimisticUpdate = async (id: string, updates: Partial<Notebook>) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({ queryKey: queryKeys.notebook(id) });

    // Snapshot current value
    const previous = queryClient.getQueryData(queryKeys.notebook(id));

    // Optimistically update
    queryClient.setQueryData(queryKeys.notebook(id), (old: any) => ({
      ...old,
      ...updates,
    }));

    return { previous };
  };

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Notebook> }) =>
      workspacesApi.update(id, data),
    onMutate: ({ id, data }) => optimisticUpdate(id, data),
    onError: (err, variables, context) => {
      // Rollback on error
      if (context?.previous) {
        queryClient.setQueryData(
          queryKeys.notebook(variables.id),
          context.previous
        );
      }
    },
    onSettled: (data, error, variables) => {
      // Always refetch after mutation
      queryClient.invalidateQueries({ queryKey: queryKeys.notebook(variables.id) });
    },
  });
}
