/**
 * Orchestration API Client
 *
 * Handles autonomous agent orchestration API calls and SSE streaming.
 */

import { apiClient } from './client';

export interface OrchestrationRequest {
  goal: string;
  notebook_id?: string;
  resources?: Record<string, any>;
  config?: Record<string, any>;
}

export interface OrchestrationResponse {
  orchestration_id: string;
  status: string;
  orchestration_mode?: string;
  team_id?: string;
  result?: Record<string, any>;
  error?: string;
  timestamp: string;
}

export interface OrchestrationStatus {
  orchestration_id: string;
  status: string;
  current_phase: string;
  progress: number;
  team_id?: string;
  orchestration_mode?: string;
  started_at: string;
  updated_at: string;
}

export interface OrchestrationEvent {
  type: string;
  data: Record<string, any>;
  timestamp: string;
}

export interface OrchestrationListItem {
  orchestration_id: string;
  goal: string;
  status: string;
  orchestration_mode?: string;
  team_id?: string;
  created_at: string;
}

/**
 * Execute orchestration (non-streaming)
 */
export async function executeOrchestration(
  request: OrchestrationRequest
): Promise<OrchestrationResponse> {
  const response = await apiClient.post('/orchestration/execute', request);
  return response.data;
}

/**
 * Execute orchestration with SSE streaming using fetch
 *
 * @param request Orchestration request
 * @param onEvent Callback for each SSE event
 * @param onError Callback for errors
 * @param onComplete Callback when stream completes
 */
export async function executeOrchestrationStream(
  request: OrchestrationRequest,
  onEvent: (event: OrchestrationEvent) => void,
  onError?: (error: Error) => void,
  onComplete?: () => void
): Promise<void> {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5055';
  const url = `${baseUrl}/api/orchestration/execute/stream`;

  try {
    // Get user ID from auth store
    const { useAuthStore } = await import('@/lib/stores/auth-store');
    const userId = useAuthStore.getState().user?.id || 'default-user';

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-ID': userId,
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('No response body');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentEventType = 'message'; // Default SSE event type

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;

        // Parse SSE format: "event: type\ndata: {...}\n"
        if (line.startsWith('event:')) {
          // Store event type for next data line
          currentEventType = line.slice(6).trim();
          continue;
        }

        if (line.startsWith('data:')) {
          const dataStr = line.slice(5).trim();
          try {
            const data = JSON.parse(dataStr);

            // Use the event type from the event: line
            onEvent({
              type: currentEventType,
              data: data,
              timestamp: data.timestamp || new Date().toISOString(),
            });

            // Check for completion or error
            if (currentEventType === 'orchestration.completed') {
              if (onComplete) onComplete();
              return;
            }

            if (currentEventType === 'orchestration.error') {
              if (onError) onError(new Error(data.error || 'Orchestration failed'));
              return;
            }

            // Reset event type after processing
            currentEventType = 'message';
          } catch (e) {
            console.error('Failed to parse SSE data:', dataStr, e);
          }
        }
      }
    }

    if (onComplete) onComplete();
  } catch (error) {
    console.error('Stream error:', error);
    if (onError) onError(error as Error);
  }
}

/**
 * Get orchestration status
 */
export async function getOrchestrationStatus(
  orchestrationId: string
): Promise<OrchestrationStatus> {
  const response = await apiClient.get(`/orchestration/${orchestrationId}/status`);
  return response.data;
}

/**
 * Get orchestration events
 */
export async function getOrchestrationEvents(
  orchestrationId: string,
  afterTimestamp?: string
): Promise<OrchestrationEvent[]> {
  const params = new URLSearchParams();
  if (afterTimestamp) {
    params.set('after', afterTimestamp);
  }

  const url = `/orchestration/${orchestrationId}/events${params.toString() ? `?${params}` : ''}`;
  const response = await apiClient.get(url);
  return response.data;
}

/**
 * List orchestrations for current user
 */
export async function listOrchestrations(
  limit: number = 50,
  status?: string
): Promise<OrchestrationListItem[]> {
  const params = new URLSearchParams({ limit: limit.toString() });
  if (status) {
    params.set('status', status);
  }

  const response = await apiClient.get(`/orchestration?${params}`);
  return response.data;
}

/**
 * Cancel orchestration
 */
export async function cancelOrchestration(
  orchestrationId: string
): Promise<{ message: string }> {
  const response = await apiClient.post(`/orchestration/${orchestrationId}/cancel`);
  return response.data;
}

/**
 * Delete orchestration
 */
export async function deleteOrchestration(
  orchestrationId: string
): Promise<{ message: string }> {
  const response = await apiClient.delete(`/orchestration/${orchestrationId}`);
  return response.data;
}
