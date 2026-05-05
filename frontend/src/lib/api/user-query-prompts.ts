import { apiClient } from "./client";

export interface UserQueryPrompt {
  id: string;
  user_id: string;
  name: string;
  query_text: string;
  description?: string;
  category?: string;
  team_id?: string;
  prompt_role?: string;
  tags: string[];
  use_count: number;
  last_used?: string;
  is_favorite: boolean;
  created: string;
  updated: string;
}

export interface UserQueryPromptCreate {
  name: string;
  query_text: string;
  description?: string;
  category?: string;
  team_id?: string;
  prompt_role?: string;
  tags?: string[];
  is_favorite?: boolean;
}

export interface UserQueryPromptUpdate {
  name?: string;
  query_text?: string;
  description?: string;
  category?: string;
  tags?: string[];
  is_favorite?: boolean;
}

export const userQueryPromptsApi = {
  // List saved prompts
  list: async (params?: {
    team_id?: string;
    category?: string;
    is_favorite?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<UserQueryPrompt[]> => {
    const { data } = await apiClient.get("/user-query-prompts", { params });
    return data.prompts || [];
  },

  // Get specific prompt
  get: async (promptId: string): Promise<UserQueryPrompt> => {
    const { data } = await apiClient.get(`/user-query-prompts/${promptId}`);
    return data;
  },

  // Create new prompt
  create: async (prompt: UserQueryPromptCreate): Promise<UserQueryPrompt> => {
    const { data } = await apiClient.post("/user-query-prompts", prompt);
    return data;
  },

  // Update prompt
  update: async (
    promptId: string,
    update: UserQueryPromptUpdate
  ): Promise<UserQueryPrompt> => {
    const { data } = await apiClient.put(`/user-query-prompts/${promptId}`, update);
    return data;
  },

  // Delete prompt
  delete: async (promptId: string): Promise<void> => {
    await apiClient.delete(`/user-query-prompts/${promptId}`);
  },

  // Mark prompt as used (increments use count)
  markUsed: async (promptId: string): Promise<UserQueryPrompt> => {
    const { data } = await apiClient.post(`/user-query-prompts/${promptId}/use`);
    return data;
  },

  // Toggle favorite status
  toggleFavorite: async (promptId: string): Promise<UserQueryPrompt> => {
    const { data } = await apiClient.post(`/user-query-prompts/${promptId}/favorite`);
    return data;
  },
};
