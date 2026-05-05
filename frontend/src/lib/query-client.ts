import { QueryClient } from "@tanstack/react-query";

/**
 * TanStack Query client configuration for Open Notebook
 *
 * Settings:
 * - 5 minute stale time: Data considered fresh for 5 minutes before refetching
 * - 10 minute GC time: Inactive data kept in cache for 10 minutes
 * - No automatic retries: Let user explicitly retry failed requests
 * - No automatic refetch on window focus: Prevent unnecessary API calls
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
      retry: false, // Don't retry failed requests automatically
      refetchOnWindowFocus: false, // Don't refetch when window regains focus
      refetchOnReconnect: true, // Refetch when network reconnects
    },
    mutations: {
      retry: false, // Don't retry failed mutations
    },
  },
});

/**
 * Query keys for organized cache management
 * Use these constants for consistent query invalidation and refetching
 */
export const queryKeys = {
  // Notebooks
  notebooks: ["notebooks"] as const,
  notebook: (id: string) => ["notebooks", id] as const,
  notebookSources: (id: string) => ["notebooks", id, "sources"] as const,
  notebookNotes: (id: string) => ["notebooks", id, "notes"] as const,
  notebookChats: (id: string) => ["notebooks", id, "chats"] as const,

  // Sources
  sources: ["sources"] as const,
  source: (id: string) => ["sources", id] as const,
  sourcesByType: (type: string) => ["sources", "type", type] as const,
  sourcesByNotebook: (notebookId: string) =>
    ["sources", "notebook", notebookId] as const,

  // Search
  search: (query: string, strategy: string, filters: any) =>
    ["search", { query, strategy, filters }] as const,
  searchConfig: ["search", "config"] as const,
  searchStrategies: ["search", "strategies"] as const,

  // Chat
  chatSessions: ["chat", "sessions"] as const,
  chatSession: (id: string) => ["chat", "sessions", id] as const,
  chatSessionsByNotebook: (notebookId: string) =>
    ["chat", "sessions", "notebook", notebookId] as const,

  // Database
  databaseConfig: ["database", "config"] as const,
  databaseStatus: ["database", "status"] as const,

  // Models & Credentials
  models: ["models"] as const,
  modelsByType: (type: string) => ["models", "type", type] as const,
  availableModels: ["models", "available"] as const,
  modelDefaults: ["models", "defaults"] as const,
  modelUsage: ["models", "usage"] as const,
  credentials: ["credentials"] as const,
  credential: (id: string) => ["credentials", id] as const,
  embeddingConfig: ["embedding", "config"] as const,

  // Folders & Tags
  folders: ["folders"] as const,
  folderTree: (id?: string) =>
    id ? ["folders", id, "tree"] : ["folders", "tree"] as const,
  tags: ["tags"] as const,
  tag: (id: string) => ["tags", id] as const,
  tagNotebooks: (id: string) => ["tags", id, "notebooks"] as const,

  // Microsites
  micrositeTemplates: ["microsites", "templates"] as const,
  micrositeTemplate: (id: string) => ["microsites", "templates", id] as const,
  micrositeContent: (id: string) => ["microsites", id, "content"] as const,
  micrositeVersions: (id: string) => ["microsites", id, "versions"] as const,
  micrositeModeration: (id: string) => ["microsites", id, "moderation"] as const,
  micrositeModerationHistory: (id: string) =>
    ["microsites", id, "moderation-history"] as const,

  // Tools
  tools: ["tools"] as const,
  tool: (id: string) => ["tools", id] as const,
  toolsByCategory: (category: string) => ["tools", "category", category] as const,
  toolPermissions: (toolId: string) => ["tools", toolId, "permissions"] as const,
  toolUsage: (toolId: string) => ["tools", toolId, "usage"] as const,

  // Agents
  agentTeams: ["agents", "teams"] as const,
  agentTeam: (id: string) => ["agents", "teams", id] as const,
  agents: ["agents"] as const,
  agent: (id: string) => ["agents", id] as const,
  agentsByTeam: (teamId: string) => ["agents", "team", teamId] as const,
  teamExecutions: (teamId: string) => ["agents", "teams", teamId, "executions"] as const,
  execution: (id: string) => ["agents", "executions", id] as const,
  teamTasks: (teamId: string) => ["agents", "teams", teamId, "tasks"] as const,
  teamMessages: (teamId: string) => ["agents", "teams", teamId, "messages"] as const,

  // Memory
  memories: ["memory"] as const,
  memory: (id: string) => ["memory", id] as const,
  memoriesByType: (type: string) => ["memory", "type", type] as const,
  memorySearch: (query: string) => ["memory", "search", query] as const,
  memoryStats: ["memory", "stats"] as const,
  memoryTags: ["memory", "tags"] as const,

  // Agent Prompts
  promptTemplates: ["agents", "prompts", "templates"] as const,
  promptTemplate: (role: string) => ["agents", "prompts", "templates", role] as const,
  agentPrompt: (agentId: string) => ["agents", agentId, "prompt"] as const,

  // User Query Prompts
  userQueryPrompts: ["user-query-prompts"] as const,
  userQueryPrompt: (id: string) => ["user-query-prompts", id] as const,
  userQueryPromptsByTeam: (teamId: string) => ["user-query-prompts", "team", teamId] as const,
  userQueryPromptsByCategory: (category: string) => ["user-query-prompts", "category", category] as const,
  userQueryPromptsFavorites: ["user-query-prompts", "favorites"] as const,

  // Standalone Agents
  standaloneAgents: ["standalone-agents"] as const,
  standaloneAgent: (id: string) => ["standalone-agents", id] as const,
  standaloneAgentsByNotebook: (notebookId: string) => ["standalone-agents", "notebook", notebookId] as const,
  standaloneAgentsByRole: (role: string) => ["standalone-agents", "role", role] as const,
  standaloneAgentExecutions: (agentId: string) => ["standalone-agents", agentId, "executions"] as const,
  standaloneAgentExecution: (executionId: string) => ["standalone-agents", "executions", executionId] as const,

  // Bookmarks
  bookmarks: ["bookmarks"] as const,
  bookmark: (id: string) => ["bookmarks", id] as const,
  bookmarkCheck: (type: string, id: string) => ["bookmarks", "check", type, id] as const,

  // Guided Workspace / Draft Sessions
  draftSessions: ["draft-sessions"] as const,
} as const;
