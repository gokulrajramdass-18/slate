"""
LightRAG Hybrid Search Strategy.

Multi-stage retrieval combining entity extraction, graph traversal,
community context, and traditional vector search with graph-aware re-ranking.
"""

import json
from typing import List, Dict, Any, Optional
import logging

from open_notebook.search.strategies import SearchStrategy, SearchResult, SearchFilters
from open_notebook.search.vector import VectorSearch
from open_notebook.search.entity_vector import EntityVectorSearch
from open_notebook.domain.entity import Entity, Community
from open_notebook.config import get_database

logger = logging.getLogger(__name__)


class LightRAGHybridSearch(SearchStrategy):
    """
    LightRAG hybrid search combining all LightRAG components.

    Multi-stage pipeline:
    1. Entity extraction from query
    2. Graph traversal (get entity neighborhoods)
    3. Community context gathering
    4. Traditional vector search with expanded query
    5. Graph-aware re-ranking
    """

    def __init__(
        self,
        vector_weight: float = 0.4,
        graph_weight: float = 0.3,
        entity_match_weight: float = 0.2,
        community_weight: float = 0.1,
        traversal_depth: int = 2,
        include_communities: bool = True
    ):
        """
        Initialize LightRAG hybrid search.

        Args:
            vector_weight: Weight for vector similarity (α)
            graph_weight: Weight for graph centrality (β)
            entity_match_weight: Weight for entity matching (γ)
            community_weight: Weight for community membership (δ)
            traversal_depth: Graph traversal depth
            include_communities: Whether to use community context
        """
        self.vector_search = VectorSearch()
        self.entity_vector_search = EntityVectorSearch(
            vector_weight=vector_weight,
            graph_weight=graph_weight,
            entity_match_weight=entity_match_weight,
            expansion_depth=traversal_depth
        )
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        self.entity_match_weight = entity_match_weight
        self.community_weight = community_weight
        self.traversal_depth = traversal_depth
        self.include_communities = include_communities

    async def search(
        self,
        query: str,
        filters: SearchFilters,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Perform LightRAG hybrid search.

        Args:
            query: Search query
            filters: Search filters
            limit: Maximum results

        Returns:
            List of search results with comprehensive scoring
        """
        logger.info(f"Starting LightRAG hybrid search for: {query}")

        # Stage 1: Entity extraction
        entities = await self._extract_query_entities(query)

        if not entities:
            logger.debug("No entities found, falling back to vector search")
            return await self.vector_search.search(query, filters, limit)

        # Stage 2: Graph traversal
        graph_context = await self._traverse_entity_graph(entities, filters)

        # Stage 3: Community context
        community_context = None
        if self.include_communities:
            community_context = await self._get_community_context(entities)

        # Stage 4: Build expanded query
        expanded_query = await self._build_expanded_query(
            query,
            graph_context,
            community_context
        )

        # Stage 5: Vector search with expanded query
        vector_results = await self.vector_search.search(
            expanded_query,
            filters,
            limit * 3
        )

        # Stage 6: Graph-aware re-ranking
        final_results = await self._rerank_with_graph_and_community(
            vector_results,
            graph_context,
            community_context,
            limit
        )

        logger.info(f"LightRAG search returned {len(final_results)} results")

        return final_results

    async def _extract_query_entities(self, query: str) -> List[Entity]:
        """Extract and find entities from query."""
        # Simple extraction (same as EntityVectorSearch)
        words = query.split()
        entity_names = []
        current_entity = []

        for word in words:
            clean_word = word.strip('.,?!;:')
            if clean_word and clean_word[0].isupper():
                current_entity.append(clean_word)
            else:
                if current_entity:
                    entity_names.append(' '.join(current_entity))
                    current_entity = []

        if current_entity:
            entity_names.append(' '.join(current_entity))

        # Find matching entities
        matched_entities = []
        for name in entity_names:
            results = await Entity.search(query=name, limit=3)
            matched_entities.extend(results)

        # Deduplicate
        seen = set()
        unique = []
        for entity in matched_entities:
            if entity.id not in seen:
                seen.add(entity.id)
                unique.append(entity)

        logger.debug(f"Extracted {len(unique)} entities from query")
        return unique

    async def _traverse_entity_graph(
        self,
        entities: List[Entity],
        filters: SearchFilters
    ) -> Dict[str, Any]:
        """
        Traverse entity graph to gather related entities and relationships.

        Returns context dict with entities, relationships, and metadata.
        """
        all_entity_ids = set([e.id for e in entities])
        all_relationships = []

        # Traverse from each entity
        for entity in entities:
            related = await Entity.get_related(
                entity.id,
                depth=self.traversal_depth
            )

            for rel_info in related:
                all_entity_ids.add(rel_info['entity_id'])
                if 'relationship' in rel_info:
                    all_relationships.append(rel_info['relationship'])

        # Fetch all entities
        all_entities = []
        for entity_id in all_entity_ids:
            entity = await Entity.get(entity_id)
            if entity:
                all_entities.append(entity)

        context = {
            'entities': all_entities,
            'relationships': all_relationships,
            'entity_count': len(all_entities),
            'relationship_count': len(all_relationships)
        }

        logger.debug(f"Graph traversal found {len(all_entities)} entities and {len(all_relationships)} relationships")

        return context

    async def _get_community_context(
        self,
        entities: List[Entity]
    ) -> Optional[Dict[str, Any]]:
        """
        Get community context for entities.

        Returns community summaries and central entities.
        """
        if not entities:
            return None

        communities = []
        community_ids_seen = set()

        for entity in entities:
            community_data = await Entity.get_community(entity.id)

            if community_data and community_data['id'] not in community_ids_seen:
                community_ids_seen.add(community_data['id'])
                communities.append(community_data)

        if not communities:
            return None

        context = {
            'communities': communities,
            'community_count': len(communities),
            'summaries': [c.get('description', '') for c in communities if c.get('description')]
        }

        logger.debug(f"Found {len(communities)} communities for query entities")

        return context

    async def _build_expanded_query(
        self,
        original_query: str,
        graph_context: Dict[str, Any],
        community_context: Optional[Dict[str, Any]]
    ) -> str:
        """
        Build expanded query incorporating entity and community context.

        Appends related entity names and community keywords to original query.
        """
        expanded_parts = [original_query]

        # Add related entity names (top 5 by centrality)
        if graph_context and graph_context['entities']:
            entity_names = [e.name for e in graph_context['entities'][:5]]
            expanded_parts.append(' '.join(entity_names))

        # Add community keywords
        if community_context and community_context['summaries']:
            # Extract key terms from community summaries
            summaries_text = ' '.join(community_context['summaries'])
            expanded_parts.append(summaries_text[:200])  # Limit length

        expanded_query = ' '.join(expanded_parts)

        logger.debug(f"Expanded query from {len(original_query)} to {len(expanded_query)} characters")

        return expanded_query

    async def _rerank_with_graph_and_community(
        self,
        vector_results: List[SearchResult],
        graph_context: Dict[str, Any],
        community_context: Optional[Dict[str, Any]],
        limit: int
    ) -> List[SearchResult]:
        """
        Re-rank results using graph centrality and community membership.

        Score = α * vector_sim + β * graph_centrality + γ * entity_match + δ * community_membership
        """
        db = get_database()

        # Build entity ID to source ID mapping
        entity_source_map = {}
        if graph_context and graph_context['entities']:
            for entity in graph_context['entities']:
                if entity.source_id not in entity_source_map:
                    entity_source_map[entity.source_id] = []
                entity_source_map[entity.source_id].append(entity.id)

        # Calculate graph centrality by source
        centrality_by_source = {}
        if graph_context and graph_context['relationships']:
            # Count relationships per entity
            entity_rel_count = {}
            for rel in graph_context['relationships']:
                source_entity = rel.get('source_entity_id')
                target_entity = rel.get('target_entity_id')

                entity_rel_count[source_entity] = entity_rel_count.get(source_entity, 0) + 1
                entity_rel_count[target_entity] = entity_rel_count.get(target_entity, 0) + 1

            # Map to sources
            for source_id, entity_ids in entity_source_map.items():
                total_centrality = sum([entity_rel_count.get(eid, 0) for eid in entity_ids])
                max_centrality = max(entity_rel_count.values()) if entity_rel_count else 1
                centrality_by_source[source_id] = total_centrality / max_centrality if max_centrality > 0 else 0

        # Calculate community membership scores
        community_by_source = {}
        if community_context and community_context['communities']:
            for community in community_context['communities']:
                entity_ids = community.get('entity_ids', [])
                if isinstance(entity_ids, str):
                    entity_ids = json.loads(entity_ids)

                # Map to sources
                for entity_id in entity_ids:
                    entity = await Entity.get(entity_id)
                    if entity:
                        community_by_source[entity.source_id] = 1.0

        # Re-score results
        for result in vector_results:
            source_id = result.source_id

            # Base vector score
            vector_score = result.score

            # Graph centrality score
            graph_score = centrality_by_source.get(source_id, 0.0)

            # Entity match score (1.0 if source has entities from query)
            entity_score = 1.0 if source_id in entity_source_map else 0.0

            # Community membership score
            community_score = community_by_source.get(source_id, 0.0)

            # Combined score
            final_score = (
                self.vector_weight * vector_score +
                self.graph_weight * graph_score +
                self.entity_match_weight * entity_score +
                self.community_weight * community_score
            )

            result.score = final_score

            # Add metadata about scoring
            result.metadata['lightrag_scores'] = {
                'vector': vector_score,
                'graph': graph_score,
                'entity': entity_score,
                'community': community_score,
                'final': final_score
            }

        # Sort and return top results
        sorted_results = sorted(vector_results, key=lambda r: r.score, reverse=True)

        return sorted_results[:limit]
