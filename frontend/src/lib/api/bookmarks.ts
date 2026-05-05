import { apiClient } from "./client";
import type {
  BookmarkCreate,
  BookmarkUpdate,
  BookmarkToggleResponse,
  BookmarkListResponse,
  BookmarkCheckResponse,
  BookmarkBulkCheckResponse,
  EnrichedBookmark,
} from "@/lib/types";

export const bookmarksApi = {
  toggle: async (data: BookmarkCreate): Promise<BookmarkToggleResponse> => {
    const response = await apiClient.post("/bookmarks/toggle", data);
    return response.data;
  },

  list: async (params?: {
    entity_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<BookmarkListResponse> => {
    const response = await apiClient.get("/bookmarks", { params });
    return response.data;
  },

  get: async (id: string): Promise<EnrichedBookmark> => {
    const response = await apiClient.get(`/bookmarks/${id}`);
    return response.data;
  },

  check: async (
    entityType: string,
    entityId: string
  ): Promise<BookmarkCheckResponse> => {
    const response = await apiClient.get(
      `/bookmarks/check/${entityType}/${entityId}`
    );
    return response.data;
  },

  bulkCheck: async (
    entityType: string,
    entityIds: string[]
  ): Promise<BookmarkBulkCheckResponse> => {
    const response = await apiClient.post("/bookmarks/bulk-check", {
      entity_type: entityType,
      entity_ids: entityIds,
    });
    return response.data;
  },

  update: async (
    id: string,
    data: BookmarkUpdate
  ): Promise<EnrichedBookmark> => {
    const response = await apiClient.put(`/bookmarks/${id}`, data);
    return response.data;
  },

  delete: async (id: string): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/bookmarks/${id}`);
    return response.data;
  },
};
