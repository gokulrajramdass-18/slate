"""
Agents package for Open Notebook

Contains LangGraph agents for various workflows including data querying,
deep research, query analysis, planning, persistent memory, and
multi-agent team coordination.
"""

from open_notebook.agents.memory_system import (
    Memory,
    MemoryStore,
    MemoryType,
    get_memory_store,
)

from open_notebook.agents.query_analyzer import (
    QueryAnalyzer,
    QueryAnalysis,
    QueryComplexity,
    QueryIntent,
    ResourceEstimate,
)
from open_notebook.agents.planner_agent import (
    PlannerAgent,
    ExecutionPlan,
    SubTask,
    TaskStatus,
    AgentRole,
)

from open_notebook.agents.base_agent import AgentStatus, BaseAgent
from open_notebook.agents.llm_pool import LLMClientPool
from open_notebook.agents.messaging import MessageBus
from open_notebook.agents.task_manager import TaskManager, DependencyCycleError
from open_notebook.agents.agent_manager import (
    AgentManager,
    register_agent,
    get_agent_class,
)
