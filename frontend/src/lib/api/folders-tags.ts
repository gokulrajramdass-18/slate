import { apiClient } from "./client";
import type { Folder, Tag } from "@/lib/types";

export const foldersApi = {
  // List all folders
  list: async (): Promise<Folder[]> => {
    const { data } = await apiClient.get("/folders");
    return data;
  },

  // Get folder with children (tree structure)
  getTree: async (folderId?: string): Promise<Folder> => {
    const url = folderId ? `/folders/${folderId}/tree` : "/folders/tree";
    const { data } = await apiClient.get(url);
    return data;
  },

  // Create folder
  create: async (folder: {
    name: string;
    parent_id?: string;
  }): Promise<Folder> => {
    const { data } = await apiClient.post("/folders", folder);
    return data;
  },

  // Update folder
  update: async (
    id: string,
    updates: { name?: string; parent_id?: string }
  ): Promise<Folder> => {
    const { data } = await apiClient.put(`/folders/${id}`, updates);
    return data;
  },

  // Delete folder
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/folders/${id}`);
  },
};

export const tagsApi = {
  // List all tags
  list: async (): Promise<Tag[]> => {
    const { data } = await apiClient.get("/tags");
    return data;
  },

  // Create tag
  create: async (tag: { name: string; color?: string }): Promise<Tag> => {
    const { data } = await apiClient.post("/tags", tag);
    return data;
  },

  // Update tag
  update: async (
    id: string,
    updates: { name?: string; color?: string }
  ): Promise<Tag> => {
    const { data } = await apiClient.put(`/tags/${id}`, updates);
    return data;
  },

  // Delete tag
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/tags/${id}`);
  },

  // Get notebooks with tag
  getNotebooks: async (tagId: string): Promise<string[]> => {
    const { data } = await apiClient.get(`/tags/${tagId}/workspaces`);
    return data;
  },
};
