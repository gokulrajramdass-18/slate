import { apiClient } from "./client";
import type {
  ChatSession,
  ChatMessage,
  ChatSessionCreate,
  ChatMessageCreate,
  AgentStep,
} from "@/lib/types";

export const chatApi = {
  // List chat sessions
  list: async (notebookId?: string): Promise<ChatSession[]> => {
    const params = notebookId ? { notebook_id: notebookId } : undefined;
    const { data } = await apiClient.get("/chat/sessions", { params });
    return data;
  },

  // Get chat session with messages
  get: async (sessionId: string): Promise<ChatSession & { messages: ChatMessage[] }> => {
    const { data } = await apiClient.get(`/chat/sessions/${sessionId}`);
    // Backend returns { session: {...}, messages: [...] }
    // Transform to flat structure with messages included
    return {
      ...data.session,
      messages: data.messages || []
    };
  },

  // Create chat session
  create: async (session: ChatSessionCreate): Promise<ChatSession> => {
    const { data } = await apiClient.post("/chat/sessions", session);
    return data;
  },

  // Update chat session (title, model)
  update: async (
    sessionId: string,
    updates: Partial<ChatSession>
  ): Promise<ChatSession> => {
    const { data } = await apiClient.put(`/chat/sessions/${sessionId}`, updates);
    return data;
  },

  // Delete chat session
  delete: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/chat/sessions/${sessionId}`);
  },

  // Send message (with streaming support)
  sendMessage: async (
    sessionId: string,
    message: ChatMessageCreate,
    onChunk?: (chunk: string) => void,
    onMetadata?: (metadata: any) => void,
    onUIComponents?: (components: any[]) => void,
    onToolResults?: (results: any[]) => void,
    onAgentStep?: (step: AgentStep) => void
  ): Promise<ChatMessage> => {
    if (onChunk) {
      // Streaming mode with SSE

      // Get user ID from auth store
      const { user } = (await import("@/lib/stores/auth-store")).useAuthStore.getState();
      const userId = user?.id;

      // Track abort controller for cleanup
      const abortController = new AbortController();

      // Cleanup function
      const cleanup = () => {
        try {
          if (!abortController.signal.aborted) {
            abortController.abort();
          }
        } catch (e) {
          // Ignore abort errors during cleanup
          console.log("[Chat API] Cleanup completed");
        }
      };

      // Handle page visibility change (refresh, tab switch)
      // Only abort if the page is being unloaded (refresh/close)
      const handleBeforeUnload = () => {
        cleanup();
      };

      // Use beforeunload instead of visibilitychange to avoid false positives
      window.addEventListener('beforeunload', handleBeforeUnload);

      try {
        // Ensure we have a baseURL - use 127.0.0.1 for better browser compatibility
        const baseURL = apiClient.defaults.baseURL || 'http://127.0.0.1:5055/api';
        const url = `${baseURL}/chat/sessions/${sessionId}/messages`;
        const authHeader = apiClient.defaults.headers.Authorization as string;

        let response;
        try {
          response = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Cache-Control": "no-cache",
              "Connection": "keep-alive",
              ...(authHeader ? { Authorization: authHeader } : {}),
              ...(userId ? { 'X-User-ID': userId } : {}),
            },
            body: JSON.stringify({ ...message, stream: true }),
            signal: abortController.signal, // Add abort signal
            // @ts-ignore - Add cache: 'no-store' to prevent buffering
            cache: 'no-store'
          });
        } catch (fetchError) {
          // Serialize error properly for logging
          const errorDetails = {
            name: fetchError instanceof Error ? fetchError.name : 'Unknown',
            message: fetchError instanceof Error ? fetchError.message : String(fetchError),
            isAbortError: (fetchError as any)?.name === 'AbortError',
          };

          // Throw with more context
          if (errorDetails.isAbortError) {
            throw new Error(`Request was aborted`);
          }
          throw new Error(`Chat API fetch failed: ${errorDetails.message || 'Unknown error'}`);
        }

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Request failed: ${response.status} - ${errorText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("No response body reader");
        }

        const decoder = new TextDecoder();
        let fullMessage = "";
        let sources: any[] = [];
        let uiComponents: any[] = [];
        let toolResults: any[] = [];

        let buffer = "";
        let currentEvent = "";
        let dataBuffer = "";

        try {
          while (true) {
            // Check if aborted
            if (abortController.signal.aborted) {
              reader.cancel();
              break;
            }

            const { done, value } = await reader.read();

            if (done) {
              break;
            }

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");

          // Keep last incomplete line in buffer
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmedLine = line.trim();

            // Skip completely empty lines when we don't have pending data
            if (!trimmedLine && !currentEvent && !dataBuffer) {
              continue;
            }

            if (trimmedLine.startsWith("event:")) {
              // New event - reset everything
              currentEvent = trimmedLine.slice(6).trim();
              dataBuffer = "";
            } else if (trimmedLine.startsWith("data:")) {
              // Accumulate data lines (remove "data:" prefix)
              const dataChunk = trimmedLine.slice(5).trim();
              // Only accumulate non-empty data
              if (dataChunk) {
                dataBuffer += dataChunk;
              }
            } else if (trimmedLine === "") {
              // Blank line = end of SSE message
              // Only process if we have both event and data (and data is not empty)
              if (currentEvent && dataBuffer && dataBuffer.length > 0) {
                try {
                  const data = JSON.parse(dataBuffer);

                  // Skip empty objects - they're meaningless events
                  if (Object.keys(data).length === 0) {
                    currentEvent = "";
                    dataBuffer = "";
                    continue;
                  }

                  // Process events
                  if (currentEvent === "chunk") {
                    if (data.content) {
                      fullMessage += data.content;
                      // Dispatch custom event for immediate DOM update
                      console.log(`[Chat API ${performance.now().toFixed(0)}ms] CHUNK len=${data.content.length} preview="${data.content.substring(0, 30)}"`);
                      window.dispatchEvent(new CustomEvent('streaming:chunk', {
                        detail: { sessionId, content: data.content }
                      }));
                      // Also call callback for React state (will be batched)
                      onChunk(data.content);
                    }
                  } else if (currentEvent === "agent_step") {
                    if (onAgentStep) {
                      // Dispatch custom event for immediate DOM update
                      console.log(`[Chat API ${performance.now().toFixed(0)}ms] AGENT_STEP type=${data.step_type} status=${data.status}`);
                      window.dispatchEvent(new CustomEvent('streaming:agent_step', {
                        detail: { sessionId, step: data }
                      }));
                      // Also call callback for React state (will be batched)
                      onAgentStep(data);
                    }
                  } else if (currentEvent === "ui_components") {
                    uiComponents = data.components || [];
                    onUIComponents?.(uiComponents);
                  } else if (currentEvent === "tool_results") {
                    toolResults = data.results || [];
                    onToolResults?.(toolResults);
                  } else if (currentEvent === "done") {
                    // Stream complete - return with sources from done event
                    return {
                      id: data.message_id,
                      session_id: sessionId,
                      role: "assistant",
                      content: fullMessage,
                      created: new Date().toISOString(),
                      sources: data.sources || sources,
                      ui_components: uiComponents.length > 0 ? JSON.stringify(uiComponents) : undefined,
                      tool_results: toolResults.length > 0 ? JSON.stringify(toolResults) : undefined,
                    };
                  } else if (currentEvent === "metadata") {
                    // Handle metadata event - stream sources immediately to UI
                    if (data && typeof data === 'object' && data.context_info?.sources) {
                      sources = data.context_info.sources;
                      // Stream sources to the UI immediately via metadata callback
                      if (onMetadata) {
                        onMetadata({
                          ...data,
                          sources: sources // Ensure sources are in the metadata
                        });
                      }
                    } else if (onMetadata) {
                      // Always call metadata callback if provided
                      onMetadata(data);
                    }
                  } else if (currentEvent === "error") {
                    throw new Error(data.error || "Unknown error");
                  }

                  // Reset for next message
                  currentEvent = "";
                  dataBuffer = "";
                } catch (e) {
                  // Suppress errors for empty or very short buffers (likely innocuous)
                  if (dataBuffer.length > 2) { // More than just "{}" or "[]"
                    console.warn("SSE parse warning:", {
                      event: currentEvent,
                      dataBuffer: dataBuffer.substring(0, 200),
                      dataBufferLength: dataBuffer.length,
                      errorMessage: e instanceof Error ? e.message : String(e),
                    });
                  }
                  // Always reset on error to prevent stuck state
                  currentEvent = "";
                  dataBuffer = "";
                }
              } else {
                // Blank line with no pending data - just a separator, reset state
                currentEvent = "";
                dataBuffer = "";
              }
            }
            }
          }
        } catch (error) {
          // Handle abort errors gracefully
          if (error instanceof Error && error.name === 'AbortError') {
            throw new Error("Stream cancelled");
          }
          throw error;
        } finally {
          // Cleanup
          window.removeEventListener('beforeunload', handleBeforeUnload);
        }

        // Fallback return
        return {
          id: "",
          session_id: sessionId,
          role: "assistant",
          content: fullMessage,
          created: new Date().toISOString(),
          sources,
          ui_components: uiComponents.length > 0 ? JSON.stringify(uiComponents) : undefined,
          tool_results: toolResults.length > 0 ? JSON.stringify(toolResults) : undefined,
        };
      } catch (error) {
        // Handle abort errors gracefully - don't show to user
        if (error instanceof Error && (error.name === 'AbortError' || error.message === 'Stream cancelled')) {
          // Return empty result for aborted streams
          return {
            id: "",
            session_id: sessionId,
            role: "assistant",
            content: "",
            created: new Date().toISOString(),
          };
        }
        throw error;
      }
    }

    // Non-streaming
    const { data } = await apiClient.post(
      `/chat/sessions/${sessionId}/messages`,
      message
    );
    return data;
  },

  // Get deep research job status for a session
  getDeepResearchStatus: async (sessionId: string): Promise<{
    status: string;
    jobs: any[];
    latest: any | null;
  }> => {
    const { data } = await apiClient.get(
      `/chat/sessions/${sessionId}/deep-research-status`
    );
    return data;
  },

  // Detect microsite generation intent in a message
  detectMicrositeIntent: async (
    sessionId: string,
    message: string
  ): Promise<{
    is_match: boolean;
    template_hint?: string;
    workspace_hint?: string;
    action?: string;
  }> => {
    const { data } = await apiClient.post(
      `/chat/sessions/${sessionId}/detect-microsite-intent`,
      { message, stream: false, include_context: false }
    );
    return data;
  },

  // Trigger microsite generation from chat with SSE progress streaming
  streamMicrositeGenerate: async (
    sessionId: string,
    params: {
      micrositeId: string;
      templateId: string;
      sourceIds: string[];
      userPrompt?: string;
    },
    onProgress?: (data: { phase: string; progress: number; message: string }) => void,
    onModeration?: (report: any) => void,
    onDone?: (result: { microsite_id: string; version: number; preview_url: string }) => void,
    onError?: (error: string) => void
  ): Promise<void> => {
    const queryParams = new URLSearchParams({
      microsite_id: params.micrositeId,
      template_id: params.templateId,
    });
    params.sourceIds.forEach((id) => queryParams.append("source_ids", id));
    if (params.userPrompt) {
      queryParams.append("user_prompt", params.userPrompt);
    }

    const response = await fetch(
      `${apiClient.defaults.baseURL}/chat/sessions/${sessionId}/microsite-generate?${queryParams}`,
      {
        method: "POST",
        headers: {
          Authorization: apiClient.defaults.headers.Authorization as string,
        },
      }
    );

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      onError?.("No response stream");
      return;
    }

    let buffer = "";
    let currentEvent = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));

            if (currentEvent === "progress") {
              onProgress?.(data);
            } else if (currentEvent === "moderation") {
              onModeration?.(data);
            } else if (currentEvent === "done") {
              onDone?.(data);
            } else if (currentEvent === "error") {
              onError?.(data.error || "Generation failed");
            }

            currentEvent = "";
          } catch {
            // Skip malformed data
          }
        }
      }
    }
  },
};
