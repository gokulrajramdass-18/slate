/**
 * API Client for Standalone Agents
 *
 * Manages individual agents with their own tools, MCP servers, and data sources
 */

import { apiClient } from "./client";
import type {
  StandaloneAgent,
  StandaloneAgentCreate,
  StandaloneAgentUpdate,
  StandaloneAgentExecution,
  StandaloneAgentExecuteRequest,
} from "@/lib/types";

/**
 * Create a new standalone agent
 */
export async function createStandaloneAgent(
  data: StandaloneAgentCreate
): Promise<StandaloneAgent> {
  const response = await apiClient.post("/standalone-agents", data);
  return response.data;
}

/**
 * Get all standalone agents
 */
export async function listStandaloneAgents(params?: {
  notebook_id?: string;
  status?: string;
  role?: string;
  limit?: number;
  offset?: number;
}): Promise<{ agents: StandaloneAgent[]; total: number }> {
  const response = await apiClient.get("/standalone-agents", { params });
  return response.data;
}

/**
 * Get a single standalone agent by ID
 */
export async function getStandaloneAgent(id: string): Promise<StandaloneAgent> {
  const response = await apiClient.get(`/standalone-agents/${id}`);
  return response.data;
}

/**
 * Update a standalone agent
 */
export async function updateStandaloneAgent(
  id: string,
  data: StandaloneAgentUpdate
): Promise<StandaloneAgent> {
  const response = await apiClient.put(`/standalone-agents/${id}`, data);
  return response.data;
}

/**
 * Delete a standalone agent
 */
export async function deleteStandaloneAgent(id: string): Promise<void> {
  await apiClient.delete(`/standalone-agents/${id}`);
}

/**
 * Execute a standalone agent (non-streaming)
 */
export async function executeStandaloneAgent(
  agentId: string,
  request: StandaloneAgentExecuteRequest
): Promise<StandaloneAgentExecution> {
  const response = await apiClient.post(
    `/standalone-agents/${agentId}/execute`,
    request
  );
  return response.data;
}

/**
 * Execute a standalone agent with streaming
 */
export async function executeStandaloneAgentStream(
  agentId: string,
  request: StandaloneAgentExecuteRequest,
  onEvent: (event: any) => void
): Promise<void> {
  const API_BASE =
    import.meta.env.VITE_API_URL || "/api";
  const response = await fetch(
    `${API_BASE}/standalone-agents/${agentId}/execute/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }
  );

  if (!response.ok) {
    throw new Error("Failed to start execution");
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let i = 0;
      while (i < lines.length) {
        const line = lines[i];
        if (line.startsWith("event:")) {
          const eventType = line.substring(6).trim();
          // Look for the next line which should be data
          if (i + 1 < lines.length && lines[i + 1].startsWith("data:")) {
            const dataLine = lines[i + 1];
            const data = JSON.parse(dataLine.substring(5).trim());
            onEvent({ type: eventType, data });
            i += 2; // Skip both event and data lines
            continue;
          }
        }
        i++;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * Get execution history for an agent
 */
export async function listStandaloneAgentExecutions(
  agentId: string,
  params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }
): Promise<{ executions: StandaloneAgentExecution[]; total: number }> {
  const response = await apiClient.get(
    `/standalone-agents/${agentId}/executions`,
    { params }
  );
  return response.data;
}

/**
 * Get a specific execution
 */
export async function getStandaloneAgentExecution(
  executionId: string
): Promise<StandaloneAgentExecution> {
  const response = await apiClient.get(
    `/standalone-agents/executions/${executionId}`
  );
  return response.data;
}

/**
 * Delete an execution
 */
export async function deleteStandaloneAgentExecution(
  executionId: string
): Promise<void> {
  await apiClient.delete(`/standalone-agents/executions/${executionId}`);
}

/**
 * Cancel a running execution
 */
export async function cancelStandaloneAgentExecution(
  executionId: string
): Promise<{ message: string }> {
  const response = await apiClient.post(
    `/standalone-agents/executions/${executionId}/cancel`
  );
  return response.data;
}
