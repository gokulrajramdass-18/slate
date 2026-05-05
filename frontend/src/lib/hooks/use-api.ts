/**
 * Custom React Query hooks for Open Notebook API
 *
 * These hooks provide type-safe, optimistic UI updates, and automatic
 * cache invalidation for all API operations.
 *
 * Example usage:
 * ```tsx
 * const { data: notebooks, isLoading } = useNotebooks();
 * const createMutation = useCreateNotebook();
 * createMutation.mutate({ name: "My Notebook" });
 * ```
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  workspacesApi,
  sourcesApi,
  searchApi,
  chatApi,
  databaseApi,
  modelsApi,
  credentialsApi,
  embeddingApi,
  foldersApi,
  tagsApi,
  micrositesApi,
  toolsApi,
  agentsApi,
  memoryApi,
  bookmarksApi,
} from "@/lib/api";
import { listSessions, deleteSession } from "@/lib/api/guided-workspace";
import { queryKeys } from "@/lib/query-client";
import type {
  Notebook,
  NotebookCreate,
  Source,
  SourceCreate,
  SearchRequest,
  ChatSessionCreate,
  ChatMessageCreate,
  DatabaseConfig,
  MicrositeGenerateRequest,
  MicrositeContentUpdate,
  ToolCreate,
  ToolUpdate,
  PermissionCreate,
  PermissionUpdate,
  TeamCreateRequest,
  MemoryCreate,
  MemoryUpdate,
  MemorySearchRequest,
  MemoryType,
  BookmarkCreate,
  BookmarkUpdate,
} from "@/lib/types";

// ============================================================================
// NOTEBOOKS
// ============================================================================

export function useNotebooks(params?: {
  folder_id?: string;
  archived?: boolean;
  tags?: string[];
}) {
  return useQuery({
    queryKey: [...queryKeys.notebooks, params],
    queryFn: () => workspacesApi.list(params),
    staleTime: 2 * 60 * 1000,  // 2 minutes - data considered fresh
    gcTime: 15 * 60 * 1000,    // 15 minutes - keep in cache
    refetchInterval: false,     // Don't auto-refetch
    refetchOnWindowFocus: false, // Don't refetch on tab switch
  });
}

export function useNotebook(id: string) {
  return useQuery({
    queryKey: queryKeys.notebook(id),
    queryFn: () => workspacesApi.get(id),
    enabled: !!id,
  });
}

export function useCreateNotebook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (notebook: NotebookCreate) => workspacesApi.create(notebook),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notebooks });
    },
  });
}

export function useUpdateNotebook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Notebook> }) =>
      workspacesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notebook(variables.id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.notebooks });
    },
  });
}

export function useDeleteNotebook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workspacesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notebooks });
    },
  });
}

export function useDuplicateNotebook() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => workspacesApi.duplicate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.notebooks });
    },
  });
}

export function useNotebookSources(notebookId: string) {
  return useQuery({
    queryKey: queryKeys.notebookSources(notebookId),
    queryFn: () => workspacesApi.getSources(notebookId),
    enabled: !!notebookId,
  });
}

export function useNotebookNotes(notebookId: string) {
  return useQuery({
    queryKey: queryKeys.notebookNotes(notebookId),
    queryFn: () => workspacesApi.getNotes(notebookId),
    enabled: !!notebookId,
  });
}

export function useNotebookChatSessions(notebookId: string) {
  return useQuery({
    queryKey: queryKeys.notebookChats(notebookId),
    queryFn: () => workspacesApi.getChatSessions(notebookId),
    enabled: !!notebookId,
  });
}

// ============================================================================
// SOURCES
// ============================================================================

export function useSources(params?: {
  source_type?: string;
  notebook_id?: string;
}) {
  return useQuery({
    queryKey: [...queryKeys.sources, params],
    queryFn: () => sourcesApi.list(params),
    refetchInterval: (query) => {
      // Auto-refetch every 3 seconds if any source has active embedding/sync status
      const data = query.state.data as any[];
      if (data?.some((s) => s.sync_status === "embedding" || s.sync_status === "syncing")) {
        return 3000; // 3 seconds
      }
      return false; // Don't auto-refetch otherwise
    },
  });
}

export function useSource(id: string) {
  return useQuery({
    queryKey: queryKeys.source(id),
    queryFn: () => sourcesApi.get(id),
    enabled: !!id,
  });
}

export function useCreateSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (source: SourceCreate) => sourcesApi.create(source),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
  });
}

export function useUploadFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ file, title, notebookId }: { file: File; title?: string; notebookId?: string }) =>
      sourcesApi.uploadFile(file, title, notebookId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
  });
}

export function useUpdateSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Source> }) =>
      sourcesApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.source(variables.id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
  });
}

export function useDeleteSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => sourcesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.sources });
    },
  });
}

export function useSyncSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => sourcesApi.sync(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.source(id) });
    },
  });
}

// ============================================================================
// SEARCH
// ============================================================================

export function useSearch(request: SearchRequest, enabled: boolean = false) {
  return useQuery({
    queryKey: queryKeys.search(
      request.query,
      request.strategy || "hybrid",
      request.filters || {}
    ),
    queryFn: () => searchApi.search(request),
    enabled: enabled && !!request.query,
  });
}

export function useSearchStrategies() {
  return useQuery({
    queryKey: queryKeys.searchStrategies,
    queryFn: () => searchApi.getStrategies(),
  });
}

export function useSearchConfig() {
  return useQuery({
    queryKey: queryKeys.searchConfig,
    queryFn: () => searchApi.getConfig(),
  });
}

export function useUpdateSearchConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (config: any) => searchApi.updateConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.searchConfig });
    },
  });
}

// ============================================================================
// CHAT
// ============================================================================

export function useChatSessions(notebookId?: string) {
  return useQuery({
    queryKey: notebookId
      ? queryKeys.chatSessionsByNotebook(notebookId)
      : queryKeys.chatSessions,
    queryFn: () => chatApi.list(notebookId),
  });
}

export function useChatSession(sessionId: string) {
  return useQuery({
    queryKey: queryKeys.chatSession(sessionId),
    queryFn: () => chatApi.get(sessionId),
    enabled: !!sessionId,
  });
}

export function useCreateChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (session: ChatSessionCreate) => chatApi.create(session),
    onSuccess: () => {
      // Invalidate all chat-related queries to refresh everywhere
      queryClient.invalidateQueries({ queryKey: ["chat"] }); // All chat queries
      queryClient.invalidateQueries({ queryKey: ["notebooks"], predicate: (query) => {
        // Invalidate notebook queries that include "chats" in their key
        return query.queryKey.includes("chats");
      }});
    },
  });
}

export function useUpdateChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ sessionId, updates }: { sessionId: string; updates: Partial<any> }) =>
      chatApi.update(sessionId, updates),
    onSuccess: (_, variables) => {
      // Invalidate the specific session and session list
      queryClient.invalidateQueries({ queryKey: queryKeys.chatSession(variables.sessionId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.chatSessions });
    },
  });
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sessionId: string) => chatApi.delete(sessionId),
    onSuccess: () => {
      // Invalidate all chat-related queries to refresh everywhere
      queryClient.invalidateQueries({ queryKey: ["chat"] }); // All chat queries
      queryClient.invalidateQueries({ queryKey: ["notebooks"], predicate: (query) => {
        // Invalidate notebook queries that include "chats" in their key
        return query.queryKey.includes("chats");
      }});
    },
  });
}

// ============================================================================
// DATABASE
// ============================================================================

export function useDatabaseConfig() {
  return useQuery({
    queryKey: queryKeys.databaseConfig,
    queryFn: () => databaseApi.getConfig(),
  });
}

export function useDatabaseStatus() {
  return useQuery({
    queryKey: queryKeys.databaseStatus,
    queryFn: () => databaseApi.getStatus(),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}

export function useTestDatabaseConnection() {
  return useMutation({
    mutationFn: (config: DatabaseConfig) => databaseApi.testConnection(config),
  });
}

export function useSwitchDatabase() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      targetType,
      config,
    }: {
      targetType: "sqlite" | "hana";
      config?: DatabaseConfig;
    }) => databaseApi.switch(targetType, config),
    onSuccess: () => {
      // Invalidate all queries after database switch
      queryClient.invalidateQueries();
    },
  });
}

// ============================================================================
// MODELS & CREDENTIALS
// ============================================================================

export function useModels(type?: "language" | "embedding" | "speech_to_text" | "text_to_speech") {
  return useQuery({
    queryKey: type ? queryKeys.modelsByType(type) : queryKeys.models,
    queryFn: () => modelsApi.list(type),
  });
}

export function useAvailableModels() {
  return useQuery({
    queryKey: queryKeys.availableModels,
    queryFn: () => modelsApi.available(),
  });
}

export function useModelDefaults() {
  return useQuery({
    queryKey: queryKeys.modelDefaults,
    queryFn: () => modelsApi.getDefaults(),
  });
}

export function useUpdateModelDefaults() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (defaults: any) => modelsApi.updateDefaults(defaults),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.modelDefaults });
    },
  });
}

export function useCredentials() {
  return useQuery({
    queryKey: queryKeys.credentials,
    queryFn: () => credentialsApi.list(),
  });
}

export function useCreateCredential() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (credential: any) => credentialsApi.create(credential),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credentials });
    },
  });
}

export function useDeleteCredential() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => credentialsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credentials });
    },
  });
}

export function useEmbeddingConfig() {
  return useQuery({
    queryKey: queryKeys.embeddingConfig,
    queryFn: () => embeddingApi.getConfig(),
  });
}

export function useUpdateEmbeddingConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (config: any) => embeddingApi.updateConfig(config),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.embeddingConfig });
    },
  });
}

// ============================================================================
// FOLDERS & TAGS
// ============================================================================

export function useFolders() {
  return useQuery({
    queryKey: queryKeys.folders,
    queryFn: () => foldersApi.list(),
  });
}

export function useFolderTree(folderId?: string) {
  return useQuery({
    queryKey: queryKeys.folderTree(folderId),
    queryFn: () => foldersApi.getTree(folderId),
  });
}

export function useCreateFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (folder: { name: string; parent_id?: string }) =>
      foldersApi.create(folder),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.folders });
    },
  });
}

export function useDeleteFolder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => foldersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.folders });
    },
  });
}

export function useTags() {
  return useQuery({
    queryKey: queryKeys.tags,
    queryFn: () => tagsApi.list(),
  });
}

export function useCreateTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (tag: { name: string; color?: string }) => tagsApi.create(tag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tags });
    },
  });
}

export function useDeleteTag() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => tagsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tags });
    },
  });
}

// ============================================================================
// MICROSITES
// ============================================================================

export function useMicrositeTemplates(params?: {
  category?: string;
  is_custom?: boolean;
}) {
  return useQuery({
    queryKey: [...queryKeys.micrositeTemplates, params],
    queryFn: () => micrositesApi.listTemplates(params),
  });
}

export function useMicrositeTemplate(id: string) {
  return useQuery({
    queryKey: queryKeys.micrositeTemplate(id),
    queryFn: () => micrositesApi.getTemplate(id),
    enabled: !!id,
  });
}

export function useGenerateMicrosite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      micrositeId,
      request,
    }: {
      micrositeId: string;
      request: MicrositeGenerateRequest;
    }) => micrositesApi.generate(micrositeId, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.micrositeContent(variables.micrositeId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.micrositeVersions(variables.micrositeId),
      });
    },
  });
}

export function useMicrositeContent(micrositeId: string) {
  return useQuery({
    queryKey: queryKeys.micrositeContent(micrositeId),
    queryFn: () => micrositesApi.getContent(micrositeId),
    enabled: !!micrositeId,
  });
}

export function useUpdateMicrositeContent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      micrositeId,
      update,
    }: {
      micrositeId: string;
      update: MicrositeContentUpdate;
    }) => micrositesApi.updateContent(micrositeId, update),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.micrositeContent(variables.micrositeId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.micrositeVersions(variables.micrositeId),
      });
    },
  });
}

export function useModerateMicrosite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      micrositeId,
      sectionIds,
    }: {
      micrositeId: string;
      sectionIds?: string[];
    }) => micrositesApi.moderate(micrositeId, sectionIds),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.micrositeModeration(variables.micrositeId),
      });
    },
  });
}

export function useMicrositeVersions(micrositeId: string) {
  return useQuery({
    queryKey: queryKeys.micrositeVersions(micrositeId),
    queryFn: () => micrositesApi.listVersions(micrositeId),
    enabled: !!micrositeId,
  });
}

export function useRollbackMicrosite() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      micrositeId,
      versionNumber,
    }: {
      micrositeId: string;
      versionNumber: number;
    }) => micrositesApi.rollback(micrositeId, versionNumber),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.micrositeContent(variables.micrositeId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.micrositeVersions(variables.micrositeId),
      });
    },
  });
}

// ============================================================================
// TOOLS
// ============================================================================

export function useTools(params?: { category?: string; enabled?: boolean }) {
  return useQuery({
    queryKey: [...queryKeys.tools, params],
    queryFn: () => toolsApi.list(params),
  });
}

export function useTool(toolId: string) {
  return useQuery({
    queryKey: queryKeys.tool(toolId),
    queryFn: () => toolsApi.get(toolId),
    enabled: !!toolId,
  });
}

export function useCreateTool() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (tool: ToolCreate) => toolsApi.create(tool),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
    },
  });
}

export function useUpdateTool() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ToolUpdate }) =>
      toolsApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tool(variables.id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
    },
  });
}

export function useDeleteTool() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => toolsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
    },
  });
}

export function useToggleTool() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      toolsApi.toggle(id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tools });
    },
  });
}

export function useToolPermissions(toolId: string) {
  return useQuery({
    queryKey: queryKeys.toolPermissions(toolId),
    queryFn: () => toolsApi.listPermissions(toolId),
    enabled: !!toolId,
  });
}

export function useAddToolPermission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      toolId,
      perm,
    }: {
      toolId: string;
      perm: PermissionCreate;
    }) => toolsApi.addPermission(toolId, perm),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.toolPermissions(variables.toolId),
      });
    },
  });
}

export function useUpdateToolPermission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      permId,
      toolId,
      update,
    }: {
      permId: string;
      toolId: string;
      update: PermissionUpdate;
    }) => toolsApi.updatePermission(permId, update),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.toolPermissions(variables.toolId),
      });
    },
  });
}

export function useDeleteToolPermission() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ permId, toolId }: { permId: string; toolId: string }) =>
      toolsApi.deletePermission(permId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.toolPermissions(variables.toolId),
      });
    },
  });
}

export function useToolUsage(toolId: string, days: number = 7) {
  return useQuery({
    queryKey: queryKeys.toolUsage(toolId),
    queryFn: () => toolsApi.getUsage(toolId, days),
    enabled: !!toolId,
  });
}

// ============================================================================
// AGENT TEAMS
// ============================================================================

export function useAgentTeams() {
  return useQuery({
    queryKey: queryKeys.agentTeams,
    queryFn: () => agentsApi.listTeams(),
  });
}

export function useAgentTeam(teamId: string) {
  return useQuery({
    queryKey: queryKeys.agentTeam(teamId),
    queryFn: () => agentsApi.getTeam(teamId),
    enabled: !!teamId,
  });
}

export function useCreateAgentTeam() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: TeamCreateRequest) => agentsApi.createTeam(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agentTeams });
    },
  });
}

export function useDeleteAgentTeam() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (teamId: string) => agentsApi.deleteTeam(teamId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.agentTeams });
    },
  });
}

export function useAgents(teamId?: string) {
  return useQuery({
    queryKey: teamId ? queryKeys.agentsByTeam(teamId) : queryKeys.agents,
    queryFn: () => agentsApi.listAgents(teamId),
  });
}

export function useTeamExecutions(teamId: string) {
  return useQuery({
    queryKey: queryKeys.teamExecutions(teamId),
    queryFn: () => agentsApi.listExecutions(teamId),
    enabled: !!teamId,
  });
}

export function useExecution(executionId: string) {
  return useQuery({
    queryKey: queryKeys.execution(executionId),
    queryFn: () => agentsApi.getExecution(executionId),
    enabled: !!executionId,
    refetchInterval: (query) => {
      const data = query.state.data as any;
      if (data?.status === "executing" || data?.status === "planning") {
        return 2000;
      }
      return false;
    },
  });
}

export function useTeamTasks(teamId: string, executionId?: string) {
  return useQuery({
    queryKey: queryKeys.teamTasks(teamId),
    queryFn: () => agentsApi.listTasks(teamId, executionId),
    enabled: !!teamId,
  });
}

export function useTeamMessages(teamId: string, executionId?: string) {
  return useQuery({
    queryKey: queryKeys.teamMessages(teamId),
    queryFn: () => agentsApi.listMessages(teamId, executionId),
    enabled: !!teamId,
  });
}

// ============================================================================
// MEMORY
// ============================================================================

export function useMemories(params?: {
  memory_type?: MemoryType;
  tags?: string[];
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: [...queryKeys.memories, params],
    queryFn: () => memoryApi.list(params),
  });
}

export function useMemory(memoryId: string) {
  return useQuery({
    queryKey: queryKeys.memory(memoryId),
    queryFn: () => memoryApi.get(memoryId),
    enabled: !!memoryId,
  });
}

export function useCreateMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (memory: MemoryCreate) => memoryApi.create(memory),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.memories });
      queryClient.invalidateQueries({ queryKey: queryKeys.memoryStats });
    },
  });
}

export function useUpdateMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MemoryUpdate }) =>
      memoryApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.memory(variables.id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.memories });
    },
  });
}

export function useDeleteMemory() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (memoryId: string) => memoryApi.delete(memoryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.memories });
      queryClient.invalidateQueries({ queryKey: queryKeys.memoryStats });
    },
  });
}

export function useMemorySearch(request: MemorySearchRequest, enabled: boolean = false) {
  return useQuery({
    queryKey: queryKeys.memorySearch(request.query),
    queryFn: () => memoryApi.search(request),
    enabled: enabled && !!request.query,
  });
}

export function useMemoryStats() {
  return useQuery({
    queryKey: queryKeys.memoryStats,
    queryFn: () => memoryApi.getStats(),
  });
}

export function useMemoryTags() {
  return useQuery({
    queryKey: queryKeys.memoryTags,
    queryFn: () => memoryApi.getTags(),
  });
}

export function useClearExpiredMemories() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => memoryApi.clearExpired(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.memories });
      queryClient.invalidateQueries({ queryKey: queryKeys.memoryStats });
    },
  });
}

// ============================================================================
// BOOKMARKS
// ============================================================================

export function useBookmarks(params?: {
  entity_type?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: [...queryKeys.bookmarks, params],
    queryFn: () => bookmarksApi.list(params),
  });
}

export function useBookmark(id: string) {
  return useQuery({
    queryKey: queryKeys.bookmark(id),
    queryFn: () => bookmarksApi.get(id),
    enabled: !!id,
  });
}

export function useToggleBookmark() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: BookmarkCreate) => bookmarksApi.toggle(data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bookmarks });

      // Invalidate entity queries to update is_bookmarked flag
      if (variables.entity_type === "source") {
        queryClient.invalidateQueries({ queryKey: queryKeys.sources });
      } else if (variables.entity_type === "notebook") {
        queryClient.invalidateQueries({ queryKey: queryKeys.notebooks });
      }
    },
  });
}

export function useUpdateBookmark() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: BookmarkUpdate }) =>
      bookmarksApi.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bookmark(variables.id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bookmarks });
    },
  });
}

export function useDeleteBookmark() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => bookmarksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bookmarks });
    },
  });
}

// ============================================================================
// DRAFT WORKSPACE SESSIONS
// ============================================================================

export function useDraftSessions() {
  return useQuery({
    queryKey: queryKeys.draftSessions,
    queryFn: () => listSessions('draft'),
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useDeleteDraftSession() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.draftSessions });
    },
  });
}
