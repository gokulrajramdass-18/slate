import { apiClient } from "./client";

export interface PromptTemplate {
  id: string;
  role: string;
  name: string;
  template: string;
  description?: string;
  is_default: boolean;
  created: string;
  updated: string;
}

export interface PromptTemplateUpdate {
  template: string;
  role?: string;  // Required for CREATE
  name?: string;
  description?: string;
}

export interface AgentPrompt {
  agent_id: string;
  role: string;
  prompt_template: string;
  is_custom: boolean;
  template_id?: string;
}

export const promptsApi = {
  // List all prompt templates
  list: async (): Promise<PromptTemplate[]> => {
    const { data } = await apiClient.get("/agents/prompts/templates");
    return data.templates || data;
  },

  // Get prompt template by role
  getByRole: async (role: string): Promise<PromptTemplate> => {
    const { data } = await apiClient.get(`/agents/prompts/templates/${role}`);
    return data;
  },

  // Create new prompt template (custom agent role)
  create: async (create: PromptTemplateUpdate): Promise<PromptTemplate> => {
    const { data } = await apiClient.post("/agents/prompts/templates", create);
    return data;
  },

  // Update prompt template
  update: async (role: string, update: PromptTemplateUpdate): Promise<PromptTemplate> => {
    const { data } = await apiClient.put(`/agents/prompts/templates/${role}`, update);
    return data;
  },

  // Reset prompt template to default
  reset: async (role: string): Promise<PromptTemplate> => {
    const { data } = await apiClient.post(`/agents/prompts/templates/${role}/reset`);
    return data;
  },

  // Delete custom prompt template
  delete: async (role: string): Promise<void> => {
    await apiClient.delete(`/agents/prompts/templates/${role}`);
  },

  // Get effective prompt for an agent
  getAgentPrompt: async (agentId: string): Promise<AgentPrompt> => {
    const { data } = await apiClient.get(`/agents/${agentId}/prompt`);
    return data;
  },

  // Set custom prompt for an agent
  updateAgentPrompt: async (agentId: string, template: string): Promise<AgentPrompt> => {
    const { data } = await apiClient.put(`/agents/${agentId}/prompt`, { template });
    return data;
  },

  // Reset agent prompt to role default
  resetAgentPrompt: async (agentId: string): Promise<AgentPrompt> => {
    const { data } = await apiClient.post(`/agents/${agentId}/prompt/reset`);
    return data;
  },
};
