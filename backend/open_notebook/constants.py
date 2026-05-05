"""
Constants for user management and RBAC system.
"""

# Resource Types
RESOURCE_WORKSPACE = "workspace"
RESOURCE_SOURCE = "source"
RESOURCE_CHAT_SESSION = "chat_session"
RESOURCE_AGENT = "agent"
RESOURCE_AGENT_TEAM = "agent_team"
RESOURCE_TOOL = "tool"
RESOURCE_MCP_SERVER = "mcp_server"
RESOURCE_HANA_CONNECTION = "hana_connection"
RESOURCE_API_CONNECTION = "api_connection"
RESOURCE_MICROSITE = "microsite"
RESOURCE_WORKFLOW = "workflow"
RESOURCE_BOOKMARK = "bookmark"
RESOURCE_QUERY_PROMPT = "query_prompt"
RESOURCE_USER = "user"
RESOURCE_ROLE = "role"

# Actions
ACTION_CREATE = "create"
ACTION_READ = "read"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_EXECUTE = "execute"
ACTION_SHARE = "share"
ACTION_PUBLISH = "publish"

# Scopes
SCOPE_OWN = "own"
SCOPE_TEAM = "team"
SCOPE_ALL = "all"

# User Status
USER_STATUS_ACTIVE = "active"
USER_STATUS_SUSPENDED = "suspended"
USER_STATUS_DELETED = "deleted"

# Permission Levels (for resource sharing)
PERMISSION_READ = "read"
PERMISSION_WRITE = "write"
PERMISSION_ADMIN = "admin"

# Map resource types to display names
RESOURCE_DISPLAY_NAMES = {
    RESOURCE_WORKSPACE: "Workspace",
    RESOURCE_SOURCE: "Source",
    RESOURCE_CHAT_SESSION: "Chat Session",
    RESOURCE_AGENT: "Agent",
    RESOURCE_AGENT_TEAM: "Agent Team",
    RESOURCE_TOOL: "Tool",
    RESOURCE_MCP_SERVER: "MCP Server",
    RESOURCE_HANA_CONNECTION: "HANA Connection",
    RESOURCE_API_CONNECTION: "API Connection",
    RESOURCE_MICROSITE: "Microsite",
    RESOURCE_WORKFLOW: "Workflow",
    RESOURCE_BOOKMARK: "Bookmark",
    RESOURCE_QUERY_PROMPT: "Query Prompt",
    RESOURCE_USER: "User",
    RESOURCE_ROLE: "Role",
}

# Map actions to display names
ACTION_DISPLAY_NAMES = {
    ACTION_CREATE: "Create",
    ACTION_READ: "View",
    ACTION_UPDATE: "Edit",
    ACTION_DELETE: "Delete",
    ACTION_EXECUTE: "Execute",
    ACTION_SHARE: "Share",
    ACTION_PUBLISH: "Publish",
}

# Map scopes to display names
SCOPE_DISPLAY_NAMES = {
    SCOPE_OWN: "Own Resources Only",
    SCOPE_TEAM: "Team Resources",
    SCOPE_ALL: "All Resources",
}
