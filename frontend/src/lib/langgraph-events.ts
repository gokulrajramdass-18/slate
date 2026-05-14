/**
 * Utility functions for handling LangGraph SSE events and converting them to AgentStep format
 */

import { AgentStep } from '@/lib/types';

export interface LangGraphEvent {
  event: 'metadata' | 'step_start' | 'step_complete' | 'tool_call' | 'tool_result' | 'llm_call' | 'llm_response' | 'done' | 'error';
  data: {
    execution_id?: string;
    team_id?: string;
    query?: string;
    step?: string;
    input?: any;
    output?: any;
    tool?: string;
    args?: any;
    prompt?: string;
    response?: any;
    error?: string;
    timestamp?: string;
    [key: string]: any;
  };
}

/**
 * Convert LangGraph SSE event to AgentStep
 */
export function convertLangGraphEventToStep(event: LangGraphEvent): AgentStep | null {
  const { event: eventType, data } = event;

  const timestamp = data.timestamp || new Date().toISOString();

  switch (eventType) {
    case 'metadata':
      return {
        step_type: 'analysis',
        content: `Starting execution: ${data.query?.substring(0, 100) || ''}...`,
        timestamp,
        status: 'completed',
        metadata: {
          execution_id: data.execution_id,
          team_id: data.team_id,
          query: data.query,
          available_tools: data.available_tools,
          available_sources: data.available_sources
        }
      };

    case 'step_start':
      return {
        step_type: 'step_start',
        content: `Starting: ${data.step || 'Unknown step'}`,
        timestamp,
        status: 'running',
        metadata: {
          step: data.step,
          input: data.input
        }
      };

    case 'step_complete':
      // Check if this is a special step (analysis, planning, aggregation)
      const step = data.step?.toLowerCase() || '';

      if (step.includes('analyze') || step === 'analyze_query') {
        return {
          step_type: 'analysis',
          content: 'Query analysis complete',
          timestamp,
          status: 'completed',
          metadata: {
            step: data.step,
            output: data.output,
            analysis: data.output?.analysis || data.output
          }
        };
      }

      if (step.includes('plan') || step === 'create_plan') {
        return {
          step_type: 'planning',
          content: `Execution plan created: ${data.output?.plan?.length || 0} steps`,
          timestamp,
          status: 'completed',
          metadata: {
            step: data.step,
            output: data.output,
            plan: data.output?.plan || []
          }
        };
      }

      if (step.includes('aggregate') || step === 'aggregate_results') {
        return {
          step_type: 'response',
          content: 'Results aggregated into final answer',
          timestamp,
          status: 'completed',
          metadata: {
            step: data.step,
            output: data.output
          }
        };
      }

      // Regular step completion
      return {
        step_type: 'step_complete',
        content: `Completed: ${data.step || 'Unknown step'}`,
        timestamp,
        status: 'completed',
        metadata: {
          step: data.step,
          output: data.output
        }
      };

    case 'tool_call':
      return {
        step_type: 'tool_call',
        content: `Calling tool: ${data.tool || 'Unknown'}`,
        timestamp,
        status: 'running',
        metadata: {
          tool: data.tool,
          tool_name: data.tool,
          args: data.args
        }
      };

    case 'tool_result':
      return {
        step_type: 'tool_result',
        content: `Tool ${data.tool || 'Unknown'} completed`,
        timestamp,
        status: 'completed',
        metadata: {
          tool: data.tool,
          tool_name: data.tool,
          output: data.output
        }
      };

    case 'llm_call':
      return {
        step_type: 'llm_call',
        content: 'AI is thinking...',
        timestamp,
        status: 'running',
        metadata: {
          prompt: data.prompt
        }
      };

    case 'llm_response':
      return {
        step_type: 'llm_response',
        content: 'AI response received',
        timestamp,
        status: 'completed',
        metadata: {
          response: data.response,
          output: data.response
        }
      };

    case 'error':
      return {
        step_type: 'response',
        content: `Error: ${data.error || 'Unknown error'}`,
        timestamp,
        status: 'error',
        metadata: {
          error_message: data.error,
          error_type: data.type
        }
      };

    case 'done':
      return {
        step_type: 'response',
        content: 'Execution completed successfully',
        timestamp,
        status: 'completed',
        metadata: {
          result: data.result,
          execution_id: data.execution_id
        }
      };

    default:
      return null;
  }
}

/**
 * Connect to LangGraph SSE endpoint and process events
 */
export function connectToLangGraphStream(
  teamId: string,
  query: string,
  onStep: (step: AgentStep) => void,
  onError: (error: string) => void,
  onComplete: () => void,
  contextSourceIds?: string[],
  notebookId?: string
): EventSource {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5055';
  const url = `${baseUrl}/api/agents/teams/${teamId}/execute/stream`;

  // Create EventSource (note: native EventSource doesn't support POST, need to use fetch with streaming)
  // For now, we'll use a workaround with fetch
  const controller = new AbortController();

  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream'
    },
    body: JSON.stringify({
      query,
      context_source_ids: contextSourceIds,
      notebook_id: notebookId
    }),
    signal: controller.signal
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          onComplete();
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || ''; // Keep incomplete message in buffer

        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            // Parse SSE format: "event: <type>\ndata: <json>"
            const eventMatch = line.match(/event:\s*(\w+)/);
            const dataMatch = line.match(/data:\s*(\{.*\})/s);

            if (eventMatch && dataMatch) {
              const eventType = eventMatch[1];
              const eventData = JSON.parse(dataMatch[1]);

              const event: LangGraphEvent = {
                event: eventType as any,
                data: eventData
              };

              const step = convertLangGraphEventToStep(event);
              if (step) {
                onStep(step);
              }

              // Check for completion or error
              if (eventType === 'done') {
                onComplete();
                break;
              } else if (eventType === 'error') {
                onError(eventData.error || 'Unknown error');
                break;
              }
            }
          } catch (e) {
            console.error('Error parsing SSE message:', e, line);
          }
        }
      }
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        console.error('Stream error:', error);
        onError(error.message);
      }
    });

  // Return EventSource-like object with close method
  return {
    close: () => controller.abort(),
    onerror: null,
    onmessage: null,
    onopen: null,
    readyState: 0,
    url,
    withCredentials: false,
    CONNECTING: 0,
    OPEN: 1,
    CLOSED: 2,
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false
  } as EventSource;
}
