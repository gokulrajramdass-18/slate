"""
Chat Router

Handles chat session management and message sending with streaming support.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, status, Query
from sse_starlette.sse import EventSourceResponse

from api.models import (
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    OrchestratedChatRequest,
    ErrorResponse,
    SuccessResponse
)
from api.services.context import get_context_service
from api.services.observability_service import get_observability_manager
from open_notebook.domain.chat import ChatSession, ChatMessage
from open_notebook.domain.notebook import Notebook
from open_notebook.agents.deep_research_agent import ResearchPhase


def make_user_friendly_error(error: Exception) -> str:
    """
    Convert technical errors into user-friendly messages.

    Args:
        error: The exception that occurred

    Returns:
        User-friendly error message
    """
    error_str = str(error)

    # Database errors
    if "FOREIGN KEY constraint failed" in error_str:
        return "Session not found. Please refresh the page and try again."
    elif "no such table" in error_str.lower():
        return "Database schema issue detected. Please contact support."
    elif "database is locked" in error_str.lower():
        return "Database is busy. Please try again in a moment."

    # Authentication errors
    elif "Jwt is expired" in error_str or "jwt" in error_str.lower():
        return "Authentication expired. Please check your API configuration."
    elif "Unauthorized" in error_str or "401" in error_str:
        return "Authentication failed. Please check your credentials."

    # Connection errors
    elif "Connection refused" in error_str:
        return "Cannot connect to AI service. Please check your configuration."
    elif "Connection reset" in error_str or "Connection aborted" in error_str:
        return "Connection lost. Please try again."
    elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
        return "Request timed out. The service may be overloaded. Please try again."

    # Rate limiting
    elif "rate limit" in error_str.lower() or "429" in error_str:
        return "Rate limit exceeded. Please wait a moment and try again."
    elif "quota" in error_str.lower():
        return "API quota exceeded. Please check your API plan."

    # Model/API errors
    elif "model not found" in error_str.lower() or "model_not_found" in error_str:
        return "AI model not found. Please select a different model in Settings."
    elif "invalid api key" in error_str.lower() or "api_key" in error_str.lower():
        return "Invalid API key. Please check your credentials in Settings."
    elif "context length" in error_str.lower() or "token" in error_str.lower():
        return "Message too long. Please try a shorter message or use fewer sources."

    # Generic HTTP errors
    elif "500" in error_str:
        return "Server error occurred. Please try again or contact support."
    elif "404" in error_str:
        return "Resource not found. Please refresh and try again."

    # Default: return original error but cleaned up
    return error_str[:200]  # Limit length

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_model_credential(model_name: str) -> Optional[Dict]:
    """
    Get credential for a model, handling SAP AI Core models specially.

    For SAP AI Core models, returns a synthetic credential using environment variables.
    For other models, looks up the credential in the store.

    Args:
        model_name: Model ID (e.g., "sap-ai-core-{deployment_id}" or credential ID)

    Returns:
        Credential dict or None if not found
    """
    from api.routers.credentials import _credentials_store

    # First try to get from credentials store
    credential = _credentials_store.get(model_name)

    # Check if this is a SAP AI Core model (either by name prefix or provider field)
    is_sap_ai_core = (
        (model_name and model_name.startswith("sap-ai-core-")) or
        (credential and credential.get("provider") == "sap_ai_core")
    )

    if is_sap_ai_core:
        # For SAP AI Core, return a synthetic credential
        # The actual authentication is handled by gen-ai-hub SDK via environment variables
        if model_name.startswith("sap-ai-core-"):
            deployment_id = model_name.replace("sap-ai-core-", "")
        else:
            # Extract deployment ID from credential model_name
            deployment_id = credential.get("model_name", model_name)

        # Return credential with sap-ai-core- prefix for agent detection
        return {
            "model_name": f"sap-ai-core-{deployment_id}",
            "provider": "sap_ai_core",
            "base_url": None,  # Not used for SAP AI Core
            "api_key": None,   # Not used for SAP AI Core (uses env vars)
            "deployment_id": deployment_id
        }

    # For other models, return the credential as-is
    return credential


# ============================================================================
# Chat Session Endpoints
# ============================================================================

@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(session_data: ChatSessionCreate):
    """
    Create a new chat session.

    If no notebook_id is provided, creates a default "General" notebook automatically.
    Requires at least one language model to be configured.

    Args:
        session_data: Chat session creation data

    Returns:
        Created chat session
    """
    # Check that a language model is configured
    from api.services.settings import get_setting

    language_model_id = await get_setting("language_model_id", "")
    if not language_model_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No language model configured. Please select a model in Settings → Models before creating a chat session."
        )

    notebook_id = session_data.notebook_id

    # If no notebook_id provided, create or find default notebook
    if not notebook_id:
        # Try to find existing "General" notebook
        from open_notebook.database.repository import repo_query
        result = await repo_query(
            "SELECT * FROM notebooks WHERE name = :name AND archived = :archived LIMIT 1",
            {"name": "General", "archived": False}
        )

        if result:
            notebook_id = result[0]["id"]
        else:
            # Create default notebook
            default_notebook = Notebook(
                name="General",
                description="Default notebook for chat sessions"
            )
            await default_notebook.save()
            notebook_id = default_notebook.id
    else:
        # Verify provided notebook exists
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook not found: {notebook_id}"
            )

    # Create session
    session = ChatSession(
        title=session_data.title,
        notebook_id=notebook_id,
        model_override=session_data.model_override,
    )
    await session.save()

    # Get message count
    msg_count = await session.get_message_count()

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        notebook_id=session.notebook_id,
        created=session.created,
        updated=session.updated,
        message_count=msg_count
    )


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    notebook_id: Optional[str] = Query(None, description="Filter by notebook ID"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List chat sessions.

    Args:
        notebook_id: Optional notebook ID filter
        limit: Maximum number of sessions to return

    Returns:
        List of chat sessions
    """
    if notebook_id:
        sessions = await ChatSession.get_by_notebook(notebook_id)
    else:
        from open_notebook.database.repository import repo_query
        results = await repo_query(
            "SELECT * FROM chat_sessions ORDER BY updated DESC LIMIT :limit",
            {"limit": limit}
        )
        sessions = [ChatSession(**row) for row in results]

    # Get message counts and workspace names for each session
    response_sessions = []
    for session in sessions:
        msg_count = await session.get_message_count()

        # Get workspace name if notebook_id exists
        workspace_name = None
        if session.notebook_id:
            from open_notebook.database.repository import repo_query
            workspace_result = await repo_query(
                "SELECT name FROM notebooks WHERE id = :id",
                {"id": session.notebook_id}
            )
            if workspace_result:
                workspace_name = workspace_result[0]["name"]

        response_sessions.append(
            ChatSessionResponse(
                id=session.id,
                title=session.title,
                notebook_id=session.notebook_id,
                created=session.created,
                updated=session.updated,
                message_count=msg_count,
                workspace_name=workspace_name
            )
        )

    return response_sessions


@router.get("/sessions/{session_id}", response_model=dict)
async def get_chat_session(session_id: str):
    """
    Get a chat session with its messages.

    Args:
        session_id: Chat session ID

    Returns:
        Chat session with messages
    """
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    # Get messages
    messages = await session.get_messages()
    msg_count = len(messages)

    return {
        "session": ChatSessionResponse(
            id=session.id,
            title=session.title,
            notebook_id=session.notebook_id,
            created=session.created,
            updated=session.updated,
            message_count=msg_count
        ),
        "messages": [
            ChatMessageResponse(
                id=msg.id,
                session_id=msg.session_id,
                role=msg.role,
                content=msg.content,
                created=msg.created,
                sources=msg.get_sources(),  # Include sources for citations
                ui_components=msg.get_ui_components(),
                render_mode=msg.render_mode,
                tool_results=msg.get_tool_results(),
                agent_steps=msg.agent_steps,  # Include agent steps
                langfuse_trace_id=msg.langfuse_trace_id,
                langfuse_observation_id=msg.langfuse_observation_id,
            )
            for msg in messages
        ]
    }


@router.get("/sessions/{session_id}/tools")
async def get_session_tools(session_id: str):
    """
    Get available tools for a chat session.

    Returns both source-based tools (HANA, APIs), registry tools,
    and MCP server tools that the user has permission to use.

    Args:
        session_id: Chat session ID

    Returns:
        List of available tools with metadata, grouped by MCP server
    """
    # Get session and notebook
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    # Get notebook
    notebook = await Notebook.get(session.notebook_id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notebook not found: {session.notebook_id}"
        )

    # Create tools via factory
    from api.services.tool_factory import get_tool_factory

    factory = get_tool_factory()
    user_id = getattr(session, "user_id", None) or "default"

    tools = await factory.create_tools_for_session(
        notebook_id=session.notebook_id,
        user_id=user_id,
        session_id=session_id,
    )

    # Convert LangChain tools to API response format
    tool_list = []
    mcp_servers = {}  # Track MCP tools by server

    for tool in tools:
        # Check if this is an MCP tool by checking metadata
        if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict) and tool.metadata.get('source') == 'mcp':
            # Extract MCP-specific data from metadata
            server_id = tool.metadata.get('server_id')
            server_name = tool.metadata.get('server_name', 'Unknown Server')
            server_status = tool.metadata.get('server_status', 'unknown')
            original_tool_name = tool.metadata.get('tool_name')

            # Initialize server entry if not exists
            if server_id not in mcp_servers:
                mcp_servers[server_id] = {
                    "id": server_id,
                    "name": server_name,
                    "status": server_status,
                    "tools": []
                }

            # Tool ID is already in the tool name (set by create_mcp_tool)
            tool_id = tool.name

            # Create MCP tool data
            tool_data = {
                "id": tool_id,
                "name": original_tool_name,  # Original tool name without prefix
                "description": tool.description,
                "tool_type": "mcp_tool",
                "source": "mcp",
                "server_name": server_name,
                "server_id": server_id,
                "input_schema": tool.args if hasattr(tool, 'args') else {}
            }
            mcp_servers[server_id]["tools"].append(tool_data)
            continue

        # Non-MCP tool handling
        tool_id = None
        source = "source"  # Default to source tool

        # Try to get registry ID from metadata/config/_tool_meta
        if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
            tool_id = tool.metadata.get('_registry_id')
        elif hasattr(tool, 'config') and isinstance(tool.config, dict):
            tool_id = tool.config.get('_registry_id')
        elif hasattr(tool, '_tool_meta'):
            tool_id = tool.__dict__.get('_tool_meta', {}).get('registry_id')

        if tool_id:
            source = "registry"
        else:
            # Source tool - use name as ID
            tool_id = tool.name

        # Extract metadata
        metadata = {}
        if hasattr(tool, "metadata") and isinstance(tool.metadata, dict):
            # Remove internal registry_id from exposed metadata
            metadata = {k: v for k, v in tool.metadata.items() if not k.startswith('_')}

        tool_data = {
            "id": tool_id,
            "name": tool.name,
            "description": tool.description,
            "tool_type": getattr(tool, "tool_type", "custom"),
            "category": getattr(tool, "category", None),
            "source": source,
            "metadata": metadata
        }
        tool_list.append(tool_data)

    # Also fetch MCP servers that need authentication (so they show up in UI)
    from open_notebook.database.repository import repo_query

    unauthenticated_servers_sql = """
        SELECT id, name, status FROM mcp_servers
        WHERE status IN ('needs_auth', 'disconnected', 'error')
        ORDER BY name
    """
    unauth_servers = await repo_query(unauthenticated_servers_sql)

    for server in unauth_servers:
        server_id = server["id"]
        if server_id not in mcp_servers:  # Don't duplicate if already present
            # Get tools for this server from capabilities cache
            tools_sql = """
                SELECT tool_name, description, input_schema FROM mcp_tools
                WHERE server_id = :server_id
                ORDER BY tool_name
            """
            server_tools = await repo_query(tools_sql, {"server_id": server_id})

            mcp_servers[server_id] = {
                "id": server_id,
                "name": server["name"],
                "status": server["status"],
                "tools": [
                    {
                        "id": f"mcp_{server_id}_{tool['tool_name']}",
                        "name": tool["tool_name"],
                        "description": tool["description"] or "",
                        "tool_type": "mcp_tool",
                        "source": "mcp",
                        "server_name": server["name"],
                        "server_id": server_id,
                        "input_schema": json.loads(tool["input_schema"]) if tool["input_schema"] else {}
                    }
                    for tool in server_tools
                ]
            }

    return {
        "tools": tool_list,
        "count": len(tool_list),
        "mcp_servers": list(mcp_servers.values())
    }


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(session_id: str, update_data: ChatSessionUpdate):
    """
    Update a chat session.

    Args:
        session_id: Chat session ID
        update_data: Update data

    Returns:
        Updated chat session
    """
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    # Update fields
    if update_data.title is not None:
        session.title = update_data.title

    if update_data.model_override is not None:
        session.model_override = update_data.model_override

    session.updated = datetime.utcnow()
    await session.save()

    msg_count = await session.get_message_count()

    return ChatSessionResponse(
        id=session.id,
        title=session.title,
        notebook_id=session.notebook_id,
        created=session.created,
        updated=session.updated,
        message_count=msg_count
    )


@router.delete("/sessions/{session_id}", response_model=SuccessResponse)
async def delete_chat_session(session_id: str):
    """
    Delete a chat session and all its messages.

    Args:
        session_id: Chat session ID

    Returns:
        Success response
    """
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    await session.delete()

    return SuccessResponse(
        success=True,
        message=f"Chat session {session_id} deleted successfully"
    )


# ============================================================================
# Chat Message Endpoints
# ============================================================================

@router.post("/sessions/{session_id}/messages")
async def send_chat_message(session_id: str, request: ChatRequest):
    """
    Send a message in a chat session using DataQueryAgent.

    Supports both streaming and non-streaming responses.
    Uses LangGraph agent with LangChain tools for HANA and API sources.

    Args:
        session_id: Chat session ID
        request: Chat request with message and options

    Returns:
        ChatResponse or EventSourceResponse (for streaming)
    """
    print(f"🔍 Chat request received - stream: {request.stream}, deep_research: {request.deep_research}, message: {request.message[:50]}...")

    # Apply global setting for generative UI if not explicitly set in request
    if not request.enable_generative_ui:
        from api.services.settings import get_setting
        global_enable_ui = await get_setting("enable_generative_ui", False)
        request.enable_generative_ui = global_enable_ui

    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    # Get notebook
    notebook = await Notebook.get(session.notebook_id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notebook not found: {session.notebook_id}"
        )

    # Create LangChain tools for this notebook via ToolFactory
    from api.services.tool_factory import get_tool_factory

    factory = get_tool_factory()
    # Extract user_id from auth context if available, default to "default"
    user_id = getattr(session, "user_id", None) or "default"

    tools = await factory.create_tools_for_session(
        notebook_id=session.notebook_id,
        user_id=user_id,
        session_id=session_id,
    )

    # Filter tools if selected_tool_ids provided
    if request.selected_tool_ids:
        print(f"🔧 Filtering tools: {len(tools)} available, {len(request.selected_tool_ids)} selected")
        print(f"🔧 Selected tool IDs: {request.selected_tool_ids}")

        filtered_tools = []
        for tool in tools:
            # Use tool name as the primary identifier (works for all tool types)
            tool_id = getattr(tool, 'name', None)

            # For registry tools, prefer the registry ID from metadata
            if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
                registry_id = tool.metadata.get('_registry_id')
                if registry_id:
                    tool_id = registry_id
            elif hasattr(tool, 'config') and isinstance(tool.config, dict):
                registry_id = tool.config.get('_registry_id')
                if registry_id:
                    tool_id = registry_id
            elif hasattr(tool, '_tool_meta'):
                registry_id = tool.__dict__.get('_tool_meta', {}).get('registry_id')
                if registry_id:
                    tool_id = registry_id

            if not tool_id:
                continue

            if tool_id in request.selected_tool_ids:
                print(f"  ✅ Including tool: {tool_id}")
                filtered_tools.append(tool)
            else:
                print(f"  ❌ Excluding tool: {tool_id}")

        tools = filtered_tools
        print(f"✅ Using {len(tools)} filtered tools")

    print(f"🤖 Created {len(tools)} LangChain tools for notebook {session.notebook_id}")

    # Build context if requested
    context_info = None
    system_message = None

    if request.include_context:
        context_service = get_context_service(
            max_tokens=request.max_context_tokens or 4000,
            model="gpt-4"
        )

        try:
            # INTELLIGENT SOURCE SELECTION
            # If sources are selected, use AI to determine which are most relevant
            selected_source_ids_for_context = request.selected_source_ids
            selected_note_ids_for_context = []

            if request.selected_source_ids and len(request.selected_source_ids) > 0:
                print(f"\n🧠 [Intelligent Source Selection] Analyzing query to select relevant sources...")
                print(f"   - User query: {request.message[:100]}...")
                print(f"   - Available sources: {len(request.selected_source_ids)}")

                # Import the intelligent source selector
                from api.services.intelligent_source_selector import IntelligentSourceSelector

                # Get notebook to fetch source and note metadata
                notebook = await Notebook.get(session.notebook_id)
                if notebook:
                    all_sources = await notebook.get_sources()
                    all_notes = await notebook.get_notes()

                    # Filter to only selected sources
                    selected_sources = [s for s in all_sources if s.id in request.selected_source_ids]
                    # Get all notes (they'll be filtered by the selector)
                    available_notes = all_notes

                    # Build metadata for selector
                    source_metadata = [
                        {
                            'id': s.id,
                            'title': s.title,
                            'source_type': s.source_type,
                            'summary': getattr(s, 'summary', None)
                        }
                        for s in selected_sources
                    ]

                    note_metadata = [
                        {
                            'id': n.id,
                            'title': n.title,
                            'summary': getattr(n, 'summary', None)
                        }
                        for n in available_notes
                    ]

                    # Use intelligent selector
                    selector = IntelligentSourceSelector()
                    selection_result = await selector.select_sources(
                        query=request.message,
                        available_sources=source_metadata,
                        available_notes=note_metadata,
                        max_sources=3
                    )

                    selected_source_ids_for_context = selection_result['selected_source_ids']
                    selected_note_ids_for_context = selection_result['selected_note_ids']

                    # Ensure we pass empty list [] not None when no sources selected
                    if not selected_source_ids_for_context:
                        selected_source_ids_for_context = []

                    print(f"   ✅ Selection complete:")
                    print(f"      - Selected sources: {selected_source_ids_for_context}")
                    print(f"      - Selected notes: {selected_note_ids_for_context}")
                    print(f"      - Reasoning: {selection_result['reasoning']}")
                    print(f"      - Confidence: {selection_result['confidence']}")

            # Fetch live data from API and HANA sources
            from api.services.live_data_service import fetch_all_live_sources, format_live_data_for_context

            print(f"📡 Fetching live data from API and HANA sources for notebook {session.notebook_id}")
            live_results = await fetch_all_live_sources(session.notebook_id)
            live_data_context = format_live_data_for_context(live_results)

            if live_results:
                print(f"✅ Fetched live data from {len(live_results)} source(s)")

            # Try to build notebook context (embedded content)
            context_data = None
            try:
                # Use intelligently selected sources and notes
                # Pass empty list [] not None when no sources selected (important!)
                context_data = await context_service.build_notebook_context(
                    notebook_id=session.notebook_id,
                    selected_source_ids=selected_source_ids_for_context if selected_source_ids_for_context is not None else [],
                    selected_note_ids=selected_note_ids_for_context if selected_note_ids_for_context else [],
                    include_notes=True  # Include notes (especially final deliverable) in context
                )
            except Exception as context_error:
                print(f"⚠️ Error building embedded context (continuing with live data only): {context_error}")
                # Continue with just live data
                context_data = {
                    "content": "",
                    "tokens": 0,
                    "sources": []
                }

            context_info = {
                "tokens": context_data["tokens"],
                "sources_included": len(context_data.get("sources", [])) or len(context_data.get("chunks", [])),
                "sources": context_data.get("sources", []),  # Include source details
                "live_sources": len(live_results)  # Track number of live sources
            }

            # Create numbered source references for citations
            source_references = []
            for idx, source in enumerate(context_data.get("sources", []), 1):
                source_references.append(f"[{idx}] {source['source_name']}")

            # Add placeholder for tool results if tools are available
            num_notebook_sources = len(context_data.get("sources", []))
            if tools:
                source_references.append(f"\n[{num_notebook_sources + 1}+] Tool query results (numbered when executed)")

            sources_list = "\n".join(source_references) if source_references else "No sources available"

            # Create system message with context and citation instructions
            embedded_content = context_data['content'] if context_data['content'] else "No embedded content available."

            # Load base system prompt from database
            from api.services.prompt_loader import load_prompt

            # Hardcoded fallback for backward compatibility
            FALLBACK_BASE_SYSTEM = """You are a helpful AI assistant with access to the following information from the notebook "{notebook_name}":

{embedded_content}

**Available Sources:**
{sources_list}
{live_data_context}

**Citation Instructions:**
- ONLY add citations [N] when you are directly using specific information from a source or tool result.
- DO NOT cite sources for general greetings, acknowledgments, or offers to help.
- DO NOT cite sources when describing what you CAN do or what tools are available.
- ONLY cite when you are stating a FACT or CLAIM that comes from a specific source.
- Notebook sources are numbered [1] through [{num_notebook_sources}].
- Tool results (web_search, HANA queries, API calls, etc.) are numbered starting from [{num_notebook_sources}+].
- Include citations throughout your answer, not just at the end.
- Be specific about which source OR tool result supports each claim.

**Examples:**
✅ CORRECT: "The main benefit is improved performance [1]. There are 1,234 active users [3]."
❌ WRONG: "Hello! I can help you look up accounts [1] or search emails [2]." (Don't cite when listing capabilities)
❌ WRONG: "I'm here to help you with Outreach [1]." (Don't cite in greetings)

**Remember:** Citations are for facts and data, not for describing your capabilities or greeting users.
"""

            # FORCE FALLBACK - Don't use database template for now
            base_system_message = FALLBACK_BASE_SYSTEM.format(
                notebook_name=notebook.name,
                embedded_content=embedded_content,
                sources_list=sources_list,
                live_data_context=live_data_context,
                num_notebook_sources=num_notebook_sources
            )

            print(f"\n📝 [System Prompt Debug]:")
            print(f"   - embedded_content length: {len(embedded_content)}")
            print(f"   - embedded_content preview: {embedded_content[:200]}...")
            print(f"   - sources_list length: {len(sources_list)}")
            print(f"   - Base system message length: {len(base_system_message)}")
            print(f"   - Contains embedded_content placeholder: {'{embedded_content}' in base_system_message}")
            print(f"   - Contains 'FINAL DELIVERABLE': {'FINAL DELIVERABLE' in base_system_message}")


            # Add tool instruction if tools are available
            if tools:
                FALLBACK_TOOL_INSTRUCTIONS = """

**IMPORTANT - Data Query Tools:**
You have access to {tool_count} data source(s) through query tools. When the user asks questions about data, you MUST use the provided tools to get live, accurate data. Do NOT make up or guess data values.

Available tools:
{tool_list}

Examples of when to use query tools:
- "Show me the first 10 rows"
- "What are the latest entries?"
- "How many records are there?"
- "Filter by X condition"
- "Show top N by some metric"
- "Call the API with specific parameters"

**FORMATTING DATA RESULTS:**
When you receive data from query tools, provide a brief summary and key insights about the data. Do NOT format the raw data yourself - the system will automatically render it in an interactive table format for the user.

Example response: "I've retrieved 10 log entries from the NBI LOG table. The data shows user actions (SNOOZE and DISMISS) taken between January 30-31, 2025. Key insights: 6 SNOOZE actions and 4 DISMISS actions across multiple user accounts."

Always prefer querying the live data sources over using any embedded context.

**CREATING VISUALIZATIONS:**
When the user asks for charts, graphs, or visualizations, use the 'create_chart' tool to generate interactive visualizations. DO NOT write JSON or code yourself. The tool will handle chart creation automatically.

IMPORTANT - Chart Title Guidelines:
- ALWAYS provide a meaningful, descriptive title that summarizes what the chart shows
- NEVER use generic titles like "Create Chart", "Chart", "Visualization", or "Data"
- The title should describe the data being visualized (e.g., "Revenue by Region", "Sales Trends Over Time", "Customer Distribution by Segment")
- Include context when relevant (e.g., company name, time period, metric names)

Examples of GOOD titles:
- "Total Addressable Wallet by SAP Solution Area"
- "Monthly Revenue Growth Q1 2024"
- "Customer Satisfaction Scores by Department"
- "Product Sales Comparison - North vs South Region"

Examples of when to use create_chart:
- "Show me a bar chart of sales by region"
- "Create a line graph of revenue over time"
- "Visualize the data as a pie chart"
- "Plot temperature trends"

To use create_chart:
1. Extract or structure the data as an array of dictionaries (e.g., [{"month": "Jan", "value": 100}, {"month": "Feb", "value": 150}])
2. Call create_chart with the data and ALWAYS provide a descriptive title
3. Optionally specify chart_type, description, axis labels, etc.
4. The system will automatically render the interactive chart for the user

Example: If analyzing sales data from the final deliverable and user asks "show me this as a chart", extract the relevant data points and call create_chart with title="Sales by Product Category" or similar descriptive title."""

                tool_instructions = await load_prompt(
                    "chat_tool_instructions",
                    variables={
                        "tool_count": len(tools),
                        "tool_list": "\n".join(f"- {tool.name}: {tool.description}" for tool in tools)
                    },
                    fallback=FALLBACK_TOOL_INSTRUCTIONS
                )
                base_system_message += tool_instructions

            # Add live data instruction
            if live_results:
                successful_live = [r for r in live_results if r["success"]]
                if successful_live:
                    FALLBACK_LIVE_DATA_NOTICE = """

**LIVE DATA AVAILABLE:**
The data shown in the "LIVE DATA FROM SOURCES" section above was fetched in real-time just now. This is fresh, up-to-date information from live API endpoints and HANA database tables. When answering questions about this data, you are working with current information, not historical snapshots."""

                    live_data_notice = await load_prompt(
                        "chat_live_data_notice",
                        fallback=FALLBACK_LIVE_DATA_NOTICE
                    )
                    base_system_message += live_data_notice

            system_message = base_system_message

        except Exception as e:
            print(f"Error building context: {e}")
            # Continue without context
            pass

    # Save user message
    user_message = await session.add_message("user", request.message)

    # Handle deep research mode - use BACKGROUND JOB instead of SSE streaming
    if request.deep_research:
        print(f"[Chat] 🔬 Deep research mode enabled - starting background job...")
        from open_notebook.agents.deep_research_agent import DeepResearchAgent
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store

        # Get model configuration
        language_model_id = await get_setting("language_model_id", "")
        model_name = session.model_override or language_model_id
        print(f"[Chat] Model: {model_name}")

        if not model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No language model configured. Please select a model in Settings → Models before using deep research."
            )

        credential = get_model_credential(model_name)
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model credential not found. Please configure a model."
            )

        actual_model_name = credential["model_name"]
        base_url = credential.get("base_url", "https://api.openai.com/v1")
        api_key = credential.get("api_key")

        print(f"[Chat] Creating background job for deep research...")

        # Create a background job that runs independently
        import uuid
        job_id = str(uuid.uuid4())

        # Store job metadata
        from api.routers.deep_research import _research_jobs
        _research_jobs[job_id] = {
            "job_id": job_id,
            "session_id": session_id,
            "status": "running",
            "phase": "initializing",
            "progress": 0,
            "message": request.message,
            "created": datetime.utcnow().isoformat(),
            "result": None,
            "error": None
        }

        # Start the research in the background
        async def run_deep_research_job():
            try:
                print(f"[Job {job_id}] Starting deep research...")

                # Get tools
                from api.services.tool_factory import ToolFactory
                tool_factory = ToolFactory()
                tools = await tool_factory.create_tools_for_session(
                    notebook_id=session.notebook_id,
                    user_id=session.created_by or "default_user",
                    session_id=session_id
                )

                # Create agent
                agent = DeepResearchAgent(
                    model_name=actual_model_name,
                    notebook_id=session.notebook_id,
                    session_id=session_id,
                    max_iterations=5,
                    search_strategies=["hybrid", "vector", "keyword"],
                    tools=tools,
                    base_url=base_url,
                    api_key=api_key,
                    progress_callback=None,
                    step_callback=None
                )

                # Run research
                final_report = ""
                async for update in agent.research(request.message):
                    phase = update.get('phase')
                    progress = update.get('progress', 0)

                    # Update job status
                    _research_jobs[job_id].update({
                        "phase": str(phase),
                        "progress": progress,
                        "status": "running"
                    })

                    if phase == "complete" or str(phase) == "ResearchPhase.COMPLETE":
                        final_report = update.get("final_report", "")
                        break

                # Save the result
                assistant_msg = await session.add_message(
                    "assistant",
                    f"# Deep Research Complete\n\n{final_report}",
                    agent_steps=agent.agent_steps
                )

                # Mark job as complete
                _research_jobs[job_id].update({
                    "status": "completed",
                    "phase": "complete",
                    "progress": 100,
                    "result": {
                        "message_id": assistant_msg.id,
                        "report": final_report,
                        "report_length": len(final_report)
                    }
                })

                print(f"[Job {job_id}] ✓ Deep research completed, report saved: {len(final_report)} chars")

            except Exception as e:
                print(f"[Job {job_id}] ✗ Deep research failed: {e}")
                import traceback
                traceback.print_exc()
                _research_jobs[job_id].update({
                    "status": "failed",
                    "error": make_user_friendly_error(e)
                })

        # Start the job in background (don't await)
        asyncio.create_task(run_deep_research_job())

        # Return immediately with job info
        return ChatResponse(
            message_id=job_id,  # Return job_id as message_id temporarily
            content=f"Deep research started. Job ID: {job_id}",
            role="assistant",
            sources=[],
            metadata={
                "job_id": job_id,
                "deep_research": True,
                "status": "running"
            }
        )
        print(f"[Chat] 🔬 Deep research mode enabled - starting research workflow...")
        from open_notebook.agents.deep_research_agent import DeepResearchAgent
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store

        # Get model configuration
        language_model_id = await get_setting("language_model_id", "")
        model_name = session.model_override or language_model_id
        print(f"[Chat] Model: {model_name}")

        if not model_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No language model configured. Please select a model in Settings → Models before using deep research."
            )

        credential = get_model_credential(model_name)
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model credential not found. Please configure a model."
            )

        actual_model_name = credential["model_name"]
        base_url = credential.get("base_url", "https://api.openai.com/v1")
        api_key = credential.get("api_key")

        print(f"[Chat] Creating DeepResearchAgent with model: {actual_model_name}")

        # Get tools for the agent (web_search, etc.)
        from api.services.tool_factory import ToolFactory
        tool_factory = ToolFactory()
        tools = await tool_factory.create_tools_for_session(
            notebook_id=session.notebook_id,
            user_id=session.created_by or "default_user",
            session_id=session_id
        )
        print(f"[Chat] 🔧 Loaded {len(tools)} tools for deep research")

        # Create a list to track steps with thread-safe access
        import threading
        step_lock = threading.Lock()
        streamed_steps = []
        streamed_step_ids = set()  # Track which steps we've already streamed

        def step_callback(step):
            """Callback to immediately track steps as they're recorded"""
            with step_lock:
                # Use timestamp + step_type + content as unique ID to avoid duplicates
                step_id = f"{step.get('timestamp')}_{step.get('step_type')}_{step.get('content', '')[:50]}"
                if step_id not in streamed_step_ids:
                    streamed_steps.append(step)
                    streamed_step_ids.add(step_id)

        # Create deep research agent with step callback and tools
        agent = DeepResearchAgent(
            model_name=actual_model_name,
            notebook_id=session.notebook_id,
            session_id=session_id,
            max_iterations=5,
            search_strategies=["hybrid", "vector", "keyword"],
            tools=tools,  # Pass tools for external research
            base_url=base_url,
            api_key=api_key,
            progress_callback=None,  # We'll handle progress via streaming
            step_callback=step_callback  # Real-time step notifications
        )

        print(f"[Chat] Agent created with {len(tools)} tools, starting research stream...")

        # Stream deep research results
        if request.stream:
            print(f"[Chat] Entering SSE streaming mode...")
            async def deep_research_stream():
                """Stream deep research progress and results"""
                print(f"[Chat] 🔬 Deep research stream started for query: {request.message[:50]}...")
                try:
                    final_report = ""
                    last_step_count = 0

                    # Stream directly from agent.research() - no background task needed
                    print(f"[Chat] Starting direct stream from agent.research()...")
                    async for update in agent.research(request.message):
                        phase = update.get('phase')
                        progress = update.get('progress', 0)
                        print(f"[Chat] Research update: phase={phase}, progress={progress}%")

                        # Stream progress update
                        progress_json = json.dumps({
                            'phase': str(phase),
                            'progress': progress
                        }).replace('\n', ' ').replace('\r', '')

                        yield {
                            "event": "progress",
                            "data": progress_json
                        }

                        # Stream any new agent steps that were added
                        with step_lock:
                            if len(streamed_steps) > last_step_count:
                                new_steps = streamed_steps[last_step_count:]
                                print(f"[Chat] Streaming {len(new_steps)} new agent steps...")
                                for step in new_steps:
                                    step_json = json.dumps(step).replace('\n', ' ').replace('\r', '')
                                    yield {
                                        "event": "agent_step",
                                        "data": step_json
                                    }
                                last_step_count = len(streamed_steps)

                        # Check if complete and capture final report
                        if phase == ResearchPhase.COMPLETE or phase == "complete":
                            final_report = update.get("final_report", "")
                            print(f"[Chat] Research complete! Final report: {len(final_report)} chars")
                            # Don't break - let the loop finish naturally
                            # break  # REMOVED

                    # Stream any remaining agent steps
                    with step_lock:
                        if len(streamed_steps) > last_step_count:
                            remaining_steps = streamed_steps[last_step_count:]
                            print(f"[Chat] Streaming {len(remaining_steps)} remaining agent steps...")
                            for step in remaining_steps:
                                step_json = json.dumps(step).replace('\n', ' ').replace('\r', '')
                                yield {
                                    "event": "agent_step",
                                    "data": step_json
                                }

                    # Stream final report in chunks
                    if final_report:
                        print(f"[Chat] Streaming final report ({len(final_report)} chars)...")
                        chunk_size = 100
                        for i in range(0, len(final_report), chunk_size):
                            chunk = final_report[i:i+chunk_size]
                            chunk_json = json.dumps({'content': chunk})
                            yield {
                                "event": "chunk",
                                "data": chunk_json
                            }

                    # Save assistant message with agent steps
                    assistant_msg = await session.add_message(
                        "assistant",
                        f"# Deep Research Complete\n\n{final_report}",
                        agent_steps=agent.agent_steps
                    )

                    # Send done event
                    done_json = json.dumps({'message_id': assistant_msg.id, 'sources': []})
                    yield {
                        "event": "done",
                        "data": done_json
                    }

                    print(f"[Chat] Deep research stream finished successfully")

                except Exception as e:
                    print(f"[Deep Research] Error: {e}")
                    import traceback
                    traceback.print_exc()

                    # Provide user-friendly error messages
                    error_message = str(e)
                    if "FOREIGN KEY constraint failed" in error_message:
                        error_message = "Chat session not found. Please refresh the page and try again."
                    elif "Jwt is expired" in error_message:
                        error_message = "Authentication token expired. Please check your LiteLLM configuration."
                    elif "Connection refused" in error_message:
                        error_message = "Cannot connect to AI service. Please check your API configuration."
                    elif "timeout" in error_message.lower():
                        error_message = "Request timed out. The AI service may be overloaded. Please try again."
                    elif "rate limit" in error_message.lower():
                        error_message = "Rate limit exceeded. Please wait a moment and try again."

                    error_json = json.dumps({
                        'error': error_message,
                        'details': str(e) if str(e) != error_message else None
                    })
                    yield {
                        "event": "error",
                        "data": error_json
                    }

            return EventSourceResponse(deep_research_stream())

        # Non-streaming deep research
        final_state = await agent.research_non_streaming(request.message)

        if final_state.get("phase") == "error":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=final_state.get("error", "Deep research failed")
            )

        final_report = final_state.get("final_report", "")
        assistant_msg = await session.add_message(
            "assistant",
            f"# Deep Research Complete\n\n{final_report}",
            agent_steps=agent.agent_steps
        )

        return ChatResponse(
            message_id=assistant_msg.id,
            content=final_report,
            role="assistant",
            sources=[]
        )

    # Check if workspace has assigned agents from guided creation
    workspace_agent = None
    try:
        from api.services.workspace_agent_selector import get_workspace_agent_selector

        agent_selector = get_workspace_agent_selector()
        workspace_agent = await agent_selector.select_agent_for_message(
            workspace_id=session.notebook_id,
            message=request.message
        )

        if workspace_agent:
            print(f"🎯 Workspace has assigned agent: {workspace_agent['name']} ({workspace_agent['type']})")
    except Exception as e:
        logger.warning(f"Failed to check workspace agents: {e}")

    # Prepare agent configuration based on workspace agent (if any)
    agent_system_message = system_message
    agent_model_override = None

    if workspace_agent:
        # Use workspace-assigned agent's configuration
        print(f"🤖 Using workspace-assigned agent: {workspace_agent['name']}")

        # Use agent's custom system prompt if available
        if workspace_agent.get("system_prompt"):
            agent_system_message = workspace_agent["system_prompt"]

        # Use agent's model if specified
        if workspace_agent.get("model_name"):
            agent_model_override = workspace_agent["model_name"]

        # Load agent's tools from configuration
        import json
        tool_ids = json.loads(workspace_agent.get("tool_ids", "[]"))
        if tool_ids:
            # Filter tools to only those assigned to this agent
            tools = [t for t in tools if t.name in tool_ids or any(tid in str(t) for tid in tool_ids)]
            print(f"  Agent has {len(tool_ids)} assigned tools: {tool_ids}")

    # Now use the unified DataQueryAgent path for all cases
    # This ensures consistent streaming behavior whether using workspace agent or not
    # UNIFIED AGENT APPROACH: Always use DataQueryAgent
    # The agent automatically decides whether to use tools based on the conversation
    # This matches Claude Code's pattern where tool invocation happens transparently

    from api.services.settings import get_setting

    # Get model name (use agent override if available, else session/global default)
    language_model_id = await get_setting("language_model_id", "")
    model_name = agent_model_override or session.model_override or language_model_id

    if not model_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No language model configured. Please select a model in Settings."
        )

    # Get credential to extract actual model name
    credential = get_model_credential(model_name)
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model credential not found. Please configure a model."
        )

    actual_model_name = credential["model_name"]

    print(f"📋 Credential details:")
    print(f"   model_name: {credential.get('model_name')}")
    print(f"   base_url: {credential.get('base_url')}")
    print(f"   api_key: {credential.get('api_key')[:20] if credential.get('api_key') else 'None'}...")
    print(f"   provider: {credential.get('provider')}")
    if workspace_agent:
        print(f"   workspace_agent: {workspace_agent['name']} (using {'custom' if agent_model_override else 'default'} model)")

    # Initialize observability manager and create traces
    obs_manager = get_observability_manager()
    trace_ids = obs_manager.create_trace(
        session_id=session_id,
        notebook_id=session.notebook_id,
        metadata={
            "user_message": request.message[:200],  # Truncate for metadata
            "model": actual_model_name,
            "notebook_title": notebook.name,
            "tools_available": len(tools),
            "include_context": request.include_context,
            "enable_generative_ui": request.enable_generative_ui,
            "workspace_agent": workspace_agent["name"] if workspace_agent else None,
        }
    )

    # Use DataQueryAgent for ALL cases (with or without tools, with or without workspace agent)
    # DataQueryAgent uses LangChain which handles all providers automatically:
    # - Claude (via LiteLLM, SAP AI Core, or direct Anthropic API)
    # - GPT-4 (via OpenAI or LiteLLM)
    # - Gemini (via Google or LiteLLM)
    # - Any other provider
    #
    # When tools=[], the agent simply responds conversationally
    # When tools are available, the agent decides whether to use them based on the query
    from open_notebook.agents.data_query_agent import DataQueryAgent

    if tools:
        print(f"🤖 Using DataQueryAgent (LangGraph) for {actual_model_name} with {len(tools)} tools")
    else:
        print(f"🤖 Using DataQueryAgent (LangGraph) for {actual_model_name} in conversational mode (no tools)")

    agent = DataQueryAgent(
        model_name=actual_model_name,
        notebook_id=session.notebook_id,
        tools=tools,  # Can be empty list [] - agent handles both cases
        session_id=session_id,
        system_message=agent_system_message,  # Use workspace agent's prompt if available
        capture_tool_results=request.enable_generative_ui,
        trace_ids=trace_ids,
        api_key=credential.get("api_key"),
        base_url=credential.get("base_url"),
        enable_tool_filtering=True if tools else False,  # Only filter when tools exist
        task_description=request.message,  # Use user query for filtering
    )

    # Get chat history
    chat_history = await session.get_messages()
    # Convert to dict format (exclude last message which we just added)
    history_dicts = [
        {"role": msg.role, "content": msg.content}
        for msg in chat_history[:-1]
    ] if len(chat_history) > 1 else []

    # Handle streaming vs non-streaming
    print(f"🔄 Request stream flag: {request.stream}")
    if request.stream:
        print("✅ Taking streaming path with EventSourceResponse")

        # Add workspace agent metadata to the stream if applicable
        async def enhanced_stream():
            # Send workspace agent metadata first
            if workspace_agent:
                yield {
                    "event": "metadata",
                    "data": json.dumps({
                        "workspace_agent": {
                            "name": workspace_agent["name"],
                            "type": workspace_agent["type"],
                            "id": workspace_agent["id"]
                        }
                    })
                }

            # Stream the actual agent response
            async for event in _stream_agent_response(
                agent=agent,
                user_message=request.message,
                chat_history=history_dicts,
                session=session,
                context_info=context_info,
                enable_generative_ui=request.enable_generative_ui,
            ):
                yield event

        return EventSourceResponse(
            enhanced_stream(),
            ping=5   # Send ping every 5 seconds to keep connection alive
        )
    else:
            # Non-streaming agent response
            response_text = await agent.invoke(request.message, history_dicts)

            # Generate UI components from tool results if enabled
            ui_components = None
            tool_results_data = None
            render_mode = "markdown"

            if request.enable_generative_ui:
                captured = agent.get_captured_tool_results()

                # Check if user explicitly requested visualization
                viz_keywords = ['show me', 'display', 'visualize', 'create a table', 'show table',
                               'show data', 'list all', 'show chart', 'plot', 'graph', 'draw',
                               'create chart', 'create a chart', 'pie chart', 'bar chart', 'line chart']
                user_wants_viz = any(keyword in request.message.lower() for keyword in viz_keywords)

                if captured and user_wants_viz:
                    tool_results_data = captured
                    from api.services.component_generator import get_component_generator
                    generator = get_component_generator()
                    ui_component_models = generator.generate_from_dicts(captured, response_text)
                    ui_components = [c.model_dump() for c in ui_component_models]
                    render_mode = "hybrid" if ui_components else "markdown"

            # Finalize agent steps: mark any "running" or "pending" steps as "completed"
            finalized_steps = []
            for step in agent.agent_steps:
                finalized_step = step.copy()
                if finalized_step.get("status") in ["running", "pending"]:
                    finalized_step["status"] = "completed"
                finalized_steps.append(finalized_step)

            # Save assistant message with generative UI data
            # IMPORTANT: Only save tool_results if NO ui_components were generated
            # UI components are the processed/visualized version of tool results,
            # so we don't want to duplicate the display by showing both
            assistant_message = await session.add_message(
                "assistant",
                response_text,
                ui_components=ui_components,
                render_mode=render_mode,
                tool_results=tool_results_data if not ui_components else None,
                agent_steps=finalized_steps,
                trace_ids=trace_ids,
            )

            # Flush Langfuse events
            obs_manager.flush()

            return ChatResponse(
                session_id=session.id,
                user_message=ChatMessageResponse(
                    id=user_message.id,
                    session_id=user_message.session_id,
                    role=user_message.role,
                    content=user_message.content,
                    created=user_message.created
                ),
                assistant_message=ChatMessageResponse(
                    id=assistant_message.id,
                    session_id=assistant_message.session_id,
                    role=assistant_message.role,
                    content=assistant_message.content,
                    created=assistant_message.created,
                    ui_components=ui_components,
                    render_mode=render_mode,
                    tool_results=tool_results_data if not ui_components else None,
                ),
                context_info=context_info
            )


# ============================================================================
# Notebook-Scoped Endpoints
# ============================================================================

@router.get("/notebooks/{notebook_id}/sessions", response_model=List[ChatSessionResponse])
async def get_notebook_chat_sessions(notebook_id: str):
    """
    Get all chat sessions for a notebook.

    Args:
        notebook_id: Notebook ID

    Returns:
        List of chat sessions
    """
    # Verify notebook exists
    notebook = await Notebook.get(notebook_id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notebook not found: {notebook_id}"
        )

    sessions = await ChatSession.get_by_notebook(notebook_id)

    response_sessions = []
    for session in sessions:
        msg_count = await session.get_message_count()
        response_sessions.append(
            ChatSessionResponse(
                id=session.id,
                title=session.title,
                notebook_id=session.notebook_id,
                created=session.created,
                updated=session.updated,
                message_count=msg_count
            )
        )

    return response_sessions


# ============================================================================
# Microsite Chat Integration Endpoints
# ============================================================================

@router.post("/sessions/{session_id}/detect-microsite-intent")
async def detect_microsite_intent_endpoint(session_id: str, request: ChatRequest):
    """
    Detect if a chat message contains microsite generation intent.

    Returns intent analysis without triggering generation.
    Used by the frontend to decide whether to show the MicrositeChatCommands UI.
    """
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    from api.services.microsite_intent import detect_microsite_intent

    intent = detect_microsite_intent(request.message)

    return {
        "is_match": intent.is_match,
        "template_hint": intent.template_hint,
        "workspace_hint": intent.workspace_hint,
        "action": intent.action,
    }


@router.post("/sessions/{session_id}/microsite-generate")
async def chat_microsite_generate(
    session_id: str,
    microsite_id: str,
    template_id: str,
    source_ids: List[str],
    user_prompt: Optional[str] = None,
):
    """
    Trigger microsite generation from chat with SSE progress streaming.

    Streams progress events back to the client as Server-Sent Events:
    - event: progress - Generation progress updates (phase, percentage, message)
    - event: moderation - Moderation report when guardrails complete
    - event: done - Final result with preview URL and version number
    - event: error - Error details if generation fails
    """
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    return EventSourceResponse(
        _stream_microsite_generation(
            session=session,
            microsite_id=microsite_id,
            template_id=template_id,
            source_ids=source_ids,
            user_prompt=user_prompt,
        )
    )


async def _stream_microsite_generation(
    session: ChatSession,
    microsite_id: str,
    template_id: str,
    source_ids: List[str],
    user_prompt: Optional[str],
):
    """
    Stream microsite generation progress via SSE.

    Yields progress events as the generation pipeline executes:
    loading template -> building context -> generating sections -> running guardrails -> saving
    """
    try:
        # Phase 1: Starting
        yield {
            "event": "progress",
            "data": json.dumps({
                "phase": "starting",
                "progress": 0,
                "message": "Initializing microsite generation...",
            }),
        }

        # Phase 2: Loading template
        yield {
            "event": "progress",
            "data": json.dumps({
                "phase": "loading_template",
                "progress": 10,
                "message": "Loading template structure...",
            }),
        }

        from api.services.microsite_generation_service import MicrositeGenerationService

        service = MicrositeGenerationService()

        # Phase 3: Building context
        yield {
            "event": "progress",
            "data": json.dumps({
                "phase": "building_context",
                "progress": 25,
                "message": f"Analyzing {len(source_ids)} source(s)...",
            }),
        }

        # Phase 4: Generating content
        yield {
            "event": "progress",
            "data": json.dumps({
                "phase": "generating",
                "progress": 40,
                "message": "AI is generating content sections...",
            }),
        }

        # Execute the full generation
        result = await service.generate_microsite(
            microsite_id=microsite_id,
            template_id=template_id,
            source_ids=source_ids,
            notebook_id=session.notebook_id,
            user_prompt=user_prompt,
        )

        # Phase 5: Guardrails
        yield {
            "event": "progress",
            "data": json.dumps({
                "phase": "moderation",
                "progress": 80,
                "message": "Running content moderation...",
            }),
        }

        # Send moderation report if available
        moderation = result.get("moderation", {})
        if moderation:
            yield {
                "event": "moderation",
                "data": json.dumps(moderation),
            }

        # Phase 6: Complete
        yield {
            "event": "progress",
            "data": json.dumps({
                "phase": "complete",
                "progress": 100,
                "message": "Microsite generated successfully!",
            }),
        }

        # Save assistant message in chat
        preview_url = result.get("preview_url", f"/microsites/{microsite_id}/preview")
        version = result.get("version", 1)
        assistant_content = (
            f"Your microsite has been generated (version {version})! "
            f"[Preview]({preview_url}) | [Edit](/microsites/{microsite_id}/edit)"
        )
        await session.add_message("assistant", assistant_content)

        # Send final result
        yield {
            "event": "done",
            "data": json.dumps({
                "microsite_id": microsite_id,
                "version": version,
                "preview_url": preview_url,
                "sections_count": len(result.get("sections", [])),
                "moderation_status": moderation.get("status", "unknown"),
            }),
        }

    except Exception as e:
        import traceback
        print(f"Microsite generation streaming error: {e}")
        traceback.print_exc()

        # Save error message in chat
        await session.add_message(
            "assistant",
            f"Sorry, microsite generation failed: {str(e)}"
        )

        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)}),
        }


# ============================================================================
# Helper Functions
# ============================================================================

async def generate_chat_response(
    user_message: str,
    system_message: Optional[str],
    session: ChatSession,
    hana_tools: Optional[List[dict]] = None,
    tool_metadata_map: Optional[Dict[str, dict]] = None
) -> str:
    """
    Generate a chat response using LLM with optional HANA tool support.

    Args:
        user_message: User's message
        system_message: Optional system message with context
        session: Chat session for history
        hana_tools: Optional list of HANA query tools
        tool_metadata_map: Metadata for executing tools

    Returns:
        Assistant's response
    """
    # Get conversation history
    messages = await ChatMessage.get_recent_context(session.id, max_messages=10)

    # Build messages for LLM
    llm_messages = []

    if system_message:
        llm_messages.append({"role": "system", "content": system_message})

    # Add conversation history (excluding the last user message we just added)
    llm_messages.extend(messages[:-1] if messages else [])

    # Add current user message
    llm_messages.append({"role": "user", "content": user_message})

    # Call AI model via LiteLLM proxy
    try:
        import httpx
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store

        # Get configured model from database
        language_model_id = await get_setting("language_model_id", "")
        model_id = session.model_override or language_model_id

        if not model_id:
            print("No AI model configured")
            return "⚠️ No AI model configured. Please add a model in Settings → Models."

        credential = _credentials_store.get(model_id)

        if not credential:
            print("No AI model configured")
            return "⚠️ No AI model configured. Please add a model in Settings → Models."

        print(f"🤖 Calling AI model: {credential['model_name']} via {credential['base_url']}")

        # Detect if this is an Anthropic model
        is_anthropic = "anthropic" in credential["model_name"].lower() or "claude" in credential["model_name"].lower()

        if is_anthropic:
            # Use Anthropic's native API format
            # Convert messages to Anthropic format (system is separate, no role in messages)
            anthropic_messages = []
            system_content = None

            for msg in llm_messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            request_payload = {
                "model": credential["model_name"],
                "messages": anthropic_messages,
                "max_tokens": 2000,
                "temperature": 0.7
            }

            if system_content:
                request_payload["system"] = system_content

            # Add tools if available
            if hana_tools:
                request_payload["tools"] = hana_tools
                print(f"🔧 Including {len(hana_tools)} HANA tools in request")

            # Use Anthropic endpoint
            endpoint_url = f"{credential['base_url'].replace('/litellm/v1', '')}/anthropic/v1/messages"

            print(f"📤 Request URL: {endpoint_url}")

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    endpoint_url,
                    headers={
                        "x-api-key": credential['api_key'],
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json=request_payload
                )

                print(f"📥 Response status: {response.status_code}")

                if response.status_code == 200:
                    result = response.json()

                    # Check for tool calls
                    if result.get("stop_reason") == "tool_use":
                        print("🔧 LLM requested tool call")

                        # Execute tool calls
                        from api.services.hana_tool_executor import HANAToolExecutor

                        tool_results = []
                        for content_block in result["content"]:
                            if content_block["type"] == "tool_use":
                                tool_name = content_block["name"]
                                tool_call_id = content_block["id"]
                                tool_input = content_block["input"]

                                metadata = tool_metadata_map.get(tool_name) if tool_metadata_map else None

                                if not metadata:
                                    print(f"⚠️ No metadata for tool {tool_name}, skipping")
                                    continue

                                # Execute HANA query
                                try:
                                    tool_call = {
                                        "id": tool_call_id,
                                        "function": {"name": tool_name},
                                        "arguments": tool_input  # Already a dict in Anthropic format
                                    }
                                    query_results = await HANAToolExecutor.execute_tool(tool_call, metadata)

                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": tool_call_id,
                                        "content": json.dumps(query_results, default=str)
                                    })

                                    print(f"✅ Tool {tool_name} returned {len(query_results)} rows")

                                except Exception as e:
                                    print(f"❌ Tool execution error: {str(e)}")
                                    tool_results.append({
                                        "type": "tool_result",
                                        "tool_use_id": tool_call_id,
                                        "content": f"Error: {str(e)}",
                                        "is_error": True
                                    })

                        # If we have tool results, make another API call with results
                        if tool_results:
                            # Add assistant's tool use message
                            anthropic_messages.append({
                                "role": "assistant",
                                "content": result["content"]
                            })

                            # Add tool results as user message
                            anthropic_messages.append({
                                "role": "user",
                                "content": tool_results
                            })

                            # Make follow-up call for final response
                            request_payload["messages"] = anthropic_messages

                            response = await client.post(
                                endpoint_url,
                                headers={
                                    "x-api-key": credential['api_key'],
                                    "anthropic-version": "2023-06-01",
                                    "Content-Type": "application/json"
                                },
                                json=request_payload
                            )

                            if response.status_code == 200:
                                final_result = response.json()
                                content = final_result["content"][0]["text"]
                                print(f"✅ AI response received: {len(content)} chars")
                                return content
                            else:
                                error_text = response.text[:200]
                                print(f"❌ AI error: {response.status_code} - {error_text}")
                                return f"⚠️ AI model error ({response.status_code}): {error_text}"
                    else:
                        # No tool calls, return text content
                        content = result["content"][0]["text"]
                        print(f"✅ AI response received: {len(content)} chars")
                        return content
                else:
                    error_text = response.text[:200]
                    print(f"❌ AI error: {response.status_code} - {error_text}")
                    return f"⚠️ AI model error ({response.status_code}): {error_text}"
        else:
            # Use OpenAI-compatible format for other models
            request_payload = {
                "model": credential["model_name"],
                "messages": llm_messages,
                "temperature": 0.7,
                "max_tokens": 2000,
                "stream": False
            }
            print(f"📤 Request URL: {credential['base_url']}/chat/completions")
            print(f"📤 Request headers: Authorization=Bearer {credential['api_key'][:20]}..., Content-Type=application/json")
            print(f"📤 Request body: {request_payload}")

            # Call LiteLLM proxy
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{credential['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {credential['api_key']}",
                        "Content-Type": "application/json"
                    },
                    json=request_payload
                )

                print(f"📥 Response status: {response.status_code}")
                print(f"📥 Response body: {response.text[:500]}")

                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    print(f"✅ AI response received: {len(content)} chars")
                    return content
                else:
                    error_text = response.text[:200]
                    print(f"❌ AI error: {response.status_code} - {error_text}")
                    return f"⚠️ AI model error ({response.status_code}): {error_text}"

    except Exception as e:
        import traceback
        print(f"❌ Error calling AI model: {e}")
        print(traceback.format_exc())
        return f"⚠️ Error: {str(e)}"


# ============================================================================
# Agent Streaming Helper (New)
# ============================================================================

async def _stream_agent_response(
    agent,
    user_message: str,
    chat_history: List[dict],
    session: ChatSession,
    context_info: Optional[dict],
    enable_generative_ui: bool = False,
):
    """
    Stream agent responses with step-by-step visualization

    Args:
        agent: DataQueryAgent instance
        user_message: User's message
        chat_history: Chat history as list of dicts
        session: Chat session
        context_info: Context information
        enable_generative_ui: Whether to generate UI components from tool results

    Yields:
        SSE events with agent steps and response chunks
    """
    accumulated_text = ""

    try:
        # Send initial metadata
        yield {
            "event": "metadata",
            "data": json.dumps({
                "session_id": session.id,
                "tools_available": len(agent.tools),
                "tool_names": agent.get_tool_names(),
                "context_info": context_info
            })
        }

        # Send thinking indicator
        yield {
            "event": "agent_step",
            "data": json.dumps({
                "step_type": "thinking",
                "content": "Analyzing your question...",
                "status": "running",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {}
            })
        }

        # Stream agent execution
        print(f"🌊 Starting agent stream for message: {user_message[:30]}...")
        async for event in agent.stream_response(user_message, chat_history):
            print(f"📨 Agent event: {list(event.keys())}, content: {str(event)[:200]}")
            # Check event type
            if "agent" in event:
                # Agent node executed (reasoning/response)
                messages = event["agent"].get("messages", [])
                print(f"📨 Agent messages count: {len(messages) if messages else 0}")
                if messages:
                    last_message = messages[-1]
                    print(f"📨 Last message type: {type(last_message)}, has_tool_calls: {hasattr(last_message, 'tool_calls')}, has_content: {hasattr(last_message, 'content')}")

                    # Check if agent is calling tools
                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                        # Agent decided to use tools
                        print(f"📨 Tool calls detected: {len(last_message.tool_calls)}")
                        yield {
                            "event": "agent_step",
                            "data": json.dumps({
                                "step_type": "thinking",
                                "content": "Preparing to query data sources...",
                                "status": "completed",
                                "timestamp": datetime.utcnow().isoformat(),
                                "metadata": {}
                            })
                        }

                        for tool_call in last_message.tool_calls:
                            tool_name = tool_call.get("name")
                            yield {
                                "event": "agent_step",
                                "data": json.dumps({
                                    "step_type": "tool_call",
                                    "content": f"Executing: {tool_name}",
                                    "status": "running",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "metadata": {
                                        "tool_name": tool_name
                                    }
                                })
                            }
                    elif hasattr(last_message, "content") and last_message.content:
                        # Agent response text
                        content = last_message.content
                        print(f"📨 Message content: type={type(content)}, value={str(content)[:100]}")
                        if isinstance(content, str) and content:
                            print(f"✨ Yielding chunk: {content[:50]}...")
                            accumulated_text += content
                            yield {
                                "event": "chunk",
                                "data": json.dumps({"content": content})
                            }
                        else:
                            print(f"⚠️ Content is not a string or is empty")

            elif "tools" in event:
                # Handle tool events from LangGraph
                tool_event_type = event["tools"].get("event")
                tool_data = event["tools"].get("data", {})

                if tool_event_type == "on_tool_start":
                    # Tool is starting execution
                    tool_name = tool_data.get("name", "unknown")
                    yield {
                        "event": "agent_step",
                        "data": json.dumps({
                            "step_type": "tool_call",
                            "content": f"Executing: {tool_name}",
                            "status": "running",
                            "timestamp": datetime.utcnow().isoformat(),
                            "metadata": {
                                "tool_name": tool_name,
                                "started_at": datetime.utcnow().isoformat()
                            }
                        })
                    }
                elif tool_event_type == "on_tool_end":
                    # Tool has completed
                    tool_name = event.get("name", "unknown")
                    output = tool_data.get("output", "")

                    # Try to parse and create readable summary
                    content_str = "Completed successfully"
                    duration_ms = None

                    try:
                        if isinstance(output, str):
                            result_data = json.loads(output)
                        else:
                            result_data = output

                        if isinstance(result_data, dict):
                            duration_ms = result_data.get("duration_ms")
                            if "rows" in result_data:
                                row_count = len(result_data["rows"])
                                content_str = f"Retrieved {row_count} rows"
                            elif "result" in result_data:
                                content_str = f"Result: {str(result_data['result'])[:100]}"
                    except:
                        content_str = str(output)[:100]

                    yield {
                        "event": "agent_step",
                        "data": json.dumps({
                            "step_type": "tool_result",
                            "content": content_str,
                            "status": "completed",
                            "timestamp": datetime.utcnow().isoformat(),
                            "metadata": {
                                "tool_name": tool_name,
                                "duration_ms": duration_ms
                            }
                        })
                    }

                # Also check for old-style tool messages (backwards compatibility)
                tool_messages = event["tools"].get("messages", [])
                for tool_msg in tool_messages:
                    if hasattr(tool_msg, "name"):
                        # Tool result (legacy format)
                        try:
                            result_data = json.loads(tool_msg.content) if isinstance(tool_msg.content, str) else tool_msg.content

                            # Extract duration if available
                            duration_ms = None
                            content_str = ""

                            if isinstance(result_data, dict):
                                duration_ms = result_data.get("duration_ms")
                                # Create a readable summary
                                if "rows" in result_data:
                                    row_count = len(result_data["rows"])
                                    content_str = f"Retrieved {row_count} rows"
                                elif "result" in result_data:
                                    content_str = f"Result: {str(result_data['result'])[:100]}"
                                else:
                                    content_str = f"Completed successfully"
                            else:
                                content_str = str(result_data)[:100]

                            yield {
                                "event": "agent_step",
                                "data": json.dumps({
                                    "step_type": "tool_result",
                                    "content": content_str,
                                    "status": "completed",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "metadata": {
                                        "tool_name": tool_msg.name,
                                        "duration_ms": duration_ms
                                    }
                                })
                            }
                        except:
                            # Fallback if parsing fails
                            yield {
                                "event": "agent_step",
                                "data": json.dumps({
                                    "step_type": "tool_result",
                                    "content": str(tool_msg.content)[:200],
                                    "status": "completed",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "metadata": {
                                        "tool_name": tool_msg.name
                                    }
                                })
                            }

        # Generate UI components from captured tool results if enabled
        ui_components = None
        tool_results_data = None
        render_mode = "markdown"

        if enable_generative_ui and accumulated_text:
            captured = agent.get_captured_tool_results()
            print(f"🎨 Captured tool results: {len(captured)} results")

            # Check if user explicitly requested visualization
            # Keywords: show, display, visualize, table, chart, graph, plot, list, draw
            viz_keywords = ['show me', 'display', 'visualize', 'create a table', 'show table',
                           'show data', 'list all', 'show chart', 'plot', 'graph', 'draw',
                           'create chart', 'create a chart', 'pie chart', 'bar chart', 'line chart']
            user_wants_viz = any(keyword in user_message.lower() for keyword in viz_keywords)

            print(f"🎨 User explicitly requested visualization: {user_wants_viz}")

            for idx, result in enumerate(captured):
                print(f"  Result {idx}: tool={result.get('tool_name')}, type={result.get('result_type')}")
                print(f"    Data keys: {result.get('result', {}).keys() if isinstance(result.get('result'), dict) else type(result.get('result'))}")
                if isinstance(result.get('result'), dict) and 'rows' in result.get('result', {}):
                    rows = result['result']['rows']
                    print(f"    Rows count: {len(rows)}, first row: {rows[0] if rows else 'empty'}")

            # Only generate UI components if user explicitly asked for visualization
            if user_wants_viz:
                # Filter out unknown/empty results
                valid_results = [r for r in captured if r.get('result_type') not in ['unknown', 'empty', 'error']]
                print(f"🎨 Valid results after filtering: {len(valid_results)}")

                if valid_results:
                    tool_results_data = valid_results
                    from api.services.component_generator import get_component_generator
                    generator = get_component_generator()
                    ui_component_models = generator.generate_from_dicts(valid_results, accumulated_text)
                    print(f"🎨 Generated {len(ui_component_models)} UI components")
                    for idx, comp in enumerate(ui_component_models):
                        print(f"  Component {idx}: type={comp.component_type}, props keys={comp.props.keys() if comp.props else 'none'}")
                        if comp.props and 'columns' in comp.props:
                            print(f"    Columns: {comp.props['columns']}")
                        if comp.props and 'rows' in comp.props:
                            print(f"    Rows count: {len(comp.props['rows'])}")

                    ui_components = [c.model_dump() for c in ui_component_models]
                    render_mode = "hybrid" if ui_components else "markdown"

                    # Stream each UI component to the frontend
                    for component in (ui_components or []):
                        print(f"📤 Streaming component: {component.get('component_type')}")
                        yield {
                            "event": "ui_component",
                            "data": json.dumps(component)
                        }
            else:
                print(f"🎨 Skipping UI component generation - user didn't request visualization")

        # Finalize agent steps: mark any "running" or "pending" steps as "completed"
        finalized_steps = []
        for step in agent.agent_steps:
            finalized_step = step.copy()
            if finalized_step.get("status") in ["running", "pending"]:
                finalized_step["status"] = "completed"
            finalized_steps.append(finalized_step)

        # Merge notebook sources + tool results for citations
        notebook_sources = context_info.get("sources", []) if context_info else []
        tool_results_for_citation = []
        if tool_results_data:
            # Add tool results as sources for citation
            for idx, tool_result in enumerate(tool_results_data):
                tool_results_for_citation.append({
                    "source_id": f"tool_{idx}",
                    "source_name": f"{tool_result.get('tool_name', 'Tool')} result",
                    "source_type": "tool_call",
                    "tool_name": tool_result.get('tool_name'),
                    "result_type": tool_result.get('result_type'),
                })

        # Merge both types
        all_sources = notebook_sources + tool_results_for_citation

        # Only store sources that were actually cited in the response
        # Extract citation numbers from the text using regex
        import re
        cited_indices = set()
        for match in re.finditer(r'\[(\d+)\]', accumulated_text):
            try:
                idx = int(match.group(1)) - 1  # Convert to 0-based index
                if 0 <= idx < len(all_sources):
                    cited_indices.add(idx)
            except ValueError:
                pass

        # Filter to only include actually-cited sources
        sources_to_store = [all_sources[i] for i in sorted(cited_indices)] if cited_indices else None

        # Save assistant message with generative UI data
        # IMPORTANT: Only save tool_results if NO ui_components were generated
        # UI components are the processed/visualized version of tool results,
        # so we don't want to duplicate the display by showing both
        if accumulated_text:
            await session.add_message(
                "assistant",
                accumulated_text,
                ui_components=ui_components,
                render_mode=render_mode,
                tool_results=tool_results_data if not ui_components else None,
                agent_steps=finalized_steps,
                langfuse_trace_id=agent.langfuse_trace_id,
                sources=sources_to_store,  # Only store actually-cited sources
            )

        # Flush observability events
        obs_manager = get_observability_manager()
        obs_manager.flush()

        # Send completion
        sources_to_send = context_info.get("sources", []) if context_info else []
        yield {
            "event": "done",
            "data": json.dumps({
                "total_tokens": len(accumulated_text.split()),
                "sources": sources_to_send,
                "render_mode": render_mode,
                "ui_components_count": len(ui_components) if ui_components else 0,
            })
        }

    except Exception as e:
        import traceback
        print(f"❌ Agent streaming error: {e}")
        print(traceback.format_exc())
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)})
        }


async def stream_chat_response(
    session: ChatSession,
    user_message: str,
    system_message: Optional[str],
    context_info: Optional[dict],
    hana_tools: Optional[List[dict]] = None,
    tool_metadata_map: Optional[Dict[str, dict]] = None
):
    """
    Stream chat response using Server-Sent Events with real-time LLM streaming.

    Supports HANA tool calling for live database queries.

    Args:
        session: Chat session
        user_message: User's message
        system_message: Optional system message with context
        context_info: Context information to include in metadata
        hana_tools: Optional list of HANA query tools
        tool_metadata_map: Metadata for executing tools

    Yields:
        SSE events with response chunks
    """
    try:
        import httpx
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store

        # Get conversation history
        messages = await ChatMessage.get_recent_context(session.id, max_messages=10)

        # Build messages for LLM
        llm_messages = []

        if system_message:
            llm_messages.append({"role": "system", "content": system_message})

        llm_messages.extend(messages[:-1] if messages else [])
        llm_messages.append({"role": "user", "content": user_message})

        # Send initial metadata event
        yield {
            "event": "metadata",
            "data": json.dumps({
                "session_id": session.id,
                "context_info": context_info
            })
        }

        print(f"[Chat Stream] Starting stream for session {session.id}")
        print(f"[Chat Stream] Context sources: {len(context_info.get('sources', [])) if context_info else 0}")
        print(f"[Chat Stream] HANA tools received: {len(hana_tools) if hana_tools else 0}")
        print(f"[Chat Stream] Tool metadata map: {len(tool_metadata_map) if tool_metadata_map else 0}")

        # Get configured model
        language_model_id = await get_setting("language_model_id", "")
        model_id = session.model_override or language_model_id

        if not model_id:
            yield {
                "event": "error",
                "data": json.dumps({"error": "No AI model configured"})
            }
            return

        credential = _credentials_store.get(model_id)
        if not credential:
            yield {
                "event": "error",
                "data": json.dumps({"error": "No AI model configured"})
            }
            return

        # Detect provider
        is_anthropic = "anthropic" in credential["model_name"].lower() or "claude" in credential["model_name"].lower()

        accumulated_text = ""

        if is_anthropic:
            # Stream from Anthropic
            anthropic_messages = []
            system_content = None

            for msg in llm_messages:
                if msg["role"] == "system":
                    system_content = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

            request_payload = {
                "model": credential["model_name"],
                "messages": anthropic_messages,
                "max_tokens": 2000,
                "temperature": 0.7,
                "stream": True
            }

            if system_content:
                request_payload["system"] = system_content

            # Add HANA tools if available
            if hana_tools:
                request_payload["tools"] = hana_tools
                print(f"[Chat Stream] 🔧 Including {len(hana_tools)} HANA tools in streaming request")

            endpoint_url = f"{credential['base_url'].replace('/litellm/v1', '')}/anthropic/v1/messages"

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    endpoint_url,
                    headers={
                        "x-api-key": credential['api_key'],
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json=request_payload
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": f"AI error: {error_text.decode()[:200]}"})
                        }
                        return

                    # Track tool use
                    tool_use_blocks = []
                    current_tool_use = None

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break

                            try:
                                data = json.loads(data_str)

                                # Handle different event types
                                if data.get("type") == "content_block_start":
                                    # Check if this is a tool use block
                                    content_block = data.get("content_block", {})
                                    if content_block.get("type") == "tool_use":
                                        current_tool_use = {
                                            "id": content_block.get("id"),
                                            "name": content_block.get("name"),
                                            "input": ""
                                        }
                                        print(f"[Chat Stream] 🔧 Tool call detected: {current_tool_use['name']}")

                                elif data.get("type") == "content_block_delta":
                                    delta = data.get("delta", {})

                                    # Text content
                                    if delta.get("type") == "text_delta":
                                        chunk = delta.get("text", "")
                                        if chunk:
                                            accumulated_text += chunk
                                            yield {
                                                "event": "chunk",
                                                "data": json.dumps({"content": chunk})
                                            }
                                            print(f"[Chat Stream] Chunk: {len(chunk)} chars", end="\r")

                                    # Tool input (streamed JSON)
                                    elif delta.get("type") == "input_json_delta" and current_tool_use:
                                        current_tool_use["input"] += delta.get("partial_json", "")

                                elif data.get("type") == "content_block_stop":
                                    # Tool use block completed
                                    if current_tool_use:
                                        # Parse the accumulated input
                                        try:
                                            current_tool_use["input"] = json.loads(current_tool_use["input"])
                                        except:
                                            pass
                                        tool_use_blocks.append(current_tool_use)
                                        current_tool_use = None

                                elif data.get("type") == "message_stop":
                                    # Check if we need to execute tools
                                    if tool_use_blocks:
                                        print(f"\n[Chat Stream] Executing {len(tool_use_blocks)} tool(s)")
                                        # Stop streaming, execute tools, and restart
                                        break

                            except json.JSONDecodeError:
                                continue

                # If tools were called, execute them and make another request
                if tool_use_blocks:
                    print(f"[Chat Stream] Processing {len(tool_use_blocks)} tool call(s)")

                    from api.services.hana_tool_executor import HANAToolExecutor

                    # Execute each tool
                    tool_results = []
                    for tool_use in tool_use_blocks:
                        tool_name = tool_use["name"]
                        tool_id = tool_use["id"]
                        tool_input = tool_use["input"]

                        metadata = tool_metadata_map.get(tool_name) if tool_metadata_map else None

                        if not metadata:
                            print(f"⚠️ No metadata for tool {tool_name}")
                            continue

                        try:
                            # Execute tool
                            tool_call = {
                                "id": tool_id,
                                "function": {"name": tool_name},
                                "arguments": tool_input
                            }
                            results = await HANAToolExecutor.execute_tool(tool_call, metadata)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": json.dumps(results, default=str)
                            })

                            print(f"✅ Tool {tool_name} returned {len(results)} rows")

                        except Exception as e:
                            print(f"❌ Tool error: {str(e)}")
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": f"Error: {str(e)}",
                                "is_error": True
                            })

                    # Build second request with tool results
                    # Add assistant's tool use message
                    anthropic_messages.append({
                        "role": "assistant",
                        "content": [{"type": "tool_use", "id": tu["id"], "name": tu["name"], "input": tu["input"]} for tu in tool_use_blocks]
                    })

                    # Add tool results as user message
                    anthropic_messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Make second streaming request with tool results
                    request_payload["messages"] = anthropic_messages

                    print(f"[Chat Stream] Making second request with tool results")

                    async with client.stream(
                        "POST",
                        endpoint_url,
                        headers={
                            "x-api-key": credential['api_key'],
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        },
                        json=request_payload
                    ) as response2:
                        if response2.status_code != 200:
                            error_text = await response2.aread()
                            yield {
                                "event": "error",
                                "data": json.dumps({"error": f"AI error in second request: {error_text.decode()[:200]}"})
                            }
                            return

                        async for line in response2.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str == "[DONE]":
                                    break

                                try:
                                    data = json.loads(data_str)
                                    if data.get("type") == "content_block_delta":
                                        delta = data.get("delta", {})
                                        if delta.get("type") == "text_delta":
                                            chunk = delta.get("text", "")
                                            if chunk:
                                                accumulated_text += chunk
                                                yield {
                                                    "event": "chunk",
                                                    "data": json.dumps({"content": chunk})
                                                }
                                                print(f"[Chat Stream] Chunk: {len(chunk)} chars", end="\r")
                                except json.JSONDecodeError:
                                    continue

        else:
            # Stream from OpenAI-compatible endpoint
            request_payload = {
                "model": credential["model_name"],
                "messages": llm_messages,
                "temperature": 0.7,
                "max_tokens": 2000,
                "stream": True
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{credential['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {credential['api_key']}",
                        "Content-Type": "application/json"
                    },
                    json=request_payload
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": f"AI error: {error_text.decode()[:200]}"})
                        }
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break

                            try:
                                data = json.loads(data_str)
                                chunk = data["choices"][0]["delta"].get("content", "")
                                if chunk:
                                    accumulated_text += chunk
                                    yield {
                                        "event": "chunk",
                                        "data": json.dumps({"content": chunk})
                                    }
                                    print(f"[Chat Stream] Chunk: {len(chunk)} chars", end="\r")
                            except (json.JSONDecodeError, KeyError, IndexError):
                                continue

        # Save the complete assistant message with sources
        notebook_sources = context_info.get("sources", []) if context_info else []

        # Only store sources that were actually cited in the response
        import re
        cited_indices = set()
        for match in re.finditer(r'\[(\d+)\]', accumulated_text):
            try:
                idx = int(match.group(1)) - 1  # Convert to 0-based index
                if 0 <= idx < len(notebook_sources):
                    cited_indices.add(idx)
            except ValueError:
                pass

        # Filter to only include actually-cited sources
        sources_to_store = [notebook_sources[i] for i in sorted(cited_indices)] if cited_indices else None

        assistant_message = await session.add_message(
            "assistant",
            accumulated_text,
            sources=sources_to_store
        )

        sources_to_send = sources_to_store or []
        print(f"\n[Chat Stream] Complete! {len(accumulated_text)} chars, {len(sources_to_send)} sources")

        # Send completion event with sources
        yield {
            "event": "done",
            "data": json.dumps({
                "message_id": assistant_message.id,
                "total_tokens": len(accumulated_text.split()),
                "sources": sources_to_send
            })
        }

    except Exception as e:
        import traceback
        print(f"❌ Streaming error: {e}")
        print(traceback.format_exc())
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)})
        }


# ============================================================================
# Orchestrated Multi-Agent Chat Endpoint
# ============================================================================

@router.get("/sessions/{session_id}/deep-research-status")
async def get_deep_research_status(session_id: str):
    """
    Get status of any running deep research jobs for this session.
    Returns the most recent job status.
    """
    from api.routers.deep_research import _research_jobs

    # Find jobs for this session
    session_jobs = [
        job for job in _research_jobs.values()
        if job.get("session_id") == session_id
    ]

    if not session_jobs:
        return {"status": "no_jobs", "jobs": []}

    # Sort by created time, most recent first
    session_jobs.sort(key=lambda x: x.get("created", ""), reverse=True)

    return {
        "status": "ok",
        "jobs": session_jobs,
        "latest": session_jobs[0] if session_jobs else None
    }



async def send_orchestrated_message(session_id: str, request: OrchestratedChatRequest):
    """
    Send a message using multi-agent orchestration.

    Spawns a team of specialized agents that collaborate to produce a
    comprehensive response. Supports SSE streaming of agent progress.

    SSE Events:
    - **metadata** - Session and team info at start
    - **agent_start** - When an agent begins working
    - **agent_step** - Progress updates from agents (thinking, tool_call, tool_result)
    - **agent_done** - When an agent completes its task
    - **chunk** - Final synthesized response chunks
    - **done** - Completion with summary metadata
    - **error** - Error information

    Example:
        POST /api/chat/sessions/sess-123/messages/orchestrated
        {
            "message": "Analyze the sales data and create a summary report",
            "stream": true,
            "max_iterations": 5
        }
    """
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}",
        )

    notebook = await Notebook.get(session.notebook_id)
    if not notebook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notebook not found: {session.notebook_id}",
        )

    # Save user message
    user_message = await session.add_message("user", request.message)

    if request.stream:
        return EventSourceResponse(
            _stream_orchestrated_response(
                session=session,
                notebook=notebook,
                user_message_text=request.message,
                request=request,
            )
        )

    # Non-streaming: run orchestration and return final result
    final_text = await _run_orchestrated_chat(
        session=session,
        notebook=notebook,
        user_message_text=request.message,
        request=request,
    )

    assistant_message = await session.add_message("assistant", final_text)

    return ChatResponse(
        session_id=session.id,
        user_message=ChatMessageResponse(
            id=user_message.id,
            session_id=user_message.session_id,
            role=user_message.role,
            content=user_message.content,
            created=user_message.created,
        ),
        assistant_message=ChatMessageResponse(
            id=assistant_message.id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            created=assistant_message.created,
        ),
        context_info=None,
    )


async def _run_orchestrated_chat(
    session: ChatSession,
    notebook: Notebook,
    user_message_text: str,
    request: OrchestratedChatRequest,
) -> str:
    """
    Run multi-agent orchestration (non-streaming).

    Delegates to a planner agent that decomposes the query,
    assigns sub-tasks to specialist agents, and synthesizes results.
    """
    from api.services.settings import get_setting
    from api.routers.credentials import _credentials_store

    language_model_id = await get_setting("language_model_id", "")
    model_name = session.model_override or language_model_id

    if not model_name:
        return "No language model configured. Please select a model in Settings."

    credential = get_model_credential(model_name)
    if not credential:
        return "Model credential not found. Please configure a model."

    actual_model_name = credential["model_name"]
    base_url = credential.get("base_url", "https://api.openai.com/v1")
    api_key = credential.get("api_key")

    # Build context
    context_text = ""
    if request.include_context:
        try:
            context_service = get_context_service(max_tokens=4000, model="gpt-4")
            context_data = await context_service.build_notebook_context(
                notebook_id=session.notebook_id,
                selected_source_ids=request.selected_source_ids,
                include_notes=True  # Include notes (especially final deliverable) in context
            )
            context_text = context_data.get("content", "")
        except Exception as e:
            print(f"[Orchestrated] Context error: {e}")

    # Get tools
    from api.services.tool_factory import get_tool_factory
    factory = get_tool_factory()
    user_id = getattr(session, "user_id", None) or "default"
    tools = await factory.create_tools_for_session(
        notebook_id=session.notebook_id,
        user_id=user_id,
        session_id=session.id,
    )

    # Use DataQueryAgent as the backbone with orchestration prompt
    from open_notebook.agents.data_query_agent import DataQueryAgent

    orchestration_prompt = f"""You are an orchestrating AI assistant working on notebook "{notebook.name}".

You have multiple capabilities and should approach complex queries step-by-step:
1. Analyze the query to understand what information is needed
2. Use available tools to gather data
3. Synthesize findings into a comprehensive response

Context from notebook:
{context_text if context_text else "No context available."}

Respond thoroughly and cite your sources."""

    agent = DataQueryAgent(
        model_name=actual_model_name,
        notebook_id=session.notebook_id,
        tools=tools,
        session_id=session.id,
        system_message=orchestration_prompt,
        capture_tool_results=True,
    )

    # Get chat history
    chat_history = await session.get_messages()
    history_dicts = [
        {"role": msg.role, "content": msg.content}
        for msg in chat_history[:-1]
    ] if len(chat_history) > 1 else []

    response_text = await agent.invoke(user_message_text, history_dicts)
    return response_text


async def _stream_orchestrated_response(
    session: ChatSession,
    notebook: Notebook,
    user_message_text: str,
    request: OrchestratedChatRequest,
):
    """
    Stream multi-agent orchestrated response via SSE.

    Emits agent lifecycle events so the frontend can visualize
    which agents are active, what tools they're calling, and the
    final synthesized response.
    """
    from api.services.settings import get_setting
    from api.routers.credentials import _credentials_store

    accumulated_text = ""

    try:
        # Send initial metadata
        yield {
            "event": "metadata",
            "data": json.dumps({
                "session_id": session.id,
                "notebook_id": session.notebook_id,
                "orchestration_mode": True,
                "max_iterations": request.max_iterations,
            }),
        }

        language_model_id = await get_setting("language_model_id", "")
        model_name = session.model_override or language_model_id

        if not model_name:
            yield {
                "event": "error",
                "data": json.dumps({"error": "No language model configured"}),
            }
            return

        credential = get_model_credential(model_name)
        if not credential:
            yield {
                "event": "error",
                "data": json.dumps({"error": "Model credential not found"}),
            }
            return

        actual_model_name = credential["model_name"]

        # Signal planner starting
        yield {
            "event": "agent_start",
            "data": json.dumps({
                "agent_role": "planner",
                "content": "Analyzing query and planning approach...",
                "timestamp": datetime.utcnow().isoformat(),
            }),
        }

        # Build context
        context_text = ""
        if request.include_context:
            try:
                context_service = get_context_service(max_tokens=4000, model="gpt-4")
                context_data = await context_service.build_notebook_context(
                    notebook_id=session.notebook_id,
                    selected_source_ids=request.selected_source_ids,
                    include_notes=True  # Include notes (especially final deliverable) in context
                )
                context_text = context_data.get("content", "")
            except Exception as e:
                print(f"[Orchestrated Stream] Context error: {e}")

        # Get tools
        from api.services.tool_factory import get_tool_factory
        factory = get_tool_factory()
        user_id = getattr(session, "user_id", None) or "default"
        tools = await factory.create_tools_for_session(
            notebook_id=session.notebook_id,
            user_id=user_id,
            session_id=session.id,
        )

        yield {
            "event": "agent_step",
            "data": json.dumps({
                "step_type": "thinking",
                "agent_role": "planner",
                "content": f"Found {len(tools)} tools. Preparing orchestrated response...",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
            }),
        }

        # Signal researcher/analyst starting
        yield {
            "event": "agent_start",
            "data": json.dumps({
                "agent_role": "researcher",
                "content": "Gathering information from sources...",
                "timestamp": datetime.utcnow().isoformat(),
            }),
        }

        # Use DataQueryAgent for the actual work
        from open_notebook.agents.data_query_agent import DataQueryAgent

        orchestration_prompt = f"""You are an orchestrating AI assistant working on notebook "{notebook.name}".

You have multiple capabilities and should approach complex queries step-by-step:
1. Analyze the query to understand what information is needed
2. Use available tools to gather data
3. Synthesize findings into a comprehensive response

Context from notebook:
{context_text if context_text else "No context available."}

Respond thoroughly and cite your sources."""

        agent = DataQueryAgent(
            model_name=actual_model_name,
            notebook_id=session.notebook_id,
            tools=tools,
            session_id=session.id,
            system_message=orchestration_prompt,
            capture_tool_results=True,
        )

        chat_history = await session.get_messages()
        history_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in chat_history[:-1]
        ] if len(chat_history) > 1 else []

        # Stream agent execution
        async for event in agent.stream_response(user_message_text, history_dicts):
            if "agent" in event:
                messages = event["agent"].get("messages", [])
                if messages:
                    last_message = messages[-1]

                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                        for tool_call in last_message.tool_calls:
                            tool_name = tool_call.get("name", "unknown")
                            yield {
                                "event": "agent_step",
                                "data": json.dumps({
                                    "step_type": "tool_call",
                                    "agent_role": "researcher",
                                    "content": f"Querying: {tool_name}",
                                    "status": "running",
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "metadata": {"tool_name": tool_name},
                                }),
                            }

                    elif hasattr(last_message, "content") and last_message.content:
                        content = last_message.content
                        if isinstance(content, str) and content:
                            accumulated_text += content
                            yield {
                                "event": "chunk",
                                "data": json.dumps({"content": content}),
                            }

            elif "tools" in event:
                tool_messages = event["tools"].get("messages", [])
                for tool_msg in tool_messages:
                    if hasattr(tool_msg, "name"):
                        yield {
                            "event": "agent_step",
                            "data": json.dumps({
                                "step_type": "tool_result",
                                "agent_role": "researcher",
                                "content": f"Completed: {tool_msg.name}",
                                "status": "completed",
                                "timestamp": datetime.utcnow().isoformat(),
                                "metadata": {"tool_name": tool_msg.name},
                            }),
                        }

        # Signal agents done
        yield {
            "event": "agent_done",
            "data": json.dumps({
                "agent_role": "researcher",
                "timestamp": datetime.utcnow().isoformat(),
            }),
        }

        yield {
            "event": "agent_done",
            "data": json.dumps({
                "agent_role": "planner",
                "timestamp": datetime.utcnow().isoformat(),
            }),
        }

        # Save assistant message
        if accumulated_text:
            assistant_msg = await session.add_message(
                "assistant",
                accumulated_text,
                agent_steps=agent.agent_steps,
            )

        # Send completion
        yield {
            "event": "done",
            "data": json.dumps({
                "message_id": assistant_msg.id if accumulated_text else None,
                "orchestration_complete": True,
                "total_tokens": len(accumulated_text.split()),
            }),
        }

    except Exception as e:
        import traceback
        print(f"[Orchestrated Stream] Error: {e}")
        traceback.print_exc()
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)}),
        }
