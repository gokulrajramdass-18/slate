import { apiClient } from "./client";
import type {
  Notebook,
  NotebookCreate,
  Source,
  Note,
  ChatSession,
} from "@/lib/types";

export const workspacesApi = {
  // List all notebooks
  list: async (params?: {
    folder_id?: string;
    archived?: boolean;
    tags?: string[];
  }): Promise<Notebook[]> => {
    const { data } = await apiClient.get("/workspaces", { params });
    return data;
  },

  // List notebooks with execution plans (for template creation)
  listWithPlans: async (): Promise<Notebook[]> => {
    const { data } = await apiClient.get("/workspaces/with-plans");
    return data;
  },

  // Get single notebook
  get: async (id: string): Promise<Notebook> => {
    const { data } = await apiClient.get(`/workspaces/${id}`);
    return data;
  },

  // Create notebook
  create: async (notebook: NotebookCreate): Promise<Notebook> => {
    const { data } = await apiClient.post("/workspaces", notebook);
    return data;
  },

  // Update notebook
  update: async (id: string, notebook: Partial<Notebook>): Promise<Notebook> => {
    const { data } = await apiClient.put(`/workspaces/${id}`, notebook);
    return data;
  },

  // Delete notebook
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/workspaces/${id}`);
  },

  // Duplicate notebook
  duplicate: async (id: string): Promise<Notebook> => {
    const { data } = await apiClient.post(`/workspaces/${id}/duplicate`);
    return data;
  },

  // Get sources in notebook
  getSources: async (id: string): Promise<Source[]> => {
    const { data} = await apiClient.get(`/workspaces/${id}/sources`);
    return data;
  },

  // Add source to notebook
  addSource: async (notebookId: string, sourceId: string): Promise<void> => {
    await apiClient.post(`/workspaces/${notebookId}/sources`, { source_id: sourceId });
  },

  // Remove source from notebook
  removeSource: async (notebookId: string, sourceId: string): Promise<void> => {
    await apiClient.delete(`/workspaces/${notebookId}/sources/${sourceId}`);
  },

  // Get notes in notebook
  getNotes: async (id: string): Promise<Note[]> => {
    const { data } = await apiClient.get(`/workspaces/${id}/notes`);
    return data;
  },

  // Get chat sessions for notebook
  getChatSessions: async (id: string): Promise<ChatSession[]> => {
    const { data } = await apiClient.get(`/workspaces/${id}/chat-sessions`);
    return data;
  },
};
