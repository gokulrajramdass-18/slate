import { apiClient } from "./client";
import type {
  Memory,
  MemoryCreate,
  MemoryUpdate,
  MemorySearchRequest,
  MemorySearchResult,
  MemoryType,
} from "@/lib/types";

export const memoryApi = {
  // ========================================================================
  // CRUD
  // ========================================================================

  list: async (params?: {
    memory_type?: MemoryType;
    tags?: string[];
    limit?: number;
    offset?: number;
  }): Promise<Memory[]> => {
    const { data } = await apiClient.get("/memory", { params });
    return data;
  },

  get: async (memoryId: string): Promise<Memory> => {
    const { data } = await apiClient.get(`/memory/${memoryId}`);
    return data;
  },

  create: async (memory: MemoryCreate): Promise<Memory> => {
    const { data } = await apiClient.post("/memory", memory);
    return data;
  },

  update: async (memoryId: string, updates: MemoryUpdate): Promise<Memory> => {
    const { data } = await apiClient.put(`/memory/${memoryId}`, updates);
    return data;
  },

  delete: async (memoryId: string): Promise<void> => {
    await apiClient.delete(`/memory/${memoryId}`);
  },

  // ========================================================================
  // SEARCH
  // ========================================================================

  search: async (request: MemorySearchRequest): Promise<MemorySearchResult[]> => {
    const { data } = await apiClient.post("/memory/search", request);
    return data;
  },

  // ========================================================================
  // BULK OPERATIONS
  // ========================================================================

  getStats: async (): Promise<{
    total: number;
    by_type: Record<MemoryType, number>;
    by_priority: Record<string, number>;
    expired: number;
  }> => {
    const { data } = await apiClient.get("/memory/stats");
    return data;
  },

  clearExpired: async (): Promise<{ deleted: number }> => {
    const { data } = await apiClient.post("/memory/clear-expired");
    return data;
  },

  getTags: async (): Promise<string[]> => {
    const { data } = await apiClient.get("/memory/tags");
    return data;
  },
};
