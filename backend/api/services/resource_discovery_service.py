"""
Resource Discovery Service

Discovers relevant data sources, tools, agents, and teams based on
analyzed workspace goals. Scores resources by relevance to help
with guided workspace creation.
"""

import json
import logging
from typing import Dict, List, Any

from open_notebook.database.repository import repo_query

logger = logging.getLogger(__name__)


class ResourceDiscoveryService:
    """Discovers and scores resources relevant to workspace goals."""

    def score_relevance(self, resource: Dict[str, Any], analysis: Dict[str, Any]) -> float:
        """
        Score how relevant a resource is to the analyzed goals.

        Uses weighted combination of:
        - Keyword matching (0.4): overlap between analysis keywords and resource text
        - Requirement matching (0.4): overlap between requirements and resource capabilities
        - Quality/recency bonus (0.2): active status, recent updates

        Args:
            resource: Resource dict with title, description, name, etc.
            analysis: Goal analysis dict with keywords, requirements, etc.

        Returns:
            Float score between 0.0 and 1.0
        """
        keywords = set(k.lower() for k in analysis.get("keywords", []))
        requirements = set(r.lower() for r in analysis.get("requirements", []))

        # Build searchable text from resource fields
        resource_text = " ".join(
            str(resource.get(field, ""))
            for field in ("title", "description", "name", "goal", "role")
        ).lower()

        # Keyword score
        if keywords:
            keyword_matches = sum(1 for kw in keywords if kw in resource_text)
            keyword_score = min(keyword_matches / len(keywords), 1.0)
        else:
            keyword_score = 0.0

        # Requirement/capability score
        if requirements:
            req_matches = sum(1 for req in requirements if req in resource_text)
            req_score = min(req_matches / len(requirements), 1.0)
        else:
            req_score = 0.0

        # Quality/recency bonus
        quality_score = 0.5  # Default baseline
        status = resource.get("status", "")
        if status in ("active", "connected"):
            quality_score = 0.8
        elif status in ("error", "failed", "inactive"):
            quality_score = 0.2

        return (keyword_score * 0.4) + (req_score * 0.4) + (quality_score * 0.2)

    async def discover_data_sources(
        self, analysis: Dict[str, Any], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Discover data sources relevant to the analyzed goals.

        Queries the sources table, matching against title, description,
        topics, and source_type. Scores by keyword overlap.

        Args:
            analysis: Goal analysis dict with keywords, requirements, domain, etc.
            limit: Maximum number of results to return.

        Returns:
            List of source dicts with id, title, source_type, description,
            relevance_score, and stats.
        """
        try:
            keywords = analysis.get("keywords", [])

            if not keywords:
                logger.debug("No keywords in analysis, returning all sources")
                rows = await repo_query(
                    "SELECT id, title, source_type, full_text, topics, created, updated "
                    "FROM sources ORDER BY updated DESC LIMIT :limit",
                    {"limit": limit},
                )
            else:
                # Build LIKE conditions for keyword matching across text fields
                conditions = []
                params: Dict[str, Any] = {"limit": limit}
                for i, kw in enumerate(keywords):
                    param = f"kw_{i}"
                    conditions.append(
                        f"(title LIKE :{param} OR full_text LIKE :{param} OR topics LIKE :{param})"
                    )
                    params[param] = f"%{kw}%"

                where = " OR ".join(conditions)
                sql = (
                    "SELECT id, title, source_type, full_text, topics, created, updated "
                    f"FROM sources WHERE {where} "
                    "ORDER BY updated DESC LIMIT :limit"
                )
                rows = await repo_query(sql, params)

            results = []
            for row in rows:
                # Parse JSON fields
                topics = []
                if row.get("topics"):
                    try:
                        topics = json.loads(row["topics"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Build resource dict for scoring
                resource = {
                    "title": row.get("title", ""),
                    "description": row.get("full_text", "")[:200] if row.get("full_text") else "",
                    "name": row.get("title", ""),
                }

                score = self.score_relevance(resource, analysis)

                # Get chunk count for stats
                chunk_rows = await repo_query(
                    "SELECT COUNT(*) as count FROM source_embeddings WHERE source_id = :id",
                    {"id": row["id"]},
                )
                chunk_count = chunk_rows[0]["count"] if chunk_rows else 0

                results.append(
                    {
                        "id": row["id"],
                        "title": row.get("title", "Untitled"),
                        "source_type": row.get("source_type", "unknown"),
                        "description": row.get("full_text", "")[:200] if row.get("full_text") else "",
                        "relevance_score": round(score, 3),
                        "stats": {
                            "chunk_count": chunk_count,
                            "topics": topics,
                            "created": row.get("created"),
                            "updated": row.get("updated"),
                        },
                    }
                )

            # Sort by relevance score descending
            results.sort(key=lambda r: r["relevance_score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error discovering data sources: {e}")
            return []

    async def discover_tools(
        self, analysis: Dict[str, Any], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Discover tools relevant to the analyzed goals using AI-powered recommendations.

        Uses LLM to intelligently match tools based on intent, domain, and requirements.

        Args:
            analysis: Goal analysis dict.
            limit: Maximum number of results.

        Returns:
            List of tool dicts with id, name, description, capabilities,
            relevance_score, relevance_reason.
        """
        # Step 1: Gather all available tools
        all_tools = []

        # 1a. Get registry tools (prebuilt tools like web search, calculator, etc.)
        try:
            registry_rows = await repo_query(
                "SELECT id, name, tool_type, description, metadata "
                "FROM tool_registry "
                "WHERE enabled = 1 "
                "ORDER BY name"
            )

            for row in registry_rows:
                all_tools.append({
                    "id": f"registry:{row['id']}",
                    "name": row.get("name", ""),
                    "description": row.get("description", ""),
                    "tool_type": "registry",
                    "category": row.get("tool_type", ""),
                    "source": "registry",
                })
        except Exception as e:
            logger.warning(f"Error fetching registry tools: {e}")

        # 1b. Get MCP server tools
        try:
            mcp_rows = await repo_query(
                "SELECT t.id, t.server_id, t.tool_name, t.description, "
                "s.name AS server_name, s.status AS server_status "
                "FROM mcp_tools t "
                "JOIN mcp_servers s ON t.server_id = s.id "
                "WHERE s.status = 'connected' "
                "ORDER BY t.tool_name"
            )

            for row in mcp_rows:
                all_tools.append({
                    "id": f"mcp:{row['id']}",
                    "name": row.get("tool_name", ""),
                    "description": row.get("description", ""),
                    "tool_type": "mcp",
                    "server_name": row.get("server_name", ""),
                    "source": "mcp",
                })
        except Exception as e:
            logger.warning(f"Error fetching MCP tools: {e}")

        if not all_tools:
            return []

        # Step 2: Use AI to intelligently recommend tools
        try:
            from api.services.ai_tool_discovery import discover_tools_with_ai

            recommended_tools = await discover_tools_with_ai(all_tools, analysis, limit=limit)

            if recommended_tools:
                # AI successfully recommended tools
                results = []
                for tool in recommended_tools:
                    results.append({
                        "id": tool["id"],
                        "name": tool["name"],
                        "description": tool["description"],
                        "tool_type": tool.get("tool_type", ""),
                        "capabilities": {
                            "category": tool.get("category", ""),
                            "server_name": tool.get("server_name", ""),
                            "source": tool["source"],
                        },
                        "relevance_score": tool["relevance_score"],
                        "relevance_reason": tool["relevance_reason"],
                    })
                return results

        except Exception as e:
            logger.info(f"AI tool discovery not available, using keyword-based matching: {e}")

        # Step 3: Fallback to keyword-based matching if AI fails
        logger.info("Using fallback keyword-based tool discovery")
        results = []

        for tool in all_tools:
            resource = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "status": "active",
            }

            score = self.score_relevance(resource, analysis)

            # Fallback mode: be more inclusive
            # - If we have keywords/requirements, use relevance scoring
            # - If no filtering criteria, include all tools with base score
            has_criteria = bool(analysis.get("keywords") or analysis.get("requirements"))

            if not has_criteria:
                # No filtering - include all tools with base score
                score = 0.5
            elif score < 0.15:
                # Too low relevance even for fallback
                continue

            results.append({
                "id": tool["id"],
                "name": tool["name"],
                "description": tool["description"],
                "tool_type": tool.get("tool_type", ""),
                "capabilities": {
                    "category": tool.get("category", ""),
                    "server_name": tool.get("server_name", ""),
                    "source": tool["source"],
                },
                "relevance_score": round(score, 3),
                "relevance_reason": "Available tool for your workspace" if not has_criteria else "Matches goal keywords and requirements",
            })

        # Sort by relevance and return top results
        results.sort(key=lambda r: r["relevance_score"], reverse=True)
        return results[:limit]

    async def discover_agents(
        self, analysis: Dict[str, Any], limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Discover standalone agents relevant to the analyzed goals.

        Queries the standalone_agents table, filtering by active status
        and matching against role, name, description, and skills.

        Args:
            analysis: Goal analysis dict.
            limit: Maximum number of results.

        Returns:
            List of agent dicts with id, name, role, model, skills,
            relevance_score.
        """
        try:
            rows = await repo_query(
                "SELECT id, name, description, role, model_name, "
                "config, tool_ids, skill_ids, mcp_server_ids, data_source_ids, status "
                "FROM standalone_agents WHERE status = :status "
                "ORDER BY updated DESC",
                {"status": "active"},
            )

            results = []
            for row in rows:
                # Parse JSON fields for skills/capabilities
                skill_ids = []
                tool_ids = []
                config = {}
                if row.get("skill_ids"):
                    try:
                        skill_ids = json.loads(row["skill_ids"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                if row.get("tool_ids"):
                    try:
                        tool_ids = json.loads(row["tool_ids"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                if row.get("config"):
                    try:
                        config = json.loads(row["config"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                resource = {
                    "name": row.get("name", ""),
                    "description": row.get("description", ""),
                    "role": row.get("role", ""),
                    "status": row.get("status", ""),
                }

                score = self.score_relevance(resource, analysis)

                results.append(
                    {
                        "id": row["id"],
                        "name": row.get("name", ""),
                        "role": row.get("role", ""),
                        "model": row.get("model_name"),
                        "skills": skill_ids,
                        "tool_count": len(tool_ids),
                        "relevance_score": round(score, 3),
                    }
                )

            results.sort(key=lambda r: r["relevance_score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error discovering agents: {e}")
            return []

    async def discover_teams(
        self, analysis: Dict[str, Any], limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Discover agent teams relevant to the analyzed goals.

        Queries the agent_teams table, matching against team goal,
        name, and configuration. Also fetches member agents for
        capability assessment.

        Args:
            analysis: Goal analysis dict.
            limit: Maximum number of results.

        Returns:
            List of team dicts with id, name, agents, capabilities,
            relevance_score.
        """
        try:
            rows = await repo_query(
                "SELECT id, name, goal, status, config, result, created, updated "
                "FROM agent_teams "
                "ORDER BY updated DESC"
            )

            results = []
            for row in rows:
                config = {}
                if row.get("config"):
                    try:
                        config = json.loads(row["config"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                # Fetch team agents
                agent_rows = await repo_query(
                    "SELECT id, name, role, status FROM agent_instances "
                    "WHERE team_id = :team_id",
                    {"team_id": row["id"]},
                )

                agents = [
                    {
                        "id": a["id"],
                        "name": a.get("name", ""),
                        "role": a.get("role", ""),
                    }
                    for a in agent_rows
                ]

                # Collect capabilities from agent roles
                capabilities = list(set(a.get("role", "") for a in agent_rows if a.get("role")))

                resource = {
                    "name": row.get("name", ""),
                    "description": row.get("goal", ""),
                    "goal": row.get("goal", ""),
                    "status": row.get("status", ""),
                }

                score = self.score_relevance(resource, analysis)

                results.append(
                    {
                        "id": row["id"],
                        "name": row.get("name", ""),
                        "agents": agents,
                        "capabilities": capabilities,
                        "relevance_score": round(score, 3),
                    }
                )

            results.sort(key=lambda r: r["relevance_score"], reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Error discovering teams: {e}")
            return []


# Module-level singleton
_discovery_service = None


def get_resource_discovery_service() -> ResourceDiscoveryService:
    """Get or create the ResourceDiscoveryService singleton."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = ResourceDiscoveryService()
    return _discovery_service
