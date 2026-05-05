"""
Agentic RAG Search Strategy

Multi-step LangGraph workflow for complex queries:
1. Query Analysis - Extract intent and entities
2. Query Decomposition - Break into sub-queries
3. Parallel Retrieval - Execute sub-queries with dynamic strategy selection
4. Relevance Filtering - Filter results using LLM
5. Answer Synthesis - Generate answer with citations
"""

import asyncio
from typing import List, Optional, Dict, Any, TypedDict, Annotated
from dataclasses import dataclass
from langgraph.graph import StateGraph, END
from open_notebook.search.strategies import (
    SearchStrategy,
    SearchResult,
    SearchFilters,
    SearchExecutionError
)
from open_notebook.search.keyword import KeywordSearch
from open_notebook.search.vector import VectorSearch
from open_notebook.search.hybrid import HybridSearch


@dataclass
class SubQuery:
    """A decomposed sub-query with strategy."""
    query: str
    strategy: str  # 'keyword', 'vector', or 'hybrid'
    reason: str


class AgenticRAGState(TypedDict):
    """State passed through the LangGraph workflow."""
    original_query: str
    intent: str
    entities: List[str]
    sub_queries: List[SubQuery]
    graph_context: Optional[Dict[str, Any]]  # NEW: Entity graph context
    retrieved_results: List[SearchResult]
    filtered_results: List[SearchResult]
    final_answer: str
    citations: List[Dict[str, Any]]
    error: Optional[str]


class AgenticRAGSearch(SearchStrategy):
    """
    Agentic RAG search using LangGraph for multi-step reasoning.

    Configuration options:
        - llm_model: LLM model to use for reasoning (required)
        - max_iterations: Maximum workflow iterations (default: 5)
        - relevance_threshold: Minimum relevance for filtering (default: 0.6)
        - max_sub_queries: Maximum number of sub-queries (default: 5)
        - keyword_config: Config for keyword search
        - vector_config: Config for vector search
        - hybrid_config: Config for hybrid search
    """

    @property
    def name(self) -> str:
        return "agentic_rag"

    @property
    def description(self) -> str:
        return "Multi-step LangGraph workflow with dynamic strategy selection and synthesis"

    def __init__(self, database, config: Optional[Dict[str, Any]] = None):
        super().__init__(database, config)
        self._workflow = None
        self._llm = None

    async def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Execute agentic RAG workflow.

        Args:
            query: Complex search query
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of SearchResult with synthesized answer
        """
        if not query or not query.strip():
            return []

        # Initialize LLM
        llm_model_id = self.config.get('llm_model')
        if not llm_model_id:
            raise SearchExecutionError("llm_model not configured for agentic RAG")

        # Get credentials for the LLM model
        try:
            from api.routers.credentials import _credentials_store

            credential = _credentials_store.get(llm_model_id)
            if not credential:
                raise SearchExecutionError(f"LLM model credential not found: {llm_model_id}")

            # Extract provider and model name
            # Format: "anthropic--claude-4.5-sonnet"
            raw_model_name = credential.get("model_name", credential.get("name", "gpt-3.5-turbo"))
            api_key = credential.get("api_key")

            if "--" in raw_model_name:
                provider, model = raw_model_name.split("--", 1)
            else:
                provider = "openai"
                model = raw_model_name

            # Use native LangChain chat models for direct API calls
            if provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                self._llm = ChatAnthropic(
                    model=model,
                    anthropic_api_key=api_key,
                    temperature=0.0
                )
            elif provider == "openai":
                from langchain_openai import ChatOpenAI
                api_base = credential.get("base_url", "https://api.openai.com/v1")
                self._llm = ChatOpenAI(
                    model=model,
                    openai_api_key=api_key,
                    base_url=api_base,
                    temperature=0.0
                )
            elif provider == "google":
                from langchain_google_vertexai import ChatVertexAI
                self._llm = ChatVertexAI(
                    model=model,
                    google_api_key=api_key,
                    temperature=0.0
                )
            else:
                # Fallback to OpenAI-compatible API
                from langchain_openai import ChatOpenAI
                api_base = credential.get("base_url", "https://api.openai.com/v1")
                self._llm = ChatOpenAI(
                    model=model,
                    openai_api_key=api_key,
                    base_url=api_base,
                    temperature=0.0
                )

        except Exception as e:
            raise SearchExecutionError(f"Failed to initialize LLM: {str(e)}")

        # Build workflow if not already built
        if not self._workflow:
            self._workflow = self._build_workflow()

        # Initialize state
        initial_state: AgenticRAGState = {
            'original_query': query,
            'intent': '',
            'entities': [],
            'sub_queries': [],
            'retrieved_results': [],
            'filtered_results': [],
            'final_answer': '',
            'citations': [],
            'error': None
        }

        # Store filters for use in nodes
        self._filters = filters
        self._limit = limit

        try:
            # Execute workflow
            final_state = await self._workflow.ainvoke(initial_state)

            # Check for errors
            if final_state.get('error'):
                raise SearchExecutionError(f"Workflow error: {final_state['error']}")

            # Return filtered results with answer as first result
            results = final_state.get('filtered_results', [])

            print(f"[Agentic RAG] Final state: {len(results)} filtered results, final_answer exists: {bool(final_state.get('final_answer'))}")

            # Add synthesized answer as a special result
            if final_state.get('final_answer'):
                answer_result = SearchResult(
                    source_id='synthesized',
                    chunk_id=None,
                    content=final_state['final_answer'],
                    score=1.0,
                    highlights=[],
                    metadata={
                        'type': 'synthesized_answer',
                        'citations': final_state.get('citations', []),
                        'sub_queries': [sq.query for sq in final_state.get('sub_queries', [])]
                    },
                    strategy=self.name
                )
                final_results = [answer_result] + results[:limit]
                print(f"[Agentic RAG] Returning {len(final_results)} total results (1 synth + {len(results[:limit])} filtered)")
                return final_results

            return results[:limit]

        except Exception as e:
            raise SearchExecutionError(f"Agentic RAG failed: {str(e)}")

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgenticRAGState)

        # Add nodes
        workflow.add_node("analyze_query", self._analyze_query_node)
        workflow.add_node("decompose_query", self._decompose_query_node)
        workflow.add_node("graph_traversal", self._graph_traversal_node)  # NEW
        workflow.add_node("parallel_retrieval", self._parallel_retrieval_node)
        workflow.add_node("filter_relevance", self._filter_relevance_node)
        workflow.add_node("synthesize_answer", self._synthesize_answer_node)

        # Add edges
        workflow.set_entry_point("analyze_query")
        workflow.add_edge("analyze_query", "decompose_query")
        workflow.add_edge("decompose_query", "graph_traversal")  # NEW
        workflow.add_edge("graph_traversal", "parallel_retrieval")  # NEW
        workflow.add_edge("parallel_retrieval", "filter_relevance")
        workflow.add_edge("filter_relevance", "synthesize_answer")
        workflow.add_edge("synthesize_answer", END)

        return workflow.compile()

    async def _analyze_query_node(self, state: AgenticRAGState) -> AgenticRAGState:
        """Node 1: Analyze query to extract intent and entities."""
        query = state['original_query']

        prompt = f"""Analyze the following search query and extract:
1. The user's intent (what they want to find)
2. Key entities and concepts

Query: {query}

Respond in JSON format:
{{
    "intent": "brief description of intent",
    "entities": ["entity1", "entity2", ...]
}}
"""

        try:
            # Call LLM
            response = await self._llm.ainvoke(prompt)
            import json
            import re

            # Extract JSON from response (may include thinking/reasoning text)
            content = response.content

            # Try to find JSON object in the response
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                result = json.loads(content)

            state['intent'] = result.get('intent', '')
            state['entities'] = result.get('entities', [])

        except Exception as e:
            state['error'] = f"Query analysis failed: {str(e)}"

        return state

    async def _decompose_query_node(self, state: AgenticRAGState) -> AgenticRAGState:
        """Node 2: Decompose query into sub-queries with strategy selection."""
        query = state['original_query']
        intent = state['intent']
        entities = state['entities']
        max_sub_queries = self.config.get('max_sub_queries', 5)

        prompt = f"""Break down this search query into sub-queries for optimal retrieval.
For each sub-query, select the best search strategy:
- keyword: for exact phrase matching, known terminology
- vector: for semantic similarity, concept matching
- hybrid: for comprehensive search combining both

Original query: {query}
Intent: {intent}
Entities: {', '.join(entities)}

Maximum {max_sub_queries} sub-queries.

Respond in JSON format:
{{
    "sub_queries": [
        {{"query": "sub-query text", "strategy": "keyword|vector|hybrid", "reason": "why this strategy"}},
        ...
    ]
}}
"""

        try:
            response = await self._llm.ainvoke(prompt)
            import json
            import re

            # Extract JSON from response
            content = response.content
            json_match = re.search(r'\{[^{}]*\[[^\]]*\][^{}]*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(0))
            else:
                result = json.loads(content)

            sub_queries = []
            for sq in result.get('sub_queries', [])[:max_sub_queries]:
                sub_queries.append(SubQuery(
                    query=sq['query'],
                    strategy=sq['strategy'],
                    reason=sq.get('reason', '')
                ))

            state['sub_queries'] = sub_queries

        except Exception as e:
            # Fallback: use original query with hybrid strategy
            state['sub_queries'] = [SubQuery(
                query=query,
                strategy='hybrid',
                reason='Fallback due to decomposition error'
            )]

        return state

    async def _graph_traversal_node(self, state: AgenticRAGState) -> AgenticRAGState:
        """
        Node 2.5: Graph traversal for entity-aware context.

        Extract entities from query → Find in entity graph →
        Traverse relationships → Collect context for retrieval.
        """
        entities = state['entities']

        if not entities:
            # No entities found, skip graph traversal
            state['graph_context'] = None
            return state

        try:
            from open_notebook.domain.entity import Entity

            # Find matching entities in graph
            matched_entities = []
            for entity_name in entities:
                results = await Entity.search(query=entity_name, limit=3)
                matched_entities.extend(results)

            if not matched_entities:
                state['graph_context'] = None
                return state

            # Deduplicate entities
            seen_ids = set()
            unique_entities = []
            for entity in matched_entities:
                if entity.id not in seen_ids:
                    seen_ids.add(entity.id)
                    unique_entities.append(entity)

            # Traverse entity graph (1-2 hops)
            all_entity_ids = set([e.id for e in unique_entities])
            all_relationships = []

            graph_depth = self.config.get('graph_traversal_depth', 2)

            for entity in unique_entities:
                related = await Entity.get_related(
                    entity.id,
                    depth=graph_depth
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

            # Build graph context
            graph_context = {
                'entities': [
                    {
                        'id': e.id,
                        'name': e.name,
                        'type': e.entity_type,
                        'description': e.description,
                        'source_id': e.source_id
                    }
                    for e in all_entities
                ],
                'relationships': [
                    {
                        'source_entity_id': r.get('source_entity_id'),
                        'target_entity_id': r.get('target_entity_id'),
                        'type': r.get('relationship_type'),
                        'context': r.get('context')
                    }
                    for r in all_relationships
                ],
                'entity_count': len(all_entities),
                'relationship_count': len(all_relationships)
            }

            state['graph_context'] = graph_context

        except Exception as e:
            # If graph traversal fails, continue without it
            print(f"Graph traversal error: {e}")
            state['graph_context'] = None

        return state

    async def _parallel_retrieval_node(self, state: AgenticRAGState) -> AgenticRAGState:
        """Node 3: Execute sub-queries in parallel with selected strategies."""
        sub_queries = state['sub_queries']

        # Create strategy instances
        keyword_search = KeywordSearch(
            self.database,
            self.config.get('keyword_config', {})
        )
        vector_search = VectorSearch(
            self.database,
            self.config.get('vector_config', {})
        )
        hybrid_search = HybridSearch(
            self.database,
            self.config.get('hybrid_config', {})
        )

        strategy_map = {
            'keyword': keyword_search,
            'vector': vector_search,
            'hybrid': hybrid_search
        }

        # Execute all sub-queries in parallel
        tasks = []
        for sq in sub_queries:
            strategy = strategy_map.get(sq.strategy, hybrid_search)
            tasks.append(
                strategy.search(sq.query, self._filters, self._limit)
            )

        try:
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect all results
            all_results = []
            for results in results_list:
                if isinstance(results, Exception):
                    continue
                all_results.extend(results)

            # Deduplicate by chunk_id (keep highest score per chunk)
            seen = {}
            for result in all_results:
                # Use chunk_id if available, otherwise fallback to source_id
                key = result.chunk_id if result.chunk_id else result.source_id
                if key not in seen or result.score > seen[key].score:
                    seen[key] = result

            state['retrieved_results'] = list(seen.values())

        except Exception as e:
            state['error'] = f"Parallel retrieval failed: {str(e)}"

        return state

    async def _filter_relevance_node(self, state: AgenticRAGState) -> AgenticRAGState:
        """Node 4: Filter results by relevance using score threshold."""
        query = state['original_query']
        results = state['retrieved_results']
        threshold = self.config.get('relevance_threshold', 0.6)

        if not results:
            state['filtered_results'] = []
            return state

        print(f"[Agentic RAG] Filtering {len(results)} retrieved results with threshold {threshold}")
        for i, r in enumerate(results[:10]):
            print(f"  Result {i+1}: score={r.score:.3f}, source_id={r.source_id[:30]}")

        # Use score threshold for filtering (simpler and more reliable than LLM filtering)
        filtered = [r for r in results if r.score >= threshold]

        print(f"[Agentic RAG] After filtering: {len(filtered)} results")

        # Sort by score
        filtered.sort(key=lambda x: x.score, reverse=True)
        state['filtered_results'] = filtered

        print(f"[Agentic RAG] Returning state with {len(state['filtered_results'])} filtered_results")

        return state

    async def _synthesize_answer_node(self, state: AgenticRAGState) -> AgenticRAGState:
        """Node 5: Synthesize final answer with citations."""
        query = state['original_query']
        results = state['filtered_results']

        print(f"[Agentic RAG Synthesize] Received {len(results)} filtered results")

        if not results:
            state['final_answer'] = "No relevant results found."
            state['citations'] = []
            return state

        # Prepare context from results
        context_parts = []
        citations = []

        for i, result in enumerate(results[:10], 1):  # Top 10
            context_parts.append(f"[{i}] {result.content}")
            citations.append({
                'index': i,
                'source_id': result.source_id,
                'title': result.metadata.get('title', 'Untitled'),
                'snippet': result.content[:200]
            })

        context = "\n\n".join(context_parts)

        prompt = f"""Based on the following search results, provide a comprehensive answer to the query.
Include citations in the format [N] where N is the result number.

Query: {query}

Results:
{context}

Provide a well-structured answer with citations:
"""

        try:
            response = await self._llm.ainvoke(prompt)
            state['final_answer'] = response.content
            state['citations'] = citations

        except Exception as e:
            state['error'] = f"Answer synthesis failed: {str(e)}"

        return state
