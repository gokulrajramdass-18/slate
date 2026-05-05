import { apiClient } from "./client";

export interface User {
  id: string;
  username: string;
  email?: string;
  full_name?: string;
  avatar_url?: string;
  status: "active" | "suspended" | "deleted";
  is_superadmin: boolean;
  last_login?: string;
  created: string;
  updated: string;
  roles: Array<{
    id: string;
    name: string;
    display_name: string;
  }>;
}

export interface UserCreate {
  username: string;
  email?: string;
  password: string;
  full_name?: string;
}

export interface UserUpdate {
  email?: string;
  full_name?: string;
  avatar_url?: string;
  status?: "active" | "suspended" | "deleted";
}

export interface PasswordChange {
  old_password: string;
  new_password: string;
}

export const usersApi = {
  /**
   * List all users
   */
  list: async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<User[]> => {
    const response = await apiClient.get<User[]>("/users", { params });
    return response.data;
  },

  /**
   * Get user by ID
   */
  get: async (id: string): Promise<User> => {
    const response = await apiClient.get<User>(`/users/${id}`);
    return response.data;
  },

  /**
   * Create new user
   */
  create: async (data: UserCreate): Promise<User> => {
    const response = await apiClient.post<User>("/users", data);
    return response.data;
  },

  /**
   * Update user
   */
  update: async (id: string, data: UserUpdate): Promise<User> => {
    const response = await apiClient.put<User>(`/users/${id}`, data);
    return response.data;
  },

  /**
   * Delete user
   */
  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/users/${id}`);
  },

  /**
   * Change user password
   */
  changePassword: async (id: string, data: PasswordChange): Promise<void> => {
    await apiClient.post(`/users/${id}/password`, data);
  },

  /**
   * Assign role to user
   */
  assignRole: async (userId: string, roleId: string): Promise<void> => {
    await apiClient.post(`/users/${userId}/roles/${roleId}`);
  },

  /**
   * Remove role from user
   */
  removeRole: async (userId: string, roleId: string): Promise<void> => {
    await apiClient.delete(`/users/${userId}/roles/${roleId}`);
  },
};
