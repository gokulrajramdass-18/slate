"""
Data Source Injector

Injects data source metadata into system prompts to make agents
aware of available data (HANA tables, APIs, files, etc.).
"""

from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class DataSourceInjector:
    """
    Injects data source metadata into system prompts.

    Provides agents with awareness of available data sources by:
    1. Querying notebook sources from database
    2. Building formatted summaries of tables, APIs, files
    3. Injecting into system prompts
    """

    async def get_data_source_context(
        self,
        notebook_id: str
    ) -> Dict[str, Any]:
        """
        Get data source context for a notebook.

        Returns metadata about available sources (HANA tables, APIs, files).

        Args:
            notebook_id: Notebook ID

        Returns:
            Dict with data source metadata
        """
        try:
            from open_notebook.database.repository import repo_query

            # Get all sources in notebook
            sql = """
                SELECT
                    s.id,
                    s.title,
                    s.source_type,
                    s.connection_config,
                    s.metadata
                FROM sources s
                INNER JOIN notebook_source ns ON s.id = ns.source_id
                WHERE ns.notebook_id = :notebook_id
                ORDER BY s.source_type, s.title
            """

            sources = await repo_query(sql, {"notebook_id": notebook_id})

            # Organize by type
            context = {
                "notebook_id": notebook_id,
                "total_sources": len(sources),
                "by_type": {},
                "hana_tables": [],
                "apis": [],
                "files": [],
                "urls": [],
                "youtube": []
            }

            for source in sources:
                source_type = source["source_type"]

                # Count by type
                if source_type not in context["by_type"]:
                    context["by_type"][source_type] = 0
                context["by_type"][source_type] += 1

                # Build detailed info
                source_info = {
                    "id": source["id"],
                    "title": source["title"],
                    "type": source_type
                }

                # Add type-specific metadata
                if source_type == "hana_table":
                    config = self._parse_config(source["connection_config"])
                    source_info["table_name"] = config.get("table_name")
                    source_info["columns"] = config.get("content_columns", [])
                    context["hana_tables"].append(source_info)

                elif source_type == "api":
                    config = self._parse_config(source["connection_config"])
                    source_info["base_url"] = config.get("base_url")
                    source_info["endpoints"] = config.get("endpoints", [])
                    context["apis"].append(source_info)

                elif source_type == "file":
                    metadata = self._parse_config(source.get("metadata"))
                    source_info["file_type"] = metadata.get("file_type")
                    context["files"].append(source_info)

                elif source_type == "url":
                    context["urls"].append(source_info)

                elif source_type == "youtube":
                    context["youtube"].append(source_info)

            logger.info(
                f"[DataSourceInjector] Notebook {notebook_id} has {len(sources)} sources: "
                f"{context['by_type']}"
            )

            return context

        except Exception as e:
            logger.error(f"[DataSourceInjector] Failed to get context: {e}", exc_info=True)
            return {
                "notebook_id": notebook_id,
                "total_sources": 0,
                "by_type": {},
                "error": str(e)
            }

    def _parse_config(self, config: Any) -> Dict[str, Any]:
        """Parse connection_config or metadata JSON"""
        if isinstance(config, str):
            try:
                return json.loads(config)
            except json.JSONDecodeError:
                return {}
        elif isinstance(config, dict):
            return config
        return {}

    def build_data_source_summary(self, context: Dict[str, Any]) -> str:
        """
        Build human-readable summary of data sources.

        Used in system prompt to inform agent of available data.

        Args:
            context: Output from get_data_source_context()

        Returns:
            Formatted string describing data sources
        """
        if context.get("error"):
            return f"Note: Could not load data sources ({context['error']})"

        lines = ["## Available Data Sources\n"]

        total = context["total_sources"]
        if total == 0:
            return "This notebook has no data sources yet. You can only answer based on conversation context."

        lines.append(f"This notebook has **{total} data sources** available:\n")

        # HANA Tables
        if context["hana_tables"]:
            lines.append(f"### 🗄️ HANA Database Tables ({len(context['hana_tables'])})\n")
            for table in context["hana_tables"]:
                columns_str = ", ".join(table.get("columns", [])[:5])
                if len(table.get("columns", [])) > 5:
                    columns_str += ", ..."
                lines.append(
                    f"- **{table['title']}** (`{table['table_name']}`)\n"
                    f"  Columns: {columns_str}\n"
                )
            lines.append("")

        # APIs
        if context["apis"]:
            lines.append(f"### 🌐 REST APIs ({len(context['apis'])})\n")
            for api in context["apis"]:
                endpoints = api.get("endpoints", [])
                lines.append(
                    f"- **{api['title']}** ({api['base_url']})\n"
                    f"  Endpoints: {len(endpoints)}\n"
                )
            lines.append("")

        # Files
        if context["files"]:
            lines.append(f"### 📄 Files ({len(context['files'])})\n")
            by_type = {}
            for file in context["files"]:
                file_type = file.get("file_type", "unknown")
                by_type[file_type] = by_type.get(file_type, 0) + 1

            for file_type, count in by_type.items():
                lines.append(f"- {count} {file_type} files\n")
            lines.append("")

        # URLs
        if context["urls"]:
            lines.append(f"### 🔗 Web Pages ({len(context['urls'])})\n")
            lines.append("")

        # YouTube
        if context["youtube"]:
            lines.append(f"### 🎥 YouTube Videos ({len(context['youtube'])})\n")
            lines.append("")

        lines.append(
            "💡 **Tip**: Use the `search_notebook` tool to find information across all sources. "
            "Use HANA query tools (query_*) to analyze structured data.\n"
        )

        return "".join(lines)


# Singleton
_data_source_injector: Optional[DataSourceInjector] = None


def get_data_source_injector() -> DataSourceInjector:
    """Get or create singleton data source injector"""
    global _data_source_injector
    if _data_source_injector is None:
        _data_source_injector = DataSourceInjector()
    return _data_source_injector
