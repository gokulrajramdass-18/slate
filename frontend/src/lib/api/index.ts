/**
 * Centralized API client exports
 * Import from this file for consistent access to all API functions
 *
 * Example usage:
 * import { workspacesApi, searchApi } from "@/lib/api";
 */

export { apiClient, uploadConfig } from "./client";
export { workspacesApi } from "./workspaces";
export { sourcesApi } from "./sources";
export { searchApi } from "./search";
export { chatApi } from "./chat";
export { databaseApi } from "./database";
export { modelsApi, credentialsApi, embeddingApi } from "./models";
export { foldersApi, tagsApi } from "./folders-tags";
export { micrositesApi } from "./microsites";
export { toolsApi } from "./tools";
export { agentsApi } from "./agents";
export { memoryApi } from "./memory";
export { mcpServersApi } from "./mcp-servers";
export { agentSkillsApi } from "./agent-skills";
export { promptsApi } from "./agent-prompts";
export { bookmarksApi } from "./bookmarks";
export { graphApi } from "./graph";
export { notesApi, downloadBlob } from "./notes";
