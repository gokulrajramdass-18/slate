import { apiClient } from "./client";

export interface RolePermission {
  id: string;
  role_id: string;
  resource_type: string;
  action: string;
  scope: "own" | "team" | "all";
  conditions?: Record<string, any>;
  created: string;
  updated: string;
}

export interface Role {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  is_system_role: boolean;
  created_by?: string;
  created: string;
  updated: string;
  permissions: RolePermission[];
}

export interface RoleCreate {
  name: string;
  display_name: string;
  description?: string;
}

export interface RoleUpdate {
  display_name?: string;
  description?: string;
}

export interface RolePermissionCreate {
  resource_type: string;
  action: string;
  scope: "own" | "team" | "all";
  conditions?: Record<string, any>;
}

export interface RolePermissionUpdate {
  scope?: "own" | "team" | "all";
  conditions?: Record<string, any>;
}

export const rolesApi = {
  /**
   * List all roles
   */
  list: async (): Promise<Role[]> => {
    const response = await apiClient.get<Role[]>("/roles");
    return response.data;
  },

  /**
   * Get role by ID
   */
  get: async (id: string): Promise<Role> => {
    const response = await apiClient.get<Role>(`/roles/${id}`);
    return response.data;
  },

  /**
   * Create new role
   */
  create: async (data: RoleCreate): Promise<Role> => {
    const response = await apiClient.post<Role>("/roles", data);
    return response.data;
  },

  /**
   * Update role
   */
  update: async (id: string, data: RoleUpdate): Promise<Role> => {
    const response = await apiClient.put<Role>(`/roles/${id}`, data);
    return response.data;
  },

  /**
   * Delete role
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/roles/${id}`);
  },

  /**
   * Get role permissions
   */
  getPermissions: async (id: string): Promise<RolePermission[]> => {
    const response = await apiClient.get<RolePermission[]>(
      `/roles/${id}/permissions`
    );
    return response.data;
  },

  /**
   * Add permission to role
   */
  addPermission: async (
    roleId: string,
    permission: RolePermissionCreate
  ): Promise<RolePermission> => {
    const response = await apiClient.post<RolePermission>(
      `/roles/${roleId}/permissions`,
      permission
    );
    return response.data;
  },

  /**
   * Update role permission
   */
  updatePermission: async (
    roleId: string,
    permissionId: string,
    data: RolePermissionUpdate
  ): Promise<RolePermission> => {
    const response = await apiClient.put<RolePermission>(
      `/roles/${roleId}/permissions/${permissionId}`,
      data
    );
    return response.data;
  },

  /**
   * Remove permission from role
   */
  removePermission: async (
    roleId: string,
    permissionId: string
  ): Promise<void> => {
    await apiClient.delete(`/roles/${roleId}/permissions/${permissionId}`);
  },
};
