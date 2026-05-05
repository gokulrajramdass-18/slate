"""
Chat domain models.

Includes ChatSession and ChatMessage entities for managing conversations.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from open_notebook.database.repository import repo_create, repo_query, repo_update
from open_notebook.domain.base import ObjectModel


class ChatSession(ObjectModel):
    """
    ChatSession represents a conversation with AI about notebook content.

    Each session is associated with a notebook and contains multiple messages.
    """

    _table_name = "chat_sessions"
    model_config = {"protected_namespaces": ()}

    title: Optional[str] = "New Chat"
    notebook_id: str
    model_override: Optional[str] = None  # Optional AI model override for this session
    created_by: Optional[str] = None  # User ID who created the session

    async def get_messages(self) -> List["ChatMessage"]:
        """
        Get all messages in this chat session.

        Returns:
            List of ChatMessage instances ordered by creation time
        """
        if self.id is None:
            return []

        sql = """
            SELECT *
            FROM chat_messages
            WHERE session_id = :session_id
            ORDER BY created ASC
        """

        results = await repo_query(sql, {"session_id": self.id})
        return [ChatMessage(**row) for row in results]

    async def add_message(
        self,
        role: str,
        content: str,
        sources: Optional[List[Dict[str, Any]]] = None,
        ui_components: Optional[List[Dict[str, Any]]] = None,
        render_mode: Optional[str] = "markdown",
        tool_results: Optional[List[Dict[str, Any]]] = None,
        agent_steps: Optional[List[Dict[str, Any]]] = None,
        langfuse_trace_id: Optional[str] = None,
    ) -> "ChatMessage":
        """
        Add a message to this chat session.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            sources: Optional list of sources used for citations (notebook sources + tool results)
            ui_components: Optional list of UI component specs for generative UI
            render_mode: Render mode hint (markdown, generative_ui, hybrid)
            tool_results: Optional list of tool execution results
            agent_steps: Optional list of agent execution steps
            langfuse_trace_id: Optional Langfuse trace ID for observability

        Returns:
            Created ChatMessage instance
        """
        if self.id is None:
            raise ValueError("Cannot add message to unsaved chat session")

        message = ChatMessage(
            session_id=self.id,
            role=role,
            content=content,
            sources=json.dumps(sources) if sources else None,
            ui_components=json.dumps(ui_components) if ui_components else None,
            render_mode=render_mode,
            tool_results=json.dumps(tool_results) if tool_results else None,
            agent_steps=json.dumps(agent_steps) if agent_steps else None,
            langfuse_trace_id=langfuse_trace_id,
        )

        await message.save()

        # Update session timestamp
        self.updated = datetime.utcnow()
        await repo_update(
            self._table_name,
            self.id,
            {"updated": self.updated},
        )

        return message

    async def get_message_count(self) -> int:
        """
        Get the count of messages in this session.

        Returns:
            Number of messages
        """
        if self.id is None:
            return 0

        sql = """
            SELECT COUNT(*) as count
            FROM chat_messages
            WHERE session_id = :session_id
        """

        results = await repo_query(sql, {"session_id": self.id})
        return results[0]["count"] if results else 0

    async def delete(self) -> None:
        """
        Delete the chat session and all its messages.

        Messages are cascade deleted via foreign key constraints.
        """
        if self.id is None:
            raise ValueError("Cannot delete unsaved chat session")

        from open_notebook.database.repository import repo_delete

        await repo_delete(self._table_name, self.id)

    @classmethod
    async def get_by_notebook(cls, notebook_id: str) -> List["ChatSession"]:
        """
        Get all chat sessions for a notebook.

        Args:
            notebook_id: Notebook ID

        Returns:
            List of ChatSession instances ordered by most recent first
        """
        sql = """
            SELECT *
            FROM chat_sessions
            WHERE notebook_id = :notebook_id
            ORDER BY updated DESC
        """

        results = await repo_query(sql, {"notebook_id": notebook_id})
        return [cls(**row) for row in results]


class ChatMessage(ObjectModel):
    """
    ChatMessage represents a single message in a chat session.

    Roles:
    - user: Message from the user
    - assistant: Response from the AI
    - system: System message (e.g., context, instructions)
    """

    _table_name = "chat_messages"
    _exclude_fields = ["updated"]  # chat_messages table doesn't have 'updated' field

    session_id: str
    role: str  # user, assistant, system
    content: str
    sources: Optional[str] = None  # JSON array of source citations
    ui_components: Optional[str] = None  # JSON array of UIComponentData
    render_mode: Optional[str] = "markdown"  # markdown, generative_ui, hybrid
    tool_results: Optional[str] = None  # JSON array of ToolResultData
    agent_steps: Optional[str] = None  # JSON array of agent execution steps
    langfuse_trace_id: Optional[str] = None  # Langfuse trace ID for observability
    langfuse_observation_id: Optional[str] = None  # Langfuse observation ID

    async def get_session(self) -> Optional[ChatSession]:
        """
        Get the chat session this message belongs to.

        Returns:
            ChatSession instance or None
        """
        if self.session_id is None:
            return None

        return await ChatSession.get(self.session_id)

    def get_ui_components(self) -> Optional[List[Dict[str, Any]]]:
        """Parse ui_components JSON string into a list of dicts."""
        if not self.ui_components:
            return None
        try:
            return json.loads(self.ui_components)
        except (json.JSONDecodeError, TypeError):
            return None

    def get_sources(self) -> Optional[List[Dict[str, Any]]]:
        """Parse sources JSON string into a list of dicts."""
        if not self.sources:
            return None
        try:
            return json.loads(self.sources)
        except (json.JSONDecodeError, TypeError):
            return None

    def get_tool_results(self) -> Optional[List[Dict[str, Any]]]:
        """Parse tool_results JSON string into a list of dicts."""
        if not self.tool_results:
            return None
        try:
            return json.loads(self.tool_results)
        except (json.JSONDecodeError, TypeError):
            return None

    def get_agent_steps(self) -> List[Dict[str, Any]]:
        """
        Parse agent_steps JSON string into a list of step dicts.

        Returns:
            List of agent step dicts, empty list if None or invalid JSON
        """
        if not self.agent_steps:
            return []
        try:
            return json.loads(self.agent_steps)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_agent_steps(self, steps: List[Dict[str, Any]]) -> None:
        """
        Set agent steps from a list of step dicts.

        Args:
            steps: List of agent step dictionaries
        """
        if steps:
            self.agent_steps = json.dumps(steps)
        else:
            self.agent_steps = None

    @classmethod
    async def get_by_session(
        cls, session_id: str, limit: Optional[int] = None
    ) -> List["ChatMessage"]:
        """
        Get messages for a chat session.

        Args:
            session_id: Chat session ID
            limit: Optional limit on number of messages (most recent)

        Returns:
            List of ChatMessage instances ordered chronologically
        """
        sql = """
            SELECT *
            FROM chat_messages
            WHERE session_id = :session_id
            ORDER BY created ASC
        """

        if limit:
            sql += f" LIMIT {limit}"

        results = await repo_query(sql, {"session_id": session_id})
        return [cls(**row) for row in results]

    @classmethod
    async def get_recent_context(
        cls, session_id: str, max_messages: int = 10
    ) -> List[Dict[str, str]]:
        """
        Get recent messages formatted for LLM context.

        Args:
            session_id: Chat session ID
            max_messages: Maximum number of recent messages to retrieve

        Returns:
            List of message dicts with 'role' and 'content' keys
        """
        messages = await cls.get_by_session(session_id, limit=max_messages)

        return [
            {
                "role": msg.role,
                "content": msg.content,
            }
            for msg in messages
        ]
