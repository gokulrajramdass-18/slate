"""
Graph Service - Relationship Building and Graph Data Assembly

Builds relational graph data from sources, embeddings, and metadata.
Computes semantic similarities, notebook relationships, topic overlaps,
HANA schema connections, and API endpoint relations.
"""

import uuid
import json
import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from itertools import combinations
from collections import defaultdict

from open_notebook.database.repository import db_connection, repo_query, repo_execute, repo_create


async def compute_source_similarities(source_id: str, threshold: float = 0.7, top_k: int = 20):
    """
    Compute semantic similarities between a source and all other sources.
    Stores top-K most similar sources in source_similarities table.

    Args:
        source_id: Source to compute similarities for
        threshold: Minimum similarity score to store (0.0-1.0)
        top_k: Maximum number of similar sources to store per source
    """
    async with db_connection() as db:
        # Get source embedding (average of all chunks)
        source_embeddings = await db.query(
            "SELECT embedding FROM source_embeddings WHERE source_id = :source_id",
            {"source_id": source_id}
        )

        if not source_embeddings:
            return  # No embeddings yet

        # Parse and average embeddings
        embeddings = [json.loads(e["embedding"]) for e in source_embeddings]
        source_vector = np.mean(embeddings, axis=0)

        # Get all other source embeddings (excluding current source)
        all_sources = await db.query(
            """SELECT DISTINCT se.source_id, se.embedding
               FROM source_embeddings se
               WHERE se.source_id != :source_id""",
            {"source_id": source_id}
        )

        if not all_sources:
            return

        # Compute cosine similarity with all sources
        similarities = []
        for other in all_sources:
            other_id = other["source_id"]

            # Get all embeddings for other source and average
            other_embeddings = await db.query(
                "SELECT embedding FROM source_embeddings WHERE source_id = :source_id",
                {"source_id": other_id}
            )
            other_vectors = [json.loads(e["embedding"]) for e in other_embeddings]
            other_vector = np.mean(other_vectors, axis=0)

            # Cosine similarity
            similarity = float(np.dot(source_vector, other_vector) /
                             (np.linalg.norm(source_vector) * np.linalg.norm(other_vector)))

            if similarity >= threshold:
                similarities.append((other_id, similarity))

        # Sort by score descending, take top-K
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_similarities = similarities[:top_k]

        # Delete existing similarities for this source
        await db.execute(
            "DELETE FROM source_similarities WHERE source_id = :source_id",
            {"source_id": source_id}
        )

        # Insert new similarities
        for related_id, score in top_similarities:
            similarity_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO source_similarities (id, source_id, related_source_id, similarity_score, created)
                   VALUES (:id, :source_id, :related_id, :score, :created)""",
                {
                    "id": similarity_id,
                    "source_id": source_id,
                    "related_id": related_id,
                    "score": score,
                    "created": datetime.utcnow().isoformat()
                }
            )


async def build_semantic_edges(
    source_ids: List[str],
    threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Build semantic similarity edges from pre-computed similarities table.

    Args:
        source_ids: List of source IDs to get edges for
        threshold: Minimum similarity score to include

    Returns:
        List of edge dictionaries with type='semantic'
    """
    if not source_ids:
        return []

    async with db_connection() as db:
        # Query similarities where both ends are in source_ids
        placeholders = ",".join([f":id{i}" for i in range(len(source_ids))])
        params = {f"id{i}": sid for i, sid in enumerate(source_ids)}
        params["threshold"] = threshold

        similarities = await db.query(
            f"""SELECT source_id, related_source_id, similarity_score
               FROM source_similarities
               WHERE source_id IN ({placeholders})
               AND related_source_id IN ({placeholders})
               AND similarity_score >= :threshold""",
            params
        )

        edges = []
        for sim in similarities:
            edge = {
                "id": f"semantic-{sim['source_id']}-{sim['related_source_id']}",
                "source": sim["source_id"],
                "target": sim["related_source_id"],
                "type": "relationship",  # React Flow edge type
                "label": f"{sim['similarity_score']:.0%}",
                "data": {
                    "relationship_type": "semantic",  # Actual relationship type for styling
                    "strength": sim["similarity_score"],
                    "metadata": {}
                }
            }
            edges.append(edge)

        return edges


async def build_notebook_edges(
    source_ids: List[str],
    notebook_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Build notebook membership edges between sources in same notebooks.

    Args:
        source_ids: List of source IDs to get edges for
        notebook_ids: Optional filter for specific notebooks

    Returns:
        List of edge dictionaries with type='notebook'
    """
    if not source_ids:
        return []

    async with db_connection() as db:
        # Build query
        placeholders = ",".join([f":id{i}" for i in range(len(source_ids))])
        params = {f"id{i}": sid for i, sid in enumerate(source_ids)}

        where_clauses = [f"ns1.source_id IN ({placeholders})", f"ns2.source_id IN ({placeholders})"]

        if notebook_ids:
            nb_placeholders = ",".join([f":nbid{i}" for i in range(len(notebook_ids))])
            params.update({f"nbid{i}": nid for i, nid in enumerate(notebook_ids)})
            where_clauses.append(f"ns1.notebook_id IN ({nb_placeholders})")

        where_clause = " AND ".join(where_clauses)

        # Query pairs of sources in same notebooks
        results = await db.query(
            f"""SELECT s1.id as source1, s2.id as source2,
                       n.id as notebook_id, n.name as notebook_name
               FROM notebook_source ns1
               JOIN notebook_source ns2 ON ns1.notebook_id = ns2.notebook_id
               JOIN notebooks n ON ns1.notebook_id = n.id
               JOIN sources s1 ON ns1.source_id = s1.id
               JOIN sources s2 ON ns2.source_id = s2.id
               WHERE {where_clause} AND s1.id < s2.id""",
            params
        )

        # Build edges grouped by notebook
        edges = []
        for row in results:
            edge = {
                "id": f"notebook-{row['source1']}-{row['source2']}-{row['notebook_id']}",
                "source": row["source1"],
                "target": row["source2"],
                "type": "relationship",
                "label": row["notebook_name"],
                "data": {
                    "relationship_type": "notebook",
                    "strength": 1.0,
                    "metadata": {
                        "notebook_id": row["notebook_id"],
                        "notebook_name": row["notebook_name"]
                    }
                }
            }
            edges.append(edge)

        return edges


async def build_topic_edges(
    sources: List[Dict[str, Any]],
    min_overlap: int = 2
) -> List[Dict[str, Any]]:
    """
    Build topic overlap edges between sources sharing similar topics.
    Uses Jaccard similarity on topics arrays.

    Args:
        sources: List of source dictionaries with id and topics fields
        min_overlap: Minimum number of shared topics to create edge

    Returns:
        List of edge dictionaries with type='topic'
    """
    edges = []

    # Parse topics for each source
    sources_with_topics = []
    for source in sources:
        if source.get("topics"):
            try:
                topics = json.loads(source["topics"]) if isinstance(source["topics"], str) else source["topics"]
                if topics and len(topics) > 0:
                    sources_with_topics.append({
                        "id": source["id"],
                        "topics": set(topics)
                    })
            except (json.JSONDecodeError, TypeError):
                continue

    # Compute pairwise topic overlap
    for s1, s2 in combinations(sources_with_topics, 2):
        topics1 = s1["topics"]
        topics2 = s2["topics"]

        # Find intersection
        shared_topics = topics1 & topics2
        overlap_count = len(shared_topics)

        if overlap_count >= min_overlap:
            # Jaccard similarity
            union = topics1 | topics2
            jaccard = overlap_count / len(union) if union else 0.0

            edge = {
                "id": f"topic-{s1['id']}-{s2['id']}",
                "source": s1["id"],
                "target": s2["id"],
                "type": "relationship",
                "label": f"{overlap_count} topics",
                "data": {
                    "relationship_type": "topic",
                    "strength": jaccard,
                    "metadata": {
                        "overlap_count": overlap_count,
                        "shared_topics": list(shared_topics)[:5]  # Limit to 5 for display
                    }
                }
            }
            edges.append(edge)

    return edges


async def build_hana_edges(
    hana_sources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Build HANA schema relationship edges between HANA table sources.
    Groups by connection and schema, adds FK relationships if available.

    Args:
        hana_sources: List of source dicts with source_type='hana_table'

    Returns:
        List of edge dictionaries with type='hana_schema'
    """
    edges = []

    # Parse connection configs
    sources_by_connection = defaultdict(list)
    for source in hana_sources:
        if not source.get("connection_config"):
            continue

        try:
            config = json.loads(source["connection_config"]) if isinstance(source["connection_config"], str) else source["connection_config"]
            conn_id = config.get("connection_id")
            if conn_id:
                sources_by_connection[conn_id].append({
                    "id": source["id"],
                    "table_name": config.get("table_name"),
                    "schema": config.get("schema"),
                    "asset_data": source.get("asset_data", {})
                })
        except (json.JSONDecodeError, TypeError):
            continue

    # Build edges within each connection
    for conn_id, tables in sources_by_connection.items():
        # Get connection name
        async with db_connection() as db:
            conn = await db.query(
                "SELECT name FROM hana_connections WHERE id = :id",
                {"id": conn_id},
                fetch_one=True
            )
            conn_name = conn["name"] if conn and "name" in conn else "Unknown Connection"

        # Group by schema - tables in same schema are related
        tables_by_schema = defaultdict(list)
        for table in tables:
            schema = table["schema"] or "default"
            tables_by_schema[schema].append(table)

        # Create edges for same-schema tables
        for schema, schema_tables in tables_by_schema.items():
            for t1, t2 in combinations(schema_tables, 2):
                edge = {
                    "id": f"hana-schema-{t1['id']}-{t2['id']}",
                    "source": t1["id"],
                    "target": t2["id"],
                    "type": "relationship",
                    "label": f"Schema: {schema}",
                    "data": {
                        "relationship_type": "hana_schema",
                        "strength": 0.8,
                        "metadata": {
                            "connection_name": conn_name,
                            "schema": schema,
                            "relationship": "same_schema"
                        }
                    }
                }
                edges.append(edge)

        # Check for foreign key relationships in asset_data
        for table in tables:
            asset_data_raw = table.get("asset_data")
            if not asset_data_raw:
                continue

            if isinstance(asset_data_raw, str):
                try:
                    asset_data = json.loads(asset_data_raw)
                except json.JSONDecodeError:
                    asset_data = {}
            elif isinstance(asset_data_raw, dict):
                asset_data = asset_data_raw
            else:
                asset_data = {}

            fks = asset_data.get("foreign_keys", [])
            for fk in fks:
                # Find target table by name
                ref_table_name = fk.get("referenced_table")
                target = next((t for t in tables if t["table_name"] == ref_table_name), None)

                if target:
                    edge = {
                        "id": f"hana-fk-{table['id']}-{target['id']}",
                        "source": table["id"],
                        "target": target["id"],
                        "type": "relationship",
                        "label": f"FK: {fk.get('column')}",
                        "data": {
                            "relationship_type": "hana_schema",
                            "strength": 1.0,
                            "metadata": {
                                "connection_name": conn_name,
                                "relationship": "foreign_key",
                                "column": fk.get("column"),
                                "referenced_table": ref_table_name
                            }
                        }
                    }
                    edges.append(edge)

    return edges


async def build_api_edges(
    api_sources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Build API relationship edges between API endpoint sources.
    Groups by connection, detects nested endpoints, and identifies RESTful resources.

    Args:
        api_sources: List of source dicts with source_type='api'

    Returns:
        List of edge dictionaries with type='api_relation'
    """
    edges = []

    # Parse connection configs
    sources_by_connection = defaultdict(list)
    for source in api_sources:
        if not source.get("connection_config"):
            continue

        try:
            config = json.loads(source["connection_config"]) if isinstance(source["connection_config"], str) else source["connection_config"]
            conn_id = config.get("connection_id")
            if conn_id:
                sources_by_connection[conn_id].append({
                    "id": source["id"],
                    "url": config.get("url", ""),
                    "method": config.get("method", "GET"),
                    "endpoint": config.get("url", "")
                })
        except (json.JSONDecodeError, TypeError):
            continue

    # Build edges within each connection
    for conn_id, endpoints in sources_by_connection.items():
        # Get connection name
        async with db_connection() as db:
            conn = await db.query(
                "SELECT name FROM api_connections WHERE id = :id",
                {"id": conn_id},
                fetch_one=True
            )
            conn_name = conn["name"] if conn and "name" in conn else "Unknown Connection"

        # Same connection edges
        for e1, e2 in combinations(endpoints, 2):
            edge_id = f"api-conn-{e1['id']}-{e2['id']}"
            edges.append({
                "id": edge_id,
                "source": e1["id"],
                "target": e2["id"],
                "type": "relationship",
                "label": f"Connection: {conn_name}",
                "data": {
                    "relationship_type": "api_relation",
                    "strength": 0.7,
                    "api_variant": "solid",
                    "metadata": {
                        "connection_name": conn_name,
                        "relationship": "same_connection"
                    }
                }
            })

            # Check for nested endpoints (e.g., /users/{id} and /users/{id}/posts)
            if is_nested_endpoint(e1["endpoint"], e2["endpoint"]):
                parent, child = (e1, e2) if len(e1["endpoint"]) < len(e2["endpoint"]) else (e2, e1)
                edge_id = f"api-nested-{parent['id']}-{child['id']}"
                edges.append({
                    "id": edge_id,
                    "source": parent["id"],
                    "target": child["id"],
                    "type": "relationship",
                    "label": f"Nested: {parent['endpoint']} → {child['endpoint']}",
                    "data": {
                        "relationship_type": "api_relation",
                        "strength": 0.9,
                        "api_variant": "dashed",
                        "metadata": {
                            "relationship": "nested",
                            "parent": parent["endpoint"],
                            "child": child["endpoint"]
                        }
                    }
                })

            # Check for same RESTful resource
            resource = get_common_resource(e1["endpoint"], e2["endpoint"])
            if resource:
                edge_id = f"api-resource-{e1['id']}-{e2['id']}"
                edges.append({
                    "id": edge_id,
                    "source": e1["id"],
                    "target": e2["id"],
                    "type": "relationship",
                    "label": f"Resource: {resource}",
                    "data": {
                        "relationship_type": "api_relation",
                        "strength": 0.8,
                        "api_variant": "dotted",
                        "metadata": {
                            "relationship": "same_resource",
                            "resource": resource
                        }
                    }
                })

    return edges


def is_nested_endpoint(url1: str, url2: str) -> bool:
    """Check if one endpoint is nested under another (e.g., /users/{id} and /users/{id}/posts)."""
    # Normalize URLs (remove query params, trailing slashes)
    path1 = url1.split("?")[0].rstrip("/")
    path2 = url2.split("?")[0].rstrip("/")

    # One must be prefix of the other
    return path1.startswith(path2) or path2.startswith(path1)


def get_common_resource(url1: str, url2: str) -> Optional[str]:
    """Extract common RESTful resource from two endpoints (e.g., 'users' from /api/users and /api/users/{id})."""
    path1 = url1.split("?")[0].rstrip("/").split("/")
    path2 = url2.split("?")[0].rstrip("/").split("/")

    # Find longest common prefix
    common = []
    for p1, p2 in zip(path1, path2):
        if p1 == p2 and not p1.startswith("{"):  # Ignore path parameters
            common.append(p1)
        else:
            break

    # Return last non-empty segment as resource name
    if common:
        resource = common[-1]
        if resource and resource.lower() not in ["api", "v1", "v2", "v3"]:  # Ignore API version prefixes
            return resource

    return None


async def build_note_link_edges(
    source_ids: List[str]
) -> List[Dict[str, Any]]:
    """
    Build note link edges from note_links table.

    Args:
        source_ids: List of source IDs to get edges for

    Returns:
        List of edge dictionaries with type='note_link'
    """
    if not source_ids:
        return []

    async with db_connection() as db:
        placeholders = ",".join([f":id{i}" for i in range(len(source_ids))])
        params = {f"id{i}": sid for i, sid in enumerate(source_ids)}

        # Query note links where both notes are in source_ids
        links = await db.query(
            f"""SELECT nl.source_note_id, nl.target_note_id,
                       n1.title as source_title, n2.title as target_title
               FROM note_links nl
               JOIN notes n1 ON nl.source_note_id = n1.id
               JOIN notes n2 ON nl.target_note_id = n2.id
               WHERE nl.source_note_id IN ({placeholders})
               AND nl.target_note_id IN ({placeholders})""",
            params
        )

        edges = []
        for link in links:
            edge = {
                "id": f"note-link-{link['source_note_id']}-{link['target_note_id']}",
                "source": link["source_note_id"],
                "target": link["target_note_id"],
                "type": "relationship",
                "label": f"{link['source_title']} → {link['target_title']}",
                "data": {
                    "relationship_type": "note_link",
                    "strength": 1.0,
                    "metadata": {
                        "source_title": link["source_title"],
                        "target_title": link["target_title"]
                    }
                }
            }
            edges.append(edge)

        return edges


async def get_graph_data(
    scope: str = "global",
    scope_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build complete graph data with nodes and edges.

    Args:
        scope: 'global' for all sources or 'notebook' for specific notebook
        scope_id: notebook_id if scope='notebook'
        filters: Optional filters dict with:
            - source_types: List[str]
            - notebook_ids: List[str]
            - tags: List[str]
            - date_from: str (ISO date)
            - date_to: str (ISO date)
            - semantic_threshold: float (0.7-1.0)
            - min_topic_overlap: int (2-5)
            - show_isolated: bool
            - edge_types: List[str]

    Returns:
        Dict with nodes, edges, and metadata
    """
    filters = filters or {}

    # Build WHERE clauses for sources query
    where_clauses = []
    params = {}

    # Scope filter
    if scope == "notebook" and scope_id:
        where_clauses.append("s.id IN (SELECT source_id FROM notebook_source WHERE notebook_id = :scope_id)")
        params["scope_id"] = scope_id

    # Source type filter
    if filters.get("source_types"):
        type_placeholders = ",".join([f":type{i}" for i in range(len(filters["source_types"]))])
        params.update({f"type{i}": t for i, t in enumerate(filters["source_types"])})
        where_clauses.append(f"s.source_type IN ({type_placeholders})")

    # Notebook filter (for global scope)
    if filters.get("notebook_ids") and scope == "global":
        nb_placeholders = ",".join([f":nbid{i}" for i in range(len(filters["notebook_ids"]))])
        params.update({f"nbid{i}": nid for i, nid in enumerate(filters["notebook_ids"])})
        where_clauses.append(f"s.id IN (SELECT source_id FROM notebook_source WHERE notebook_id IN ({nb_placeholders}))")

    # Date range filter
    if filters.get("date_from"):
        where_clauses.append("s.created >= :date_from")
        params["date_from"] = filters["date_from"]

    if filters.get("date_to"):
        where_clauses.append("s.created <= :date_to")
        params["date_to"] = filters["date_to"]

    # Tag filter - sources with matching tags
    if filters.get("tags"):
        # Tags are stored as JSON array in sources table (if implemented)
        # For now, skip - can add if tags field exists on sources
        pass

    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

    async with db_connection() as db:
        # Get sources
        sources = await db.query(
            f"""SELECT s.id, s.title, s.source_type, s.created, s.updated,
                       s.topics, s.asset_data, s.connection_config,
                       COUNT(DISTINCT se.id) as chunk_count
               FROM sources s
               LEFT JOIN source_embeddings se ON s.id = se.source_id
               WHERE {where_clause}
               GROUP BY s.id
               ORDER BY s.created DESC
               LIMIT 1000""",
            params
        )

        if not sources:
            return {
                "nodes": [],
                "edges": [],
                "metadata": {
                    "total_sources": 0,
                    "date_range": None,
                    "source_type_counts": {},
                    "edge_type_counts": {}
                }
            }

        source_ids = [s["id"] for s in sources]

        # Get notebooks for each source
        notebooks_map = defaultdict(list)
        notebook_results = await db.query(
            f"""SELECT ns.source_id, n.id, n.name
               FROM notebook_source ns
               JOIN notebooks n ON ns.notebook_id = n.id
               WHERE ns.source_id IN ({','.join([f':sid{i}' for i in range(len(source_ids))])})""",
            {f"sid{i}": sid for i, sid in enumerate(source_ids)}
        )
        for nb in notebook_results:
            notebooks_map[nb["source_id"]].append({"id": nb["id"], "name": nb["name"]})

        # Get all HANA connection names
        hana_connections_map = {}
        hana_conn_results = await db.query("SELECT id, name FROM hana_connections")
        for conn in hana_conn_results:
            hana_connections_map[conn["id"]] = conn["name"]

        # Get all API connection names
        api_connections_map = {}
        api_conn_results = await db.query("SELECT id, name FROM api_connections")
        for conn in api_conn_results:
            api_connections_map[conn["id"]] = conn["name"]

    # Build nodes
    nodes = []
    for source in sources:
        # Parse topics
        topics = []
        if source.get("topics"):
            try:
                topics = json.loads(source["topics"]) if isinstance(source["topics"], str) else source["topics"]
            except (json.JSONDecodeError, TypeError):
                topics = []

        # Parse type-specific metadata
        hana_metadata = None
        api_metadata = None
        youtube_metadata = None
        file_metadata = None

        if source["source_type"] == "hana_table" and source.get("connection_config"):
            try:
                config = json.loads(source["connection_config"]) if isinstance(source["connection_config"], str) else source["connection_config"]
                connection_id = config.get("connection_id")

                hana_metadata = {
                    "table_name": config.get("table_name"),
                    "schema": config.get("schema"),
                    "connection_name": hana_connections_map.get(connection_id) if connection_id else None,
                    "key_column": config.get("key_column"),
                    "content_columns": config.get("content_columns", [])
                }
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        elif source["source_type"] == "api" and source.get("connection_config"):
            try:
                config = json.loads(source["connection_config"]) if isinstance(source["connection_config"], str) else source["connection_config"]
                connection_id = config.get("connection_id")

                api_metadata = {
                    "endpoint": config.get("url"),
                    "method": config.get("method", "GET"),
                    "connection_name": api_connections_map.get(connection_id) if connection_id else None
                }
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        elif source["source_type"] == "youtube" and source.get("asset_data"):
            try:
                asset = json.loads(source["asset_data"]) if isinstance(source["asset_data"], str) else source["asset_data"]
                youtube_metadata = {
                    "channel": asset.get("channel_name"),
                    "duration": asset.get("duration_seconds"),
                    "views": asset.get("view_count")
                }
            except (json.JSONDecodeError, TypeError):
                pass

        elif source["source_type"] == "file" and source.get("asset_data"):
            try:
                asset = json.loads(source["asset_data"]) if isinstance(source["asset_data"], str) else source["asset_data"]
                file_metadata = {
                    "asset_type": source.get("asset_type"),
                    "size": asset.get("file_size")
                }
            except (json.JSONDecodeError, TypeError):
                pass

        node = {
            "id": source["id"],
            "type": "source",  # React Flow node type (registered as 'source' in frontend)
            "label": source["title"],
            "data": {
                "title": source["title"],
                "description": "",  # No description field in sources table
                "source_type": source["source_type"],
                "created": source["created"],
                "updated": source["updated"],
                "chunk_count": source["chunk_count"],
                "topics": topics,
                "connection_count": 0,  # Will be updated after edges are built
                "notebooks": notebooks_map.get(source["id"], []),
                "hana_metadata": hana_metadata,
                "api_metadata": api_metadata,
                "youtube_metadata": youtube_metadata,
                "file_metadata": file_metadata
            }
        }
        nodes.append(node)

    # Build edges based on enabled edge types
    enabled_edge_types = filters.get("edge_types", ["semantic", "notebook", "topic", "note_link", "hana_schema", "api_relation"])
    all_edges = []

    # Semantic edges (from pre-computed similarities)
    if "semantic" in enabled_edge_types:
        threshold = filters.get("semantic_threshold", 0.7)
        semantic_edges = await build_semantic_edges(source_ids, threshold)
        all_edges.extend(semantic_edges)

    # Notebook edges
    if "notebook" in enabled_edge_types:
        notebook_ids = filters.get("notebook_ids") if scope == "global" else ([scope_id] if scope_id else None)
        notebook_edges = await build_notebook_edges(source_ids, notebook_ids)
        all_edges.extend(notebook_edges)

    # Topic edges
    if "topic" in enabled_edge_types:
        min_overlap = filters.get("min_topic_overlap", 2)
        topic_edges = await build_topic_edges(sources, min_overlap)
        all_edges.extend(topic_edges)

    # HANA schema edges
    if "hana_schema" in enabled_edge_types:
        hana_sources = [s for s in sources if s["source_type"] == "hana_table"]
        if hana_sources:
            hana_edges = await build_hana_edges(hana_sources)
            all_edges.extend(hana_edges)

    # API relation edges
    if "api_relation" in enabled_edge_types:
        api_sources = [s for s in sources if s["source_type"] == "api"]
        if api_sources:
            api_edges = await build_api_edges(api_sources)
            all_edges.extend(api_edges)

    # Note link edges
    if "note_link" in enabled_edge_types:
        note_edges = await build_note_link_edges(source_ids)
        all_edges.extend(note_edges)

    # Update connection counts on nodes
    connection_counts = defaultdict(int)
    for edge in all_edges:
        connection_counts[edge["source"]] += 1
        connection_counts[edge["target"]] += 1

    for node in nodes:
        node["data"]["connection_count"] = connection_counts.get(node["id"], 0)

    # Filter isolated nodes if requested
    if not filters.get("show_isolated", True):
        connected_node_ids = set()
        for edge in all_edges:
            connected_node_ids.add(edge["source"])
            connected_node_ids.add(edge["target"])
        nodes = [n for n in nodes if n["id"] in connected_node_ids]

    # Build metadata
    source_type_counts = {}
    for node in nodes:
        st = node["data"]["source_type"]
        source_type_counts[st] = source_type_counts.get(st, 0) + 1

    edge_type_counts = {}
    for edge in all_edges:
        et = edge["data"].get("relationship_type", "unknown")
        edge_type_counts[et] = edge_type_counts.get(et, 0) + 1

    # Date range
    dates = [datetime.fromisoformat(n["data"]["created"].replace("Z", "+00:00")) for n in nodes if n["data"].get("created")]
    date_range = None
    if dates:
        date_range = {
            "min": min(dates).isoformat(),
            "max": max(dates).isoformat()
        }

    metadata = {
        "total_sources": len(nodes),
        "date_range": date_range,
        "source_type_counts": source_type_counts,
        "edge_type_counts": edge_type_counts
    }

    return {
        "nodes": nodes,
        "edges": all_edges,
        "metadata": metadata
    }


async def get_neighborhood(
    source_id: str,
    depth: int = 1,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get neighborhood of a source (connected sources) up to specified depth.
    Uses BFS to expand from source.

    Args:
        source_id: Starting source ID
        depth: How many hops to expand (1-3)
        filters: Same filters as get_graph_data

    Returns:
        Dict with nodes and edges for neighborhood
    """
    filters = filters or {}
    depth = min(depth, 3)  # Limit to 3 hops max

    # BFS expansion
    visited = set()
    current_level = {source_id}
    all_source_ids = {source_id}

    for _ in range(depth):
        if not current_level:
            break

        # Get connected sources for current level
        next_level = set()

        async with db_connection() as db:
            # Get semantic connections
            placeholders = ",".join([f":id{i}" for i in range(len(current_level))])
            params = {f"id{i}": sid for i, sid in enumerate(current_level)}
            params["threshold"] = filters.get("semantic_threshold", 0.7)

            semantic_neighbors = await db.query(
                f"""SELECT related_source_id FROM source_similarities
                   WHERE source_id IN ({placeholders})
                   AND similarity_score >= :threshold""",
                params
            )
            for n in semantic_neighbors:
                next_level.add(n["related_source_id"])

            # Get notebook connections
            notebook_neighbors = await db.query(
                f"""SELECT ns2.source_id
                   FROM notebook_source ns1
                   JOIN notebook_source ns2 ON ns1.notebook_id = ns2.notebook_id
                   WHERE ns1.source_id IN ({placeholders})
                   AND ns2.source_id != ns1.source_id""",
                params
            )
            for n in notebook_neighbors:
                next_level.add(n["source_id"])

        # Remove already visited
        next_level -= visited
        next_level -= current_level

        # Update state
        visited.update(current_level)
        all_source_ids.update(next_level)
        current_level = next_level

    # Get full graph data for discovered sources
    filters_copy = filters.copy()
    filters_copy["source_ids"] = list(all_source_ids)

    # Build graph with discovered sources
    return await get_graph_data("global", None, filters_copy)


async def save_layout(
    name: str,
    scope: str,
    scope_id: Optional[str],
    layout_data: Dict[str, Any],
    description: Optional[str] = None
) -> str:
    """
    Save custom node layout positions.

    Args:
        name: Layout name
        scope: 'global' or 'notebook'
        scope_id: notebook_id if scope='notebook'
        layout_data: Dict of node positions: { node_id: { x, y } }
        description: Optional description

    Returns:
        Created layout ID
    """
    layout_id = str(uuid.uuid4())

    async with db_connection() as db:
        await db.execute(
            """INSERT INTO graph_layouts (id, name, description, scope, scope_id, layout_data, created, updated)
               VALUES (:id, :name, :description, :scope, :scope_id, :layout_data, :created, :updated)""",
            {
                "id": layout_id,
                "name": name,
                "description": description,
                "scope": scope,
                "scope_id": scope_id,
                "layout_data": json.dumps(layout_data),
                "created": datetime.utcnow().isoformat(),
                "updated": datetime.utcnow().isoformat()
            }
        )

    return layout_id


async def load_layout(layout_id: str) -> Optional[Dict[str, Any]]:
    """
    Load saved layout by ID.

    Args:
        layout_id: Layout ID to load

    Returns:
        Layout dict with id, name, scope, scope_id, layout_data or None
    """
    async with db_connection() as db:
        layout = await db.query(
            "SELECT * FROM graph_layouts WHERE id = :id",
            {"id": layout_id},
            fetch_one=True
        )

        if layout:
            layout["layout_data"] = json.loads(layout["layout_data"])

        return layout


async def list_layouts(scope: str, scope_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List saved layouts for a scope.

    Args:
        scope: 'global' or 'notebook'
        scope_id: notebook_id if scope='notebook'

    Returns:
        List of layout dicts (without layout_data for efficiency)
    """
    async with db_connection() as db:
        if scope == "global":
            layouts = await db.query(
                "SELECT id, name, description, scope, created, updated FROM graph_layouts WHERE scope = :scope ORDER BY updated DESC",
                {"scope": "global"}
            )
        else:
            layouts = await db.query(
                "SELECT id, name, description, scope, scope_id, created, updated FROM graph_layouts WHERE scope = :scope AND scope_id = :scope_id ORDER BY updated DESC",
                {"scope": "notebook", "scope_id": scope_id}
            )

        return layouts


async def delete_layout(layout_id: str):
    """Delete a saved layout."""
    async with db_connection() as db:
        await db.execute(
            "DELETE FROM graph_layouts WHERE id = :id",
            {"id": layout_id}
        )


async def update_layout(layout_id: str, layout_data: Dict[str, Any]):
    """Update layout positions."""
    async with db_connection() as db:
        await db.execute(
            "UPDATE graph_layouts SET layout_data = :data, updated = :updated WHERE id = :id",
            {
                "id": layout_id,
                "data": json.dumps(layout_data),
                "updated": datetime.utcnow().isoformat()
            }
        )


# ============================================================================
# Classification Graph Functions (NEW)
# ============================================================================

async def build_classification_edges(
    source_ids: List[str],
    status_filter: Optional[str] = "approved"
) -> List[Dict[str, Any]]:
    """
    Build edges between sources and their classification nodes.

    Args:
        source_ids: List of source IDs
        status_filter: Filter by approval status ('approved', 'pending', 'rejected', None for all)

    Returns:
        List of edges with type='classified_as', styled by approval status
    """
    if not source_ids:
        return []

    async with db_connection() as db:
        placeholders = ",".join([f":id{i}" for i in range(len(source_ids))])
        params = {f"id{i}": sid for i, sid in enumerate(source_ids)}

        query = f"""
            SELECT sc.source_id, sc.classification_id, sc.confidence, sc.status,
                   ct.name as classification_name, ct.level
            FROM source_classifications sc
            INNER JOIN classification_types ct ON sc.classification_id = ct.id
            WHERE sc.source_id IN ({placeholders})
        """

        if status_filter:
            query += " AND sc.status = :status"
            params["status"] = status_filter

        results = await db.query(query, params)

        edges = []
        for row in results:
            edge = {
                "id": f"classified-{row['source_id']}-{row['classification_id']}",
                "source": row["source_id"],
                "target": row["classification_id"],
                "type": "relationship",
                "label": f"{row['confidence']:.0%}",
                "data": {
                    "relationship_type": "classified_as",
                    "strength": row["confidence"],
                    "metadata": {
                        "status": row["status"],
                        "classification_name": row["classification_name"],
                        "level": row["level"]
                    }
                }
            }
            edges.append(edge)

        return edges


async def build_classification_hierarchy_edges() -> List[Dict[str, Any]]:
    """
    Build parent-child hierarchy edges between classification nodes.

    Returns:
        List of edges with type='parent_child'
    """
    async with db_connection() as db:
        # Get all parent-child relationships
        results = await db.query(
            """SELECT cr.source_classification_id as parent_id,
                      cr.target_classification_id as child_id,
                      cr.strength,
                      parent.name as parent_name,
                      child.name as child_name
               FROM classification_relationships cr
               INNER JOIN classification_types parent ON cr.source_classification_id = parent.id
               INNER JOIN classification_types child ON cr.target_classification_id = child.id
               WHERE cr.relationship_type = 'parent_child'""",
            {}
        )

        edges = []
        for row in results:
            edge = {
                "id": f"hierarchy-{row['parent_id']}-{row['child_id']}",
                "source": row["parent_id"],
                "target": row["child_id"],
                "type": "relationship",
                "label": "",
                "data": {
                    "relationship_type": "parent_child",
                    "strength": row.get("strength", 1.0),
                    "metadata": {
                        "parent_name": row["parent_name"],
                        "child_name": row["child_name"]
                    }
                },
                "animated": False,
                "markerEnd": {"type": "arrowclosed"}
            }
            edges.append(edge)

        return edges


async def get_classification_graph_data(
    scope: str = "global",
    scope_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build mixed graph with both source nodes and classification nodes.

    Args:
        scope: 'global' or 'notebook'
        scope_id: notebook_id if scope='notebook'
        filters: Dict with:
            - source_types: List of source types to include
            - classification_levels: List of levels (0, 1, 2) to include
            - show_pending: Whether to show pending classifications
            - show_approved: Whether to show approved classifications
            - date_from, date_to: Date range filters
            - semantic_threshold: Min similarity for semantic edges

    Returns:
        Dict with nodes, edges, metadata
    """
    filters = filters or {}

    # Get source nodes (existing function)
    source_graph = await get_graph_data(scope, scope_id, filters)
    nodes = source_graph["nodes"]
    edges = source_graph["edges"]

    # Get classification nodes
    async with db_connection() as db:
        # Build classification query
        class_query = "SELECT id, name, description, classification_type, level, color, icon FROM classification_types WHERE 1=1"
        class_params = {}

        if filters.get("classification_levels"):
            level_placeholders = ",".join([f":level{i}" for i in range(len(filters["classification_levels"]))])
            class_params.update({f"level{i}": level for i, level in enumerate(filters["classification_levels"])})
            class_query += f" AND level IN ({level_placeholders})"

        classifications = await db.query(class_query, class_params)

        # Add classification nodes
        for classification in classifications:
            # Count sources for this classification
            status_filter = []
            if filters.get("show_approved", True):
                status_filter.append("'approved'")
            if filters.get("show_pending", False):
                status_filter.append("'pending'")

            status_clause = f"AND sc.status IN ({','.join(status_filter)})" if status_filter else ""

            source_count_result = await db.query(
                f"""SELECT COUNT(*) as count FROM source_classifications sc
                   WHERE sc.classification_id = :classification_id {status_clause}""",
                {"classification_id": classification["id"]}
            )
            source_count = source_count_result[0]["count"] if source_count_result else 0

            # Count children
            child_count_result = await db.query(
                "SELECT COUNT(*) as count FROM classification_types WHERE parent_id = :parent_id",
                {"parent_id": classification["id"]}
            )
            child_count = child_count_result[0]["count"] if child_count_result else 0

            # Count pending
            pending_count_result = await db.query(
                """SELECT COUNT(*) as count FROM source_classifications
                   WHERE classification_id = :classification_id AND status = 'pending'""",
                {"classification_id": classification["id"]}
            )
            pending_count = pending_count_result[0]["count"] if pending_count_result else 0

            # Add node with fields matching GraphNode schema
            node = {
                "id": classification["id"],
                "type": classification["classification_type"],  # 'category', 'topic', 'project', 'subtopic'
                "label": classification["name"],  # REQUIRED
                "position": {"x": 0, "y": 0},  # Will be set by layout
                "data": {
                    # Classification-specific fields
                    "id": classification["id"],
                    "name": classification["name"],
                    "description": classification.get("description"),
                    "classification_type": classification["classification_type"],
                    "level": classification["level"],
                    "sourceCount": source_count,
                    "childCount": child_count,
                    "pendingCount": pending_count,
                    "color": classification.get("color"),
                    "icon": classification.get("icon"),
                    # Required fields for GraphNodeData schema compatibility
                    "title": classification["name"],  # REQUIRED
                    "source_type": "text",  # REQUIRED (placeholder for classification nodes)
                    "created": classification.get("created", ""),  # REQUIRED
                    "updated": classification.get("updated", ""),  # REQUIRED
                    "chunk_count": 0,
                    "topics": [],
                    "connection_count": source_count,
                    "notebooks": []
                }
            }
            nodes.append(node)

    # Get source IDs for edge building
    source_ids = [n["id"] for n in nodes if n.get("type") == "source"]

    # Build classification edges
    status_filter = None
    if filters.get("show_approved") and not filters.get("show_pending"):
        status_filter = "approved"
    elif filters.get("show_pending") and not filters.get("show_approved"):
        status_filter = "pending"

    classification_edges = await build_classification_edges(source_ids, status_filter)
    edges.extend(classification_edges)

    # Build hierarchy edges if requested
    if filters.get("show_hierarchy", True):
        hierarchy_edges = await build_classification_hierarchy_edges()
        edges.extend(hierarchy_edges)

    # Metadata
    source_node_count = len([n for n in nodes if n.get("type") in ["file", "url", "text", "youtube", "hana_table", "api"]])
    metadata = {
        "total_sources": source_node_count,  # REQUIRED
        "total_nodes": len(nodes),
        "source_nodes": source_node_count,
        "classification_nodes": len([n for n in nodes if n.get("type") not in ["file", "url", "text", "youtube", "hana_table", "api"]]),
        "total_edges": len(edges),
        "classification_edges": len([e for e in edges if e["data"]["relationship_type"] == "classified_as"]),
        "hierarchy_edges": len([e for e in edges if e["data"]["relationship_type"] == "parent_child"]),
        "source_type_counts": {},
        "edge_type_counts": {}
    }

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": metadata
    }

