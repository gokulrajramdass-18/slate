import { apiClient } from "./client";
import type {
  SearchRequest,
  SearchResult,
  SearchConfig,
  SearchStrategy,
  AgenticRAGStep,
  UnifiedSearchRequest,
  UnifiedSearchResult,
} from "@/lib/types";

export const searchApi = {
  // Perform search
  search: async (request: SearchRequest): Promise<SearchResult[]> => {
    const { data } = await apiClient.post("/search/", request);
    // Backend returns { results: [...], ... } but we just want the results array
    return data.results || data;
  },

  // Unified search (combines main search + bookmarks)
  unifiedSearch: async (request: UnifiedSearchRequest): Promise<{
    query: string;
    strategy: string;
    total_results: number;
    results: UnifiedSearchResult[];
    sources: { main_search: number; bookmarks: number };
    metadata: any;
  }> => {
    const { data } = await apiClient.post("/search/unified", request);
    return data;
  },

  // Agentic RAG search (with streaming)
  agenticRAG: async (
    query: string,
    filters?: any,
    onStep?: (step: AgenticRAGStep) => void
  ): Promise<{
    answer: string;
    steps: AgenticRAGStep[];
    sources: SearchResult[];
  }> => {
    // If streaming callback provided, use SSE
    if (onStep) {
      const response = await fetch(
        `${apiClient.defaults.baseURL}/search/agentic-rag`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: apiClient.defaults.headers.Authorization as string,
          },
          body: JSON.stringify({ query, filters }),
        }
      );

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let result = { answer: "", steps: [], sources: [] };

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = JSON.parse(line.slice(6));
              if (data.type === "step") {
                onStep(data.step);
              } else if (data.type === "complete") {
                result = data.result;
              }
            }
          }
        }
      }

      return result;
    }

    // Non-streaming
    const { data } = await apiClient.post("/search/agentic-rag", {
      query,
      filters,
    });
    return data;
  },

  // Get available strategies
  getStrategies: async (): Promise<
    Array<{
      name: SearchStrategy;
      display_name: string;
      description: string;
      config_schema?: any;
    }>
  > => {
    const { data } = await apiClient.get("/search/strategies");
    return data;
  },

  // Get search configuration
  getConfig: async (): Promise<SearchConfig> => {
    const { data } = await apiClient.get("/search/config");
    return data;
  },

  // Update search configuration
  updateConfig: async (config: Partial<SearchConfig>): Promise<SearchConfig> => {
    const { data } = await apiClient.put("/search/config", config);
    return data;
  },

  // Test search strategy
  testStrategy: async (
    strategy: SearchStrategy,
    query: string,
    config?: any
  ): Promise<{
    success: boolean;
    results: SearchResult[];
    performance: { duration_ms: number };
  }> => {
    const { data } = await apiClient.post("/search/config/test", {
      strategy,
      query,
      config,
    });
    return data;
  },
};
