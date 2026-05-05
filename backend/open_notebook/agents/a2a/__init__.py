"""
A2A Protocol Integration Package

Provides Agent-to-Agent (A2A) protocol support for:
- Exposing local skills as A2A-accessible endpoints
- Discovering and invoking remote A2A agents
- Bidirectional agent communication via standard protocol
"""

from open_notebook.agents.a2a.agent_card import AgentCardGenerator
from open_notebook.agents.a2a.message_handler import A2AMessageHandler
from open_notebook.agents.a2a.task_manager import A2ATaskManager
from open_notebook.agents.a2a.discovery import A2ADiscoveryClient
from open_notebook.agents.a2a.client import OpenNotebookA2AClient
from open_notebook.agents.a2a.skill_adapter import RemoteSkillAdapter, RemoteSkillRegistry

__all__ = [
    "AgentCardGenerator",
    "A2AMessageHandler",
    "A2ATaskManager",
    "A2ADiscoveryClient",
    "OpenNotebookA2AClient",
    "RemoteSkillAdapter",
    "RemoteSkillRegistry",
]
