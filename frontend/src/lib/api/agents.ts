import { apiClient } from "./client";
import type {
  AgentTeam,
  TeamCreateRequest,
  TeamExecution,
  TeamExecuteRequest,
  AgentTask,
  AgentMessage,
  Agent,
  EvaluationConfig,
  ExecutionEvaluations,
} from "@/lib/types";

export const agentsApi = {
  // ========================================================================
  // TEAMS
  // ========================================================================

  listTeams: async (): Promise<AgentTeam[]> => {
    const { data } = await apiClient.get("/agents/teams");
    // Backend returns {teams: [...], total: N}
    const teams = data.teams || [];
    // Normalize agents to ensure arrays are not null
    return teams.map((team: AgentTeam) => ({
      ...team,
      agents: team.agents.map((agent) => ({
        ...agent,
        tools: agent.tools || agent.tool_ids || [],
        capabilities: agent.capabilities || agent.config?.capabilities || [],
      })),
    }));
  },

  getTeam: async (teamId: string): Promise<AgentTeam> => {
    const { data } = await apiClient.get(`/agents/teams/${teamId}`);
    // Normalize agents to ensure arrays are not null
    return {
      ...data,
      agents: data.agents.map((agent: any) => ({
        ...agent,
        tools: agent.tools || agent.tool_ids || [],
        capabilities: agent.capabilities || agent.config?.capabilities || [],
      })),
    };
  },

  createTeam: async (request: TeamCreateRequest): Promise<AgentTeam> => {
    const { data } = await apiClient.post("/agents/teams", request);
    return data;
  },

  updateTeam: async (teamId: string, request: TeamCreateRequest): Promise<AgentTeam> => {
    const { data } = await apiClient.put(`/agents/teams/${teamId}`, request);
    return data;
  },

  deleteTeam: async (teamId: string): Promise<void> => {
    await apiClient.delete(`/agents/teams/${teamId}`);
  },

  // ========================================================================
  // AGENTS
  // ========================================================================

  listAgents: async (teamId?: string): Promise<Agent[]> => {
    const params = teamId ? { team_id: teamId } : undefined;
    const { data } = await apiClient.get("/agents", { params });
    // Backend returns {agents: [...], total: N}
    return data.agents || [];
  },

  getAgent: async (agentId: string): Promise<Agent> => {
    const { data } = await apiClient.get(`/agents/${agentId}`);
    return data;
  },

  // ========================================================================
  // EXECUTION
  // ========================================================================

  executeTeam: async (
    teamId: string,
    request: TeamExecuteRequest,
    onStep?: (step: any) => void,
    onMessage?: (message: AgentMessage) => void,
    onTaskUpdate?: (task: AgentTask) => void,
    onComplete?: (result: TeamExecution) => void,
    onError?: (error: string) => void
  ): Promise<TeamExecution | void> => {
    if (onStep) {
      // SSE streaming mode - use /execute/stream endpoint
      const response = await fetch(
        `${apiClient.defaults.baseURL}/agents/teams/${teamId}/execute/stream`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: apiClient.defaults.headers.Authorization as string,
          },
          body: JSON.stringify(request), // Don't add stream: true
        }
      );

      if (!response.ok) {
        const errorText = await response.text();
        onError?.(errorText || `Request failed: ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onError?.("No response body reader");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = "";
      let dataBuffer = "";
      let stepCounter = 0; // Track step numbers across all events

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmedLine = line.trim();

          if (trimmedLine.startsWith("event:")) {
            currentEvent = trimmedLine.slice(6).trim();
            dataBuffer = "";
          } else if (trimmedLine.startsWith("data:")) {
            dataBuffer += trimmedLine.slice(5).trim();
          } else if (trimmedLine === "" && dataBuffer && currentEvent) {
            try {
              const data = JSON.parse(dataBuffer);

              console.log(`[SSE] Received event: ${currentEvent}`, data);

              switch (currentEvent) {
                case "metadata":
                  // Initial metadata - capture execution ID and pass to onComplete with initial state
                  console.log("[SSE] Execution metadata:", data);
                  onComplete?.({
                    id: data.execution_id,
                    team_id: teamId,
                    query: request.query,
                    status: "running",
                    started_at: data.timestamp || new Date().toISOString(),
                    steps: [],
                    tasks: [],
                    messages: [],
                  } as any);
                  break;
                case "step_complete":
                case "step_start":
                  // Convert to step format and pass to onStep
                  stepCounter++;
                  const stepData = {
                    id: data.step || data.name || `step-${Date.now()}`,
                    step_number: stepCounter,
                    title: data.step || data.name,
                    action: data.step || data.name,
                    status: currentEvent === "step_complete" ? "completed" : "in_progress",
                    started_at: data.timestamp || new Date().toISOString(),
                    completed_at: currentEvent === "step_complete" ? (data.timestamp || new Date().toISOString()) : undefined,
                    output: typeof data.output === "string" ? data.output : JSON.stringify(data.output || data.data, null, 2),
                    result: typeof data.output === "string" ? data.output : JSON.stringify(data.output || data.data, null, 2),
                    duration_ms: data.duration_ms,
                  };
                  console.log("[SSE] Calling onStep with:", stepData);
                  onStep?.(stepData);
                  break;
                case "tool_call":
                  // Tool is being called
                  stepCounter++;
                  const toolName = data.tool || data.tool_name || "unknown_tool";
                  onStep({
                    id: `tool-${toolName}-${Date.now()}`,
                    step_number: stepCounter,
                    title: `Tool: ${toolName}`,
                    action: `Tool: ${toolName}`,
                    status: "in_progress",
                    started_at: data.timestamp || new Date().toISOString(),
                    output: JSON.stringify(data.args || data.tool_args || {}, null, 2),
                  });
                  break;
                case "tool_result":
                  // Tool result received
                  stepCounter++;
                  const resultToolName = data.tool || data.tool_name || "unknown_tool";
                  onStep({
                    id: `tool-${resultToolName}-result-${Date.now()}`,
                    step_number: stepCounter,
                    title: `Tool Result: ${resultToolName}`,
                    action: `Tool Result: ${resultToolName}`,
                    status: "completed",
                    started_at: data.timestamp || new Date().toISOString(),
                    completed_at: data.timestamp || new Date().toISOString(),
                    output: typeof data.result === "string" ? data.result : JSON.stringify(data.result || data.tool_result || {}, null, 2),
                    result: typeof data.result === "string" ? data.result : JSON.stringify(data.result || data.tool_result || {}, null, 2),
                    duration_ms: data.duration_ms,
                  });
                  break;
                case "message":
                  console.log("[SSE] Calling onMessage with:", data);
                  onMessage?.(data);
                  break;
                case "task_update":
                  console.log("[SSE] Calling onTaskUpdate with:", data);
                  onTaskUpdate?.(data);
                  break;
                case "done":
                  console.log("[SSE] Execution complete:", data);
                  onComplete?.(data);
                  return data;
                case "error":
                  console.error("[SSE] Execution error:", data);
                  onError?.(data.error || "Execution failed");
                  break;
                default:
                  console.warn(`[SSE] Unknown event type: ${currentEvent}`, data);
              }

              currentEvent = "";
              dataBuffer = "";
            } catch {
              dataBuffer = "";
            }
          }
        }
      }
      return;
    }

    // Non-streaming
    const { data } = await apiClient.post(
      `/agents/teams/${teamId}/execute`,
      request
    );
    return data;
  },

  // ========================================================================
  // EXECUTION HISTORY
  // ========================================================================

  listExecutions: async (teamId: string): Promise<TeamExecution[]> => {
    const { data } = await apiClient.get(`/agents/teams/${teamId}/executions`);
    console.log("[agentsApi.listExecutions] Raw response:", data);
    // Backend returns {executions: [...], total: N}
    const executions = data.executions || [];
    console.log("[agentsApi.listExecutions] Parsed executions:", executions);
    console.log("[agentsApi.listExecutions] First execution:", executions[0]);
    if (executions[0]) {
      console.log("[agentsApi.listExecutions] First execution steps:", executions[0].steps);
      console.log("[agentsApi.listExecutions] First execution tasks:", executions[0].tasks);
      console.log("[agentsApi.listExecutions] First execution messages:", executions[0].messages);
    }
    return executions;
  },

  getExecution: async (executionId: string): Promise<TeamExecution> => {
    const { data } = await apiClient.get(`/agents/executions/${executionId}`);
    return data;
  },

  // ========================================================================
  // TASKS
  // ========================================================================

  listTasks: async (teamId: string, executionId?: string): Promise<AgentTask[]> => {
    const params = executionId ? { execution_id: executionId } : undefined;
    const { data } = await apiClient.get(`/agents/teams/${teamId}/tasks`, { params });
    // Backend returns {tasks: [...], total: N}
    return data.tasks || [];
  },

  // ========================================================================
  // MESSAGES
  // ========================================================================

  listMessages: async (teamId: string, executionId?: string): Promise<AgentMessage[]> => {
    const params = executionId ? { execution_id: executionId } : undefined;
    const { data } = await apiClient.get(`/agents/teams/${teamId}/messages`, { params });
    return data;
  },

  // ========================================================================
  // EVALUATION CONFIGURATION
  // ========================================================================

  createEvaluationConfig: async (
    teamId: string,
    config: {
      enabled: boolean;
      auto_evaluate: boolean;
      scope: "final_only" | "agents_only" | "all";
      scoring_scale: "0-10" | "1-5" | "percentage";
    }
  ): Promise<void> => {
    await apiClient.post(`/agents/teams/${teamId}/evaluation/config`, config);
  },

  getEvaluationConfig: async (teamId: string): Promise<EvaluationConfig> => {
    const { data } = await apiClient.get<EvaluationConfig>(
      `/agents/teams/${teamId}/evaluation/config`
    );
    return data;
  },

  updateEvaluationConfig: async (
    teamId: string,
    updates: Partial<EvaluationConfig>
  ): Promise<void> => {
    await apiClient.post(`/agents/teams/${teamId}/evaluation/config`, updates);
  },

  // ========================================================================
  // EVALUATION TRIGGERS
  // ========================================================================

  triggerEvaluation: async (
    executionId: string,
    scope?: "final_only" | "agents_only" | "all"
  ): Promise<{ message: string }> => {
    const { data } = await apiClient.post<{ message: string }>(
      `/agents/executions/${executionId}/evaluate`,
      scope ? { scope } : {}
    );
    return data;
  },

  getExecutionEvaluations: async (
    executionId: string
  ): Promise<ExecutionEvaluations> => {
    const { data } = await apiClient.get<ExecutionEvaluations>(
      `/agents/executions/${executionId}/evaluations`
    );
    return data;
  },
};
