import { apiClient } from "./client";

export interface ChatPreferences {
  enable_generative_ui: boolean;
  stream_responses: boolean;
  include_context_by_default: boolean;
}

export interface ChatPreferencesUpdate {
  enable_generative_ui?: boolean;
  stream_responses?: boolean;
  include_context_by_default?: boolean;
}

export const chatSettingsApi = {
  // Get current chat preferences
  get: async (): Promise<ChatPreferences> => {
    const { data } = await apiClient.get("/chat/settings");
    return data;
  },

  // Update chat preferences
  update: async (updates: ChatPreferencesUpdate): Promise<ChatPreferences> => {
    const { data } = await apiClient.put("/chat/settings", updates);
    return data;
  },
};
