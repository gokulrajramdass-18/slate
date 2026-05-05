"""
Dashboard Analytics API Router

Provides comprehensive platform statistics and real-time WebSocket updates for the analytics dashboard.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel

from open_notebook.database.repository import repo_query
from api.services.database_service import get_database_service


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ============================================================================
# Stats Cache (30-second TTL)
# ============================================================================

_stats_cache: Dict[str, Any] = {}
_cache_time: Optional[datetime] = None
_cache_ttl_seconds = 30


def _clear_cache():
    """Clear the stats cache"""
    global _stats_cache, _cache_time
    _stats_cache = {}
    _cache_time = None


def _is_cache_valid() -> bool:
    """Check if cache is still valid"""
    if not _cache_time:
        return False
    return (datetime.utcnow() - _cache_time).total_seconds() < _cache_ttl_seconds


# ============================================================================
# Response Models
# ============================================================================

class HeroMetrics(BaseModel):
    pending_approvals: int
    active_agents: int
    scheduled_runs_today: int
    ai_usage_today: int


class WorkflowStats(BaseModel):
    total: int
    active: int
    executions_last_7_days: int
    success_rate: float
    by_trigger: Dict[str, int]
    recent_executions: List[Dict[str, Any]]


class AgentStats(BaseModel):
    total_teams: int
    active_teams: int
    total_agents: int
    agents_by_role: Dict[str, int]
    task_completion_rate: float
    active_tasks: int
    completed_tasks_today: int


class ApprovalStats(BaseModel):
    pending_count: int
    pending_items: List[Dict[str, Any]]
    avg_response_time_minutes: float
    approval_rate: float


class ScheduleStats(BaseModel):
    total_schedules: int
    enabled: int
    disabled: int
    next_runs: List[Dict[str, Any]]
    runs_today: int
    successful_runs_today: int


class WorkspaceStats(BaseModel):
    total: int
    active: int
    archived: int
    total_sources: int
    sources_by_type: Dict[str, int]


class MicrositeStats(BaseModel):
    total: int
    active: int
    total_views: int
    unique_users: int
    most_viewed: List[Dict[str, Any]]


class AIUsageStats(BaseModel):
    tool_calls_today: int
    chat_messages_today: int
    top_tools: List[Dict[str, Any]]
    avg_execution_time_ms: float


class NotificationStats(BaseModel):
    unread_count: int
    by_type: Dict[str, int]


class SystemStats(BaseModel):
    db_type: str
    total_records: int
    last_backup: Optional[str]
    uptime_hours: float


class DashboardStatsResponse(BaseModel):
    hero_metrics: HeroMetrics
    workflows: WorkflowStats
    agents: AgentStats
    approvals: ApprovalStats
    schedules: ScheduleStats
    workspaces: WorkspaceStats
    microsites: MicrositeStats
    ai_usage: AIUsageStats
    notifications: NotificationStats
    system: SystemStats


# ============================================================================
# WebSocket Connection Manager
# ============================================================================

class DashboardConnectionManager:
    """Manages WebSocket connections for dashboard real-time updates"""

    def __init__(self):
        # user_id -> list of websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """Connect a new WebSocket client"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        """Disconnect a WebSocket client"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_to_user(self, user_id: str, message: dict):
        """Send message to all connections for a specific user"""
        if user_id in self.active_connections:
            dead_connections = []
            for websocket in self.active_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    dead_connections.append(websocket)

            # Clean up dead connections
            for websocket in dead_connections:
                self.disconnect(user_id, websocket)

    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all connected clients"""
        for user_id in list(self.active_connections.keys()):
            await self.broadcast_to_user(user_id, message)


# Global connection manager
dashboard_manager = DashboardConnectionManager()


# ============================================================================
# Stats Aggregation Functions
# ============================================================================

async def _get_hero_metrics() -> HeroMetrics:
    """Get hero metrics for dashboard top banner"""
    try:
        # Pending approvals
        approvals = await repo_query(
            "SELECT COUNT(*) as count FROM workflow_approvals WHERE status = 'pending'"
        )
        pending_approvals = approvals[0]["count"] if approvals else 0

        # Active agents (teams with running status)
        agents = await repo_query(
            "SELECT COUNT(*) as count FROM agent_teams WHERE status = 'running'"
        )
        active_agents = agents[0]["count"] if agents else 0

        # Scheduled runs today
        scheduled = await repo_query(
            """
            SELECT COUNT(*) as count FROM workflow_executions
            WHERE DATE(started_at) = DATE('now')
            AND triggered_by IN ('cron', 'event', 'dependency')
            """
        )
        scheduled_runs_today = scheduled[0]["count"] if scheduled else 0

        # AI usage today (tool calls)
        ai_usage = await repo_query(
            "SELECT COUNT(*) as count FROM tool_usage_log WHERE DATE(created) = DATE('now')"
        )
        ai_usage_today = ai_usage[0]["count"] if ai_usage else 0

        return HeroMetrics(
            pending_approvals=pending_approvals,
            active_agents=active_agents,
            scheduled_runs_today=scheduled_runs_today,
            ai_usage_today=ai_usage_today
        )
    except Exception as e:
        print(f"Error getting hero metrics: {e}")
        return HeroMetrics(
            pending_approvals=0,
            active_agents=0,
            scheduled_runs_today=0,
            ai_usage_today=0
        )


async def _get_workflow_stats() -> WorkflowStats:
    """Get workflow statistics"""
    try:
        # Total workflows
        total = await repo_query("SELECT COUNT(*) as count FROM workflows WHERE is_active = 1")
        total_count = total[0]["count"] if total else 0

        # Active workflows (with recent executions)
        active = await repo_query(
            """
            SELECT COUNT(DISTINCT workflow_id) as count FROM workflow_executions
            WHERE started_at >= datetime('now', '-24 hours')
            """
        )
        active_count = active[0]["count"] if active else 0

        # Executions last 7 days
        executions = await repo_query(
            "SELECT COUNT(*) as count FROM workflow_executions WHERE started_at >= datetime('now', '-7 days')"
        )
        executions_count = executions[0]["count"] if executions else 0

        # Success rate
        success = await repo_query(
            """
            SELECT
                COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as rate
            FROM workflow_executions
            WHERE started_at >= datetime('now', '-7 days')
            """
        )
        success_rate = success[0]["rate"] if success and success[0]["rate"] else 0.0

        # By trigger type
        by_trigger = await repo_query(
            """
            SELECT triggered_by, COUNT(*) as count
            FROM workflow_executions
            WHERE started_at >= datetime('now', '-7 days')
            GROUP BY triggered_by
            """
        )
        trigger_dict = {row["triggered_by"] or "manual": row["count"] for row in by_trigger}

        # Recent executions
        recent = await repo_query(
            """
            SELECT
                e.id, e.workflow_id, w.name as workflow_name, e.status, e.started_at, e.completed_at
            FROM workflow_executions e
            LEFT JOIN workflows w ON e.workflow_id = w.id
            ORDER BY e.started_at DESC
            LIMIT 5
            """
        )
        recent_list = [dict(row) for row in recent]

        return WorkflowStats(
            total=total_count,
            active=active_count,
            executions_last_7_days=executions_count,
            success_rate=round(success_rate, 1),
            by_trigger=trigger_dict,
            recent_executions=recent_list
        )
    except Exception as e:
        print(f"Error getting workflow stats: {e}")
        return WorkflowStats(
            total=0,
            active=0,
            executions_last_7_days=0,
            success_rate=0.0,
            by_trigger={},
            recent_executions=[]
        )


async def _get_agent_stats() -> AgentStats:
    """Get agent and team statistics"""
    try:
        # Total teams
        total_teams = await repo_query("SELECT COUNT(*) as count FROM agent_teams")
        total_teams_count = total_teams[0]["count"] if total_teams else 0

        # Active teams
        active_teams = await repo_query(
            "SELECT COUNT(*) as count FROM agent_teams WHERE status = 'running'"
        )
        active_teams_count = active_teams[0]["count"] if active_teams else 0

        # Total agents
        total_agents = await repo_query("SELECT COUNT(*) as count FROM agent_instances")
        total_agents_count = total_agents[0]["count"] if total_agents else 0

        # Agents by role
        by_role = await repo_query(
            "SELECT role, COUNT(*) as count FROM agent_instances GROUP BY role"
        )
        role_dict = {row["role"]: row["count"] for row in by_role}

        # Task completion rate
        task_rate = await repo_query(
            """
            SELECT
                COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as rate
            FROM agent_tasks
            """
        )
        completion_rate = task_rate[0]["rate"] if task_rate and task_rate[0]["rate"] else 0.0

        # Active tasks
        active_tasks = await repo_query(
            "SELECT COUNT(*) as count FROM agent_tasks WHERE status = 'in_progress'"
        )
        active_tasks_count = active_tasks[0]["count"] if active_tasks else 0

        # Completed tasks today
        completed_today = await repo_query(
            """
            SELECT COUNT(*) as count FROM agent_tasks
            WHERE status = 'completed' AND DATE(completed_at) = DATE('now')
            """
        )
        completed_today_count = completed_today[0]["count"] if completed_today else 0

        return AgentStats(
            total_teams=total_teams_count,
            active_teams=active_teams_count,
            total_agents=total_agents_count,
            agents_by_role=role_dict,
            task_completion_rate=round(completion_rate, 1),
            active_tasks=active_tasks_count,
            completed_tasks_today=completed_today_count
        )
    except Exception as e:
        print(f"Error getting agent stats: {e}")
        return AgentStats(
            total_teams=0,
            active_teams=0,
            total_agents=0,
            agents_by_role={},
            task_completion_rate=0.0,
            active_tasks=0,
            completed_tasks_today=0
        )


async def _get_approval_stats() -> ApprovalStats:
    """Get approval statistics"""
    try:
        # Pending count
        pending = await repo_query(
            "SELECT COUNT(*) as count FROM workflow_approvals WHERE status = 'pending'"
        )
        pending_count = pending[0]["count"] if pending else 0

        # Pending items with workflow name
        pending_items = await repo_query(
            """
            SELECT
                a.id, a.approval_prompt, a.created, a.timeout_at, w.name as workflow_name
            FROM workflow_approvals a
            LEFT JOIN workflows w ON a.workflow_id = w.id
            WHERE a.status = 'pending'
            ORDER BY a.created DESC
            LIMIT 5
            """
        )
        pending_list = [dict(row) for row in pending_items]

        # Average response time (in minutes)
        avg_time = await repo_query(
            """
            SELECT
                AVG((julianday(responded_at) - julianday(created)) * 24 * 60) as avg_minutes
            FROM workflow_approvals
            WHERE responded_at IS NOT NULL
            """
        )
        avg_response_time = avg_time[0]["avg_minutes"] if avg_time and avg_time[0]["avg_minutes"] else 0.0

        # Approval rate
        approval_rate_query = await repo_query(
            """
            SELECT
                COUNT(CASE WHEN status = 'approved' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as rate
            FROM workflow_approvals
            WHERE status IN ('approved', 'rejected')
            """
        )
        approval_rate = approval_rate_query[0]["rate"] if approval_rate_query and approval_rate_query[0]["rate"] else 0.0

        return ApprovalStats(
            pending_count=pending_count,
            pending_items=pending_list,
            avg_response_time_minutes=round(avg_response_time, 1),
            approval_rate=round(approval_rate, 1)
        )
    except Exception as e:
        print(f"Error getting approval stats: {e}")
        return ApprovalStats(
            pending_count=0,
            pending_items=[],
            avg_response_time_minutes=0.0,
            approval_rate=0.0
        )


async def _get_schedule_stats() -> ScheduleStats:
    """Get schedule statistics"""
    try:
        # Total schedules
        total = await repo_query("SELECT COUNT(*) as count FROM workflow_schedules")
        total_count = total[0]["count"] if total else 0

        # Enabled/disabled
        enabled = await repo_query(
            "SELECT COUNT(*) as count FROM workflow_schedules WHERE enabled = 1"
        )
        enabled_count = enabled[0]["count"] if enabled else 0
        disabled_count = total_count - enabled_count

        # Next scheduled runs
        next_runs = await repo_query(
            """
            SELECT
                s.id, s.schedule_type, s.cron_expression, s.next_run_at, w.name as workflow_name
            FROM workflow_schedules s
            LEFT JOIN workflows w ON s.workflow_id = w.id
            WHERE s.enabled = 1 AND s.next_run_at IS NOT NULL
            ORDER BY s.next_run_at ASC
            LIMIT 5
            """
        )
        next_runs_list = [dict(row) for row in next_runs]

        # Runs today
        runs_today = await repo_query(
            """
            SELECT COUNT(*) as count FROM workflow_executions
            WHERE DATE(started_at) = DATE('now')
            AND triggered_by IN ('cron', 'event', 'dependency')
            """
        )
        runs_today_count = runs_today[0]["count"] if runs_today else 0

        # Successful runs today
        successful_today = await repo_query(
            """
            SELECT COUNT(*) as count FROM workflow_executions
            WHERE DATE(started_at) = DATE('now')
            AND triggered_by IN ('cron', 'event', 'dependency')
            AND status = 'completed'
            """
        )
        successful_count = successful_today[0]["count"] if successful_today else 0

        return ScheduleStats(
            total_schedules=total_count,
            enabled=enabled_count,
            disabled=disabled_count,
            next_runs=next_runs_list,
            runs_today=runs_today_count,
            successful_runs_today=successful_count
        )
    except Exception as e:
        print(f"Error getting schedule stats: {e}")
        return ScheduleStats(
            total_schedules=0,
            enabled=0,
            disabled=0,
            next_runs=[],
            runs_today=0,
            successful_runs_today=0
        )


async def _get_workspace_stats() -> WorkspaceStats:
    """Get workspace and source statistics"""
    try:
        # Total notebooks
        total = await repo_query("SELECT COUNT(*) as count FROM notebooks")
        total_count = total[0]["count"] if total else 0

        # Active (not archived)
        active = await repo_query("SELECT COUNT(*) as count FROM notebooks WHERE archived = 0")
        active_count = active[0]["count"] if active else 0
        archived_count = total_count - active_count

        # Total sources
        sources = await repo_query("SELECT COUNT(*) as count FROM sources")
        sources_count = sources[0]["count"] if sources else 0

        # Sources by type
        by_type = await repo_query(
            "SELECT source_type, COUNT(*) as count FROM sources GROUP BY source_type"
        )
        type_dict = {row["source_type"]: row["count"] for row in by_type}

        return WorkspaceStats(
            total=total_count,
            active=active_count,
            archived=archived_count,
            total_sources=sources_count,
            sources_by_type=type_dict
        )
    except Exception as e:
        print(f"Error getting workspace stats: {e}")
        return WorkspaceStats(
            total=0,
            active=0,
            archived=0,
            total_sources=0,
            sources_by_type={}
        )


async def _get_microsite_stats() -> MicrositeStats:
    """Get microsite statistics"""
    try:
        # Total microsites
        total = await repo_query("SELECT COUNT(*) as count FROM microsites")
        total_count = total[0]["count"] if total else 0

        # Active microsites
        active = await repo_query("SELECT COUNT(*) as count FROM microsites WHERE is_active = 1")
        active_count = active[0]["count"] if active else 0

        # Total views (count of access records)
        views = await repo_query("SELECT COUNT(*) as count FROM microsite_access")
        total_views = views[0]["count"] if views else 0

        # Unique users
        unique_users = await repo_query("SELECT COUNT(DISTINCT email) as count FROM microsite_access")
        unique_users_count = unique_users[0]["count"] if unique_users else 0

        # Most viewed microsites
        most_viewed = await repo_query(
            """
            SELECT
                m.id, m.title, m.slug, COUNT(a.id) as view_count
            FROM microsites m
            LEFT JOIN microsite_access a ON m.id = a.microsite_id
            WHERE m.is_active = 1
            GROUP BY m.id, m.title, m.slug
            ORDER BY view_count DESC
            LIMIT 3
            """
        )
        most_viewed_list = [dict(row) for row in most_viewed]

        return MicrositeStats(
            total=total_count,
            active=active_count,
            total_views=total_views,
            unique_users=unique_users_count,
            most_viewed=most_viewed_list
        )
    except Exception as e:
        print(f"Error getting microsite stats: {e}")
        return MicrositeStats(
            total=0,
            active=0,
            total_views=0,
            unique_users=0,
            most_viewed=[]
        )


async def _get_ai_usage_stats() -> AIUsageStats:
    """Get AI usage statistics"""
    try:
        # Tool calls today
        tool_calls = await repo_query(
            "SELECT COUNT(*) as count FROM tool_usage_log WHERE DATE(created) = DATE('now')"
        )
        tool_calls_today = tool_calls[0]["count"] if tool_calls else 0

        # Chat messages today
        chat_messages = await repo_query(
            "SELECT COUNT(*) as count FROM chat_messages WHERE DATE(created) = DATE('now')"
        )
        chat_messages_today = chat_messages[0]["count"] if chat_messages else 0

        # Top tools (last 7 days)
        top_tools = await repo_query(
            """
            SELECT
                tool_id, COUNT(*) as count
            FROM tool_usage_log
            WHERE created >= datetime('now', '-7 days')
            GROUP BY tool_id
            ORDER BY count DESC
            LIMIT 5
            """
        )
        top_tools_list = [{"tool_id": row["tool_id"], "count": row["count"]} for row in top_tools]

        # Average execution time
        avg_time = await repo_query(
            """
            SELECT AVG(execution_time_ms) as avg_ms
            FROM tool_usage_log
            WHERE execution_time_ms IS NOT NULL
            AND created >= datetime('now', '-7 days')
            """
        )
        avg_execution_time = avg_time[0]["avg_ms"] if avg_time and avg_time[0]["avg_ms"] else 0.0

        return AIUsageStats(
            tool_calls_today=tool_calls_today,
            chat_messages_today=chat_messages_today,
            top_tools=top_tools_list,
            avg_execution_time_ms=round(avg_execution_time, 1)
        )
    except Exception as e:
        print(f"Error getting AI usage stats: {e}")
        return AIUsageStats(
            tool_calls_today=0,
            chat_messages_today=0,
            top_tools=[],
            avg_execution_time_ms=0.0
        )


async def _get_notification_stats() -> NotificationStats:
    """Get notification statistics"""
    try:
        # Unread count (sum for all users)
        unread = await repo_query(
            "SELECT COUNT(*) as count FROM notifications WHERE is_read = 0 AND (expires_at IS NULL OR expires_at > datetime('now'))"
        )
        unread_count = unread[0]["count"] if unread else 0

        # By type
        by_type = await repo_query(
            """
            SELECT type, COUNT(*) as count
            FROM notifications
            WHERE is_read = 0 AND (expires_at IS NULL OR expires_at > datetime('now'))
            GROUP BY type
            """
        )
        type_dict = {row["type"]: row["count"] for row in by_type}

        return NotificationStats(
            unread_count=unread_count,
            by_type=type_dict
        )
    except Exception as e:
        print(f"Error getting notification stats: {e}")
        return NotificationStats(
            unread_count=0,
            by_type={}
        )


async def _get_system_stats() -> SystemStats:
    """Get system statistics"""
    try:
        db_service = get_database_service()

        # Database type
        db_type = db_service._current_db.db_type if db_service._current_db else "unknown"

        # Total records (approximation from key tables)
        total_records_query = await repo_query(
            """
            SELECT
                (SELECT COUNT(*) FROM notebooks) +
                (SELECT COUNT(*) FROM sources) +
                (SELECT COUNT(*) FROM notes) +
                (SELECT COUNT(*) FROM chat_messages) +
                (SELECT COUNT(*) FROM workflow_executions) as total
            """
        )
        total_records = total_records_query[0]["total"] if total_records_query else 0

        # Uptime (hours since connection start)
        uptime_hours = 0.0
        if db_service._connection_start_time:
            uptime_hours = (datetime.utcnow() - db_service._connection_start_time).total_seconds() / 3600

        return SystemStats(
            db_type=db_type,
            total_records=total_records,
            last_backup=None,  # TODO: Implement backup tracking
            uptime_hours=round(uptime_hours, 1)
        )
    except Exception as e:
        print(f"Error getting system stats: {e}")
        return SystemStats(
            db_type="unknown",
            total_records=0,
            last_backup=None,
            uptime_hours=0.0
        )


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats():
    """
    Get comprehensive dashboard statistics

    Returns aggregated statistics from all platform systems with 30-second caching.
    """
    global _stats_cache, _cache_time

    # Check cache
    if _is_cache_valid():
        return DashboardStatsResponse(**_stats_cache)

    try:
        # Gather all stats in parallel
        import asyncio

        hero_metrics, workflows, agents, approvals, schedules, workspaces, microsites, ai_usage, notifications, system = await asyncio.gather(
            _get_hero_metrics(),
            _get_workflow_stats(),
            _get_agent_stats(),
            _get_approval_stats(),
            _get_schedule_stats(),
            _get_workspace_stats(),
            _get_microsite_stats(),
            _get_ai_usage_stats(),
            _get_notification_stats(),
            _get_system_stats()
        )

        # Build response
        stats = {
            "hero_metrics": hero_metrics.dict(),
            "workflows": workflows.dict(),
            "agents": agents.dict(),
            "approvals": approvals.dict(),
            "schedules": schedules.dict(),
            "workspaces": workspaces.dict(),
            "microsites": microsites.dict(),
            "ai_usage": ai_usage.dict(),
            "notifications": notifications.dict(),
            "system": system.dict()
        }

        # Cache the results
        _stats_cache = stats
        _cache_time = datetime.utcnow()

        return DashboardStatsResponse(**stats)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard stats: {str(e)}")


# ============================================================================
# WebSocket Endpoint for Real-time Dashboard Updates
# ============================================================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str
):
    """
    WebSocket endpoint for real-time dashboard updates

    Clients connect to this endpoint to receive instant stat updates when platform events occur.
    Falls back to 30-second polling if WebSocket is unavailable.
    """
    await dashboard_manager.connect(user_id, websocket)

    try:
        # Send initial stats
        stats = await get_dashboard_stats()
        await websocket.send_json({
            "type": "stats_update",
            "data": stats.dict()
        })

        # Keep connection alive and handle incoming messages
        while True:
            # Wait for client messages (e.g., ping/pong for keep-alive)
            data = await websocket.receive_text()

            # Echo back for keep-alive
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        dashboard_manager.disconnect(user_id, websocket)
    except Exception as e:
        print(f"Dashboard WebSocket error for user {user_id}: {e}")
        dashboard_manager.disconnect(user_id, websocket)


# ============================================================================
# Broadcast Functions (called by other services)
# ============================================================================

async def broadcast_stats_update():
    """
    Broadcast stats update to all connected WebSocket clients

    Call this function when significant platform events occur:
    - Workflow execution completion/start
    - Agent team status change
    - Approval creation/response
    - Schedule trigger
    """
    # Clear cache to force refresh
    _clear_cache()

    # Get fresh stats
    stats = await get_dashboard_stats()

    # Broadcast to all connected clients
    await dashboard_manager.broadcast_to_all({
        "type": "stats_update",
        "data": stats.dict()
    })
