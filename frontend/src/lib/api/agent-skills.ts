/**
 * Agent Skills API Client
 *
 * API client for managing agent skills, bindings, and executions.
 */

import { apiClient } from "./client";

export interface Skill {
  id: string;
  name: string;
  description: string | null;
  category: string;
  skill_type: string;
  definition?: any;
  input_schema?: any;
  output_schema?: any;
  roles: string[];
  tags: string[];
  enabled: boolean;
  metadata?: any;
  created: string;
  updated: string;
  // Legacy fields for backward compatibility
  version?: string;
  author?: string;
  allowed_roles?: string[];
  config_schema?: any;
  default_config?: any;
  deprecated?: boolean;
}

export interface SkillBinding {
  id: string;
  skill_id: string;
  agent_id?: string;
  role?: string;
  team_id?: string;
  config?: any;
  enabled: boolean;
  created: string;
  created_by?: string;
}

export interface SkillExecution {
  id: string;
  skill_id: string;
  execution_id: string;
  agent_id?: string;
  team_id?: string;
  success: boolean;
  error?: string;
  duration_ms: number;
  started_at: string;
  ended_at?: string;
}

export const agentSkillsApi = {
  /**
   * List all registered skills
   */
  async listSkills(category?: string, role?: string): Promise<Skill[]> {
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (role) params.append("role", role);

    // Trailing slash is deliberate: the backend route is mounted at
    // `/api/agent-skills/`, and without it FastAPI replies 307 →
    // `/api/agent-skills/`. Behind XSUAA the AppRouter turns that
    // redirect into a re-auth bounce, surfacing as "Error loading
    // skills" in the UI. Calling the canonical URL avoids the round-trip.
    const qs = params.toString();
    const url = qs ? `/agent-skills/?${qs}` : `/agent-skills/`;
    const response = await apiClient.get(url);
    // Backend returns {skills: [...]} not just [...]
    return response.data.skills || response.data || [];
  },

  /**
   * Create a new custom skill
   */
  async createSkill(skill: Partial<Skill> & { handler_module: string; handler_function: string }): Promise<Skill> {
    const response = await apiClient.post("/agent-skills", skill);
    return response.data;
  },

  /**
   * Update an existing skill.
   *
   * The backend rejects edits to `skill_type` and `definition` for
   * built-in skills (their backing code lives in the in-process
   * registry, so DB edits to those fields would only create drift).
   * All other fields — name, description, category, tags, roles,
   * enabled, input/output schema, metadata — are editable on every
   * skill, including builtins.
   */
  async updateSkill(skillId: string, payload: Partial<Skill>): Promise<Skill> {
    const response = await apiClient.put(`/agent-skills/${skillId}`, payload);
    return response.data;
  },

  /**
   * Get skill details by ID
   */
  async getSkill(skillId: string): Promise<Skill> {
    const response = await apiClient.get(`/agent-skills/${skillId}`);
    return response.data;
  },

  /**
   * Search skills
   */
  async searchSkills(
    query: string,
    category?: string,
    role?: string
  ): Promise<Skill[]> {
    const params = new URLSearchParams({ q: query });
    if (category) params.append("category", category);
    if (role) params.append("role", role);

    const response = await apiClient.get(
      `/agent-skills/search?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get skills by category
   */
  async getSkillsByCategory(category: string): Promise<Skill[]> {
    const response = await apiClient.get(`/agent-skills/category/${category}`);
    return response.data;
  },

  /**
   * Get skills accessible to a role
   */
  async getSkillsForRole(role: string): Promise<Skill[]> {
    const response = await apiClient.get(`/agent-skills/role/${role}`);
    return response.data;
  },

  // ------------------------------------------------------------------
  // Skill Bindings
  // ------------------------------------------------------------------

  /**
   * Bind skill to a specific agent
   */
  async bindToAgent(
    agentId: string,
    skillId: string,
    config?: any
  ): Promise<{ binding_id: string }> {
    const response = await apiClient.post(
      `/agent-skills/agents/${agentId}/skills`,
      { skill_id: skillId, config }
    );
    return response.data;
  },

  /**
   * Bind skill to all agents with a role
   */
  async bindToRole(
    role: string,
    skillId: string,
    config?: any
  ): Promise<{ binding_id: string }> {
    const response = await apiClient.post(
      `/agent-skills/roles/${role}/skills`,
      { skill_id: skillId, config }
    );
    return response.data;
  },

  /**
   * Bind skill to an entire team
   */
  async bindToTeam(
    teamId: string,
    skillId: string,
    config?: any
  ): Promise<{ binding_id: string }> {
    const response = await apiClient.post(
      `/agent-skills/teams/${teamId}/skills`,
      { skill_id: skillId, config }
    );
    return response.data;
  },

  /**
   * List all skill bindings
   */
  async listBindings(
    agentId?: string,
    teamId?: string
  ): Promise<SkillBinding[]> {
    const params = new URLSearchParams();
    if (agentId) params.append("agent_id", agentId);
    if (teamId) params.append("team_id", teamId);

    const response = await apiClient.get(
      `/agent-skills/bindings?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Delete a skill binding
   */
  async deleteBinding(bindingId: string): Promise<void> {
    await apiClient.delete(`/agent-skills/bindings/${bindingId}`);
  },

  /**
   * Get skills for a specific agent
   */
  async getAgentSkills(agentId: string): Promise<{
    agent_id: string;
    skills: Skill[];
  }> {
    const response = await apiClient.get(`/agents/${agentId}/skills`);
    return response.data;
  },

  /**
   * Get skills for a team
   */
  async getTeamSkills(teamId: string): Promise<{
    team_id: string;
    skills: Skill[];
  }> {
    const response = await apiClient.get(`/teams/${teamId}/skills`);
    return response.data;
  },

  /**
   * Unbind skill from agent
   */
  async unbindFromAgent(agentId: string, skillId: string): Promise<void> {
    await apiClient.delete(`/agents/${agentId}/skills/${skillId}`);
  },

  // ------------------------------------------------------------------
  // Skill Execution
  // ------------------------------------------------------------------

  /**
   * Execute a skill
   */
  async executeSkill(
    skillId: string,
    agentId: string,
    inputData: any,
    config?: any
  ): Promise<any> {
    const response = await apiClient.post(`/agent-skills/${skillId}/execute`, {
      agent_id: agentId,
      input_data: inputData,
      config,
    });
    return response.data;
  },

  /**
   * Get skill execution history
   */
  async getExecutions(
    skillId: string,
    limit?: number
  ): Promise<SkillExecution[]> {
    const params = new URLSearchParams();
    if (limit) params.append("limit", limit.toString());

    const response = await apiClient.get(
      `/agent-skills/${skillId}/executions?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get execution statistics
   */
  async getExecutionStats(skillId?: string): Promise<any> {
    const endpoint = skillId
      ? `/agent-skills/${skillId}/stats`
      : `/agent-skills/stats`;
    const response = await apiClient.get(endpoint);
    return response.data;
  },
};
