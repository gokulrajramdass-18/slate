import { apiClient } from "./client";
import type {
  Tool,
  ToolCreate,
  ToolUpdate,
  ToolPermission,
  PermissionCreate,
  PermissionUpdate,
  ToolUsageStat,
} from "@/lib/types";

export const toolsApi = {
  // List tools with optional filters
  list: async (params?: {
    category?: string;
    enabled?: boolean;
  }): Promise<Tool[]> => {
    const { data } = await apiClient.get("/tools", { params });
    return data.tools ?? data;
  },

  // Get single tool
  get: async (toolId: string): Promise<Tool> => {
    const { data } = await apiClient.get(`/tools/${toolId}`);
    return data;
  },

  // Create a new tool
  create: async (tool: ToolCreate): Promise<{ id: string }> => {
    const { data } = await apiClient.post("/tools", tool);
    return data;
  },

  // Update a tool
  update: async (
    toolId: string,
    update: ToolUpdate
  ): Promise<{ success: boolean }> => {
    const { data } = await apiClient.put(`/tools/${toolId}`, update);
    return data;
  },

  // Delete a tool
  delete: async (toolId: string): Promise<{ success: boolean }> => {
    const { data } = await apiClient.delete(`/tools/${toolId}`);
    return data;
  },

  // Toggle tool enabled/disabled
  toggle: async (
    toolId: string,
    enabled: boolean
  ): Promise<{ success: boolean }> => {
    const { data } = await apiClient.post(`/tools/${toolId}/toggle`, null, {
      params: { enabled },
    });
    return data;
  },

  // --- Permissions ---

  // List permissions for a tool
  listPermissions: async (toolId: string): Promise<ToolPermission[]> => {
    const { data } = await apiClient.get(`/tools/${toolId}/permissions`);
    return data.permissions ?? data;
  },

  // Add permission to a tool
  addPermission: async (
    toolId: string,
    perm: PermissionCreate
  ): Promise<{ id: string }> => {
    const { data } = await apiClient.post(`/tools/${toolId}/permissions`, {
      tool_id: toolId,
      ...perm,
    });
    return data;
  },

  // Update a permission
  updatePermission: async (
    permId: string,
    update: PermissionUpdate
  ): Promise<{ success: boolean }> => {
    const { data } = await apiClient.put(
      `/tools/permissions/${permId}`,
      update
    );
    return data;
  },

  // Delete a permission
  deletePermission: async (
    permId: string
  ): Promise<{ success: boolean }> => {
    const { data } = await apiClient.delete(`/tools/permissions/${permId}`);
    return data;
  },

  // --- Usage Analytics ---

  // Get usage stats for a tool
  getUsage: async (
    toolId: string,
    days: number = 7
  ): Promise<ToolUsageStat[]> => {
    const { data } = await apiClient.get(`/tools/${toolId}/usage`, {
      params: { days },
    });
    return data.usage ?? data;
  },
};
