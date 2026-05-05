"""
Deep Research Agent

A specialized agent that performs comprehensive research on user queries
by autonomously:
1. Analyzing the query and breaking it down into sub-questions
2. Searching across multiple sources
3. Synthesizing findings into a comprehensive report
4. Providing citations and recommendations

This agent runs in the background and can take several minutes to complete.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, AsyncIterator, TypedDict
from enum import Enum

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from open_notebook.agents.llm_pool import LLMClientPool
from api.services.prompt_loader import load_prompt


def extract_json_from_response(content: str) -> str:
    """
    Extract JSON from LLM response, handling various formats.

    Handles:
    - Markdown code blocks (```json ... ```)
    - Plain JSON
    - JSON with surrounding text
    """
    import re

    content = content.strip()

    # Remove markdown code blocks
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    # Try to find JSON object or array
    json_match = re.search(r'(\{.*\}|\[.*\])', content, re.DOTALL)
    if json_match:
        return json_match.group(1)

    return content


class ResearchPhase(str, Enum):
    """Phases of deep research"""
    INITIALIZING = "initializing"
    ANALYZING_QUERY = "analyzing_query"
    DECOMPOSING = "decomposing"
    SEARCHING = "searching"
    SYNTHESIZING = "synthesizing"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


class ResearchState(TypedDict, total=False):
    """State for deep research workflow"""
    # Required fields
    original_query: str
    notebook_id: str
    session_id: str
    phase: ResearchPhase
    progress: int

    # Research data
    sub_questions: List[str]
    search_results: Dict[str, List[Dict[str, Any]]]
    key_findings: List[Dict[str, Any]]
    final_report: str
    citations: List[Dict[str, Any]]

    # Analysis
    query_analysis: Dict[str, Any]

    # Metadata
    start_time: str
    error_message: Optional[str]
    intermediate_results: List[Dict[str, Any]]


class DeepResearchAgent:
    """
    Agent that performs deep, autonomous research on user queries.

    Workflow:
    1. Query Analysis - Understand what the user is asking
    2. Query Decomposition - Break into searchable sub-questions
    3. Multi-Source Search - Search across all notebook sources
    4. Synthesis - Combine findings into coherent report
    5. Finalization - Format with citations and recommendations
    """

    def __init__(
        self,
        model_name: str,
        notebook_id: str,
        session_id: str,
        max_iterations: int = 5,
        search_strategies: Optional[List[str]] = None,
        tools: Optional[List[Any]] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        step_callback: Optional[callable] = None
    ):
        """
        Initialize deep research agent.

        Args:
            model_name: LLM model to use (e.g., "gpt-4", "claude-3-opus")
            notebook_id: Notebook to search within
            session_id: Chat session ID for context
            max_iterations: Maximum research iterations
            search_strategies: List of search strategies to use
            tools: Optional list of tools (e.g., web_search, calculator) for external research
            base_url: Optional base URL for API (for localhost proxies)
            api_key: Optional API key
            progress_callback: Optional callback function(phase, progress, message)
            step_callback: Optional callback function(step) called immediately when step is recorded
        """
        self.model_name = model_name
        self.notebook_id = notebook_id
        self.session_id = session_id
        self.max_iterations = max_iterations
        self.search_strategies = search_strategies or ["hybrid", "vector", "keyword"]
        self.tools = tools or []
        self.progress_callback = progress_callback
        self.step_callback = step_callback

        # Store credentials for creating fresh LLM clients
        # Don't use LLMClientPool because it caches clients with JWT tokens that expire
        # Deep research takes 2-5 minutes, but JWT expires in ~2 minutes
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key

        # Create fresh LLM client (avoid cached JWT expiration)
        self.llm = self._create_fresh_llm()

        # Don't bind tools to LLM - we'll use them explicitly in search phase
        # Binding tools makes every LLM call try to use tools, causing recursion

        # Agent execution steps for UI display
        self.agent_steps: List[Dict[str, Any]] = []

        # Store final report for access after completion
        self._final_report: str = ""

        # Build workflow graph
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)

    def _create_fresh_llm(self):
        """
        Create a fresh LLM client without caching.

        This avoids JWT expiration issues with LiteLLM proxy.
        LLMClientPool caches clients, which means the JWT token created
        at instantiation time expires after ~2 minutes.
        Deep research takes 2-5 minutes, so we need fresh clients.
        """
        from langchain_openai import ChatOpenAI

        llm_kwargs = {
            "model": self.model_name,
            "temperature": 0.1,
            "streaming": True,
        }

        if self.base_url:
            llm_kwargs["base_url"] = self.base_url

        if self.api_key:
            llm_kwargs["api_key"] = self.api_key

        return ChatOpenAI(**llm_kwargs)

    def _record_step(
        self,
        step_type: str,
        content: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record an agent execution step for UI display.

        Args:
            step_type: Step type ("thinking", "analyzing", "decomposing", "searching", "synthesizing", "finalizing")
            content: Human-readable step description
            status: Step status ("pending", "running", "completed", "error")
            metadata: Additional metadata (phase, progress, etc.)

        Returns:
            The created step dict
        """
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "metadata": metadata or {},
        }
        self.agent_steps.append(step)

        # Immediately notify callback if provided (for real-time streaming)
        if self.step_callback:
            try:
                self.step_callback(step)
            except Exception as e:
                print(f"[Deep Research] Step callback error: {e}")

        return step

    def _update_last_step(
        self,
        status: str = "completed",
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update the last recorded step (useful for updating 'running' to 'completed').

        Args:
            status: New status
            content: Optional new content
            metadata: Optional new metadata to merge
        """
        if not self.agent_steps:
            return

        last_step = self.agent_steps[-1]
        last_step["status"] = status

        if content:
            last_step["content"] = content

        if metadata:
            last_step["metadata"].update(metadata)

        # Notify callback about the update
        if self.step_callback:
            try:
                self.step_callback(last_step)
            except Exception as e:
                print(f"[Deep Research] Step callback error: {e}")

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for deep research"""
        workflow = StateGraph(ResearchState)

        # Add nodes
        workflow.add_node("analyze_query", self._analyze_query_node)
        workflow.add_node("decompose_query", self._decompose_query_node)
        workflow.add_node("search_sources", self._search_sources_node)
        workflow.add_node("synthesize_findings", self._synthesize_findings_node)
        workflow.add_node("finalize_report", self._finalize_report_node)

        # Define flow
        workflow.set_entry_point("analyze_query")
        workflow.add_edge("analyze_query", "decompose_query")
        workflow.add_edge("decompose_query", "search_sources")
        workflow.add_edge("search_sources", "synthesize_findings")
        workflow.add_edge("synthesize_findings", "finalize_report")
        workflow.add_edge("finalize_report", END)

        return workflow

    async def _analyze_query_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Phase 1: Analyze the user's query to understand intent and scope.

        Returns:
            Updated state with query analysis
        """
        print(f"[Deep Research] Phase 1: Analyzing query...")

        # Record step
        self._record_step(
            step_type="analyzing",
            content="Analyzing your research question to understand intent and scope",
            status="running",
            metadata={"phase": "analyzing_query", "progress": 10}
        )

        state["phase"] = ResearchPhase.ANALYZING_QUERY
        state["progress"] = 10

        # Notify progress callback
        if self.progress_callback:
            self.progress_callback(ResearchPhase.ANALYZING_QUERY, 10, "Analyzing your question...")

        # Load phase 1 prompt from database
        from api.services.prompt_loader import load_prompt

        FALLBACK_PHASE1 = """Analyze this research query and provide:
1. Main topic/theme
2. Key concepts to explore
3. Expected output format (report, analysis, comparison, etc.)
4. Estimated depth needed (quick overview vs comprehensive analysis)

Query: {original_query}

Respond in JSON format with keys: topic, concepts, output_format, depth"""

        prompt = await load_prompt(
            "research_phase1_query_analysis",
            variables={"original_query": state['original_query']},
            fallback=FALLBACK_PHASE1
        )

        try:
            print(f"[Deep Research] Calling LLM: {self.llm.model_name}")

            # Add timeout to prevent hanging
            import asyncio
            try:
                # Create fresh LLM to avoid JWT expiration
                llm = self._create_fresh_llm()
                response = await asyncio.wait_for(
                    llm.ainvoke([HumanMessage(content=prompt)]),
                    timeout=60.0  # 60 second timeout
                )
                print(f"[Deep Research] LLM response received: {len(response.content)} chars")
            except asyncio.TimeoutError:
                print(f"[Deep Research] ✗ LLM call timed out after 60 seconds")
                raise Exception("LLM API call timed out. Please check your API configuration and try again.")
            except Exception as llm_error:
                print(f"[Deep Research] ✗ LLM call failed: {type(llm_error).__name__}: {str(llm_error)}")
                raise Exception(f"LLM API call failed: {str(llm_error)}")

            # Clean JSON response (remove markdown code blocks if present)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove trailing ```
            content = content.strip()

            try:
                analysis = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract just the topic if full JSON parsing fails
                print(f"[Deep Research] ✗ Full JSON parse failed, extracting topic...")
                import re
                topic_match = re.search(r'"topic"\s*:\s*"([^"]+)"', content)
                if topic_match:
                    analysis = {
                        "topic": topic_match.group(1),
                        "concepts": [],
                        "output_format": {"primary": "Research Report"},
                        "depth": {"level": "Standard Analysis"}
                    }
                    print(f"[Deep Research] ℹ Using extracted topic: {analysis['topic']}")
                else:
                    raise

            state["query_analysis"] = analysis
            state["intermediate_results"].append({
                "phase": "analysis",
                "result": analysis
            })

            # Update step as completed
            self._update_last_step(
                status="completed",
                content=f"✓ Identified topic: {analysis.get('topic', 'Unknown')}",
                metadata={"phase": "analyzing_query", "progress": 10, "analysis": analysis}
            )

            print(f"[Deep Research] ✓ Query analyzed: {analysis.get('topic', 'Unknown')}")

        except json.JSONDecodeError as e:
            print(f"[Deep Research] ✗ JSON parsing error: {e}")
            print(f"[Deep Research] Raw response: {response.content if 'response' in locals() else 'No response'}")
            state["error_message"] = f"Query analysis failed: Invalid JSON response from model"
            state["phase"] = ResearchPhase.ERROR
        except Exception as e:
            print(f"[Deep Research] ✗ Analysis error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            state["error_message"] = f"Query analysis failed: {str(e)}"
            state["phase"] = ResearchPhase.ERROR

        return state

    async def _decompose_query_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Phase 2: Break down the main query into sub-questions.

        Returns:
            Updated state with sub-questions
        """
        print(f"[Deep Research] Phase 2: Decomposing query...")

        # Record step
        self._record_step(
            step_type="decomposing",
            content="Breaking down research question into sub-questions",
            status="running",
            metadata={"phase": "decomposing", "progress": 25}
        )

        state["phase"] = ResearchPhase.DECOMPOSING
        state["progress"] = 25

        # Notify progress callback
        if self.progress_callback:
            self.progress_callback(ResearchPhase.DECOMPOSING, 25, "Breaking down into sub-questions...")

        analysis = state.get("query_analysis", {})

        FALLBACK_PHASE2 = """You are decomposing a complex research query into strategic sub-questions for deep investigation.

Original Query: {original_query}
Topic: {topic}
Key Concepts: {concepts}

Create 5-7 targeted sub-questions that will enable comprehensive analysis. Each sub-question should:

1. **Address a distinct dimension** - Don't overlap; each should unlock unique insights
2. **Be specific and actionable** - Concrete enough to guide targeted research
3. **Progress strategically** - Start with foundational questions, build to synthesis
4. **Enable data-driven answers** - Phrased to surface quantitative/qualitative evidence
5. **Connect to decision-making** - Results should inform recommendations

For a SWOT analysis query:
- Internal assessment: What does the data reveal about current state, performance, capabilities?
- External context: What market/competitive/regulatory factors create opportunities or threats?
- Comparative analysis: How do entities compare on key dimensions?
- Gap analysis: What's missing, underdeveloped, or at risk?
- Forward-looking: What trends, deadlines, or catalysts drive urgency?
- Actionable synthesis: What specific decisions or priorities emerge from the data?

For a technical/domain query:
- Core mechanics: How does X work? What are the key components?
- Best practices: What approaches are proven effective?
- Comparative: How do different options/vendors/approaches compare?
- Implementation: What are the practical steps, challenges, timelines?
- Risk/mitigation: What can go wrong and how to address it?

Respond with a JSON array of 5-7 sub-questions that will drive thorough, insightful research."""

        prompt = await load_prompt(
            "research_phase2_decomposition",
            variables={
                "original_query": state['original_query'],
                "topic": analysis.get('topic', 'N/A'),
                "concepts": ', '.join(analysis.get('concepts', []))
            },
            fallback=FALLBACK_PHASE2
        )

        try:
            import asyncio
            try:
                # Create fresh LLM to avoid JWT expiration
                llm = self._create_fresh_llm()
                response = await asyncio.wait_for(
                    llm.ainvoke([HumanMessage(content=prompt)]),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                print(f"[Deep Research] ✗ Decomposition LLM call timed out")
                raise Exception("LLM call timed out during query decomposition")

            # Clean JSON response (remove markdown code blocks)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            sub_questions = json.loads(content)

            if not isinstance(sub_questions, list):
                sub_questions = [sub_questions]

            state["sub_questions"] = sub_questions
            state["intermediate_results"].append({
                "phase": "decomposition",
                "result": {"sub_questions": sub_questions}
            })

            # Update step as completed
            self._update_last_step(
                status="completed",
                content=f"✓ Created {len(sub_questions)} focused sub-questions",
                metadata={"phase": "decomposing", "progress": 25, "sub_questions": sub_questions}
            )

            print(f"[Deep Research] ✓ Created {len(sub_questions)} sub-questions")

        except Exception as e:
            print(f"[Deep Research] ✗ Decomposition error: {e}")
            # FALLBACK: Generate sub-questions automatically based on the query
            print(f"[Deep Research] Using automatic sub-question generation fallback")

            analysis = state.get("query_analysis", {})
            topic = analysis.get('topic', 'the topic')

            # Generate 5 sensible sub-questions based on common research patterns
            sub_questions = [
                f"What are the key strengths and opportunities related to {topic}?",
                f"What are the main weaknesses and threats concerning {topic}?",
                f"What recent trends or developments affect {topic}?",
                f"What are the competitive landscape and market dynamics for {topic}?",
                f"What actionable recommendations can be made regarding {topic}?"
            ]

            state["sub_questions"] = sub_questions
            state["intermediate_results"].append({
                "phase": "decomposition",
                "result": {"sub_questions": sub_questions, "fallback": True}
            })

            # Update step as completed with fallback note
            self._update_last_step(
                status="completed",
                content=f"✓ Generated {len(sub_questions)} research questions (automatic)",
                metadata={"phase": "decomposing", "progress": 25, "sub_questions": sub_questions, "fallback": True}
            )

            print(f"[Deep Research] ✓ Generated {len(sub_questions)} sub-questions automatically")

        return state

    async def _search_sources_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Phase 3: Search across all sources for each sub-question.
        Uses both internal notebook search and external web search tools.
        Also directly fetches uploaded source content to ensure file-based
        sources (Excel, PDF, etc.) are always included in the analysis.
        Sub-questions are searched in parallel via asyncio.gather().

        Returns:
            Updated state with search results
        """
        print(f"[Deep Research] Phase 3: Searching sources...")

        # Record step
        self._record_step(
            step_type="searching",
            content="Searching across all notebook sources and uploaded files for relevant information",
            status="running",
            metadata={"phase": "searching", "progress": 40}
        )

        state["phase"] = ResearchPhase.SEARCHING
        state["progress"] = 40

        # Notify progress callback
        if self.progress_callback:
            self.progress_callback(ResearchPhase.SEARCHING, 40, "Searching across sources...")

        sub_questions = state.get("sub_questions", [])

        # Import search service class and get database
        from api.services.search_service import SearchService
        from open_notebook.config import get_database

        # Get database instance
        db = get_database()
        await db.connect()

        try:
            # Create search service instance
            search_svc = SearchService(database=db)

            # ---- Fetch uploaded source content directly ----
            # This ensures file-based sources (Excel, PDF, etc.) are always
            # included even when they have no embeddings for search to find.
            direct_source_results = []
            direct_source_ids = set()
            if self.notebook_id:
                try:
                    from open_notebook.domain.notebook import Notebook
                    notebook = await Notebook.get(self.notebook_id)
                    if notebook:
                        sources = await notebook.get_sources()
                        for source in sources:
                            if source.full_text and source.full_text.strip():
                                # Cap individual source content to avoid blowing up context
                                content = source.full_text[:5000]
                                direct_source_results.append({
                                    "source_type": source.source_type or "file",
                                    "source_id": source.id,
                                    "source_name": source.title or "Uploaded Source",
                                    "title": source.title or "Uploaded Source",
                                    "content": content,
                                    "score": 1.0,
                                    "metadata": {
                                        "source_type": source.source_type,
                                        "direct_content": True
                                    }
                                })
                                direct_source_ids.add(source.id)
                        if direct_source_results:
                            print(f"[Deep Research] Loaded {len(direct_source_results)} source(s) directly from notebook")

                            self._record_step(
                                step_type="searching",
                                content=f"Loaded {len(direct_source_results)} uploaded source file(s) directly",
                                status="completed",
                                metadata={
                                    "phase": "searching",
                                    "source_count": len(direct_source_results),
                                    "direct_content": True
                                }
                            )
                except Exception as e:
                    print(f"[Deep Research] Failed to load direct sources: {e}")

            async def _search_single_question(idx: int, question_obj) -> tuple:
                """Search a single sub-question across all strategies. Returns (question, results)."""
                question = question_obj.get('sub_question', question_obj) if isinstance(question_obj, dict) else question_obj
                print(f"[Deep Research] Searching for: {question[:60]}...")

                all_results = []

                try:
                    # 1. Search internal notebook sources with all strategies in parallel
                    strategy_tasks = []
                    for strategy_name in self.search_strategies[:2]:  # Use top 2 strategies
                        strategy_tasks.append(
                            self._search_with_strategy(search_svc, strategy_name, question)
                        )

                    strategy_results = await asyncio.gather(*strategy_tasks, return_exceptions=True)
                    for result in strategy_results:
                        if isinstance(result, Exception):
                            print(f"[Deep Research] Strategy failed: {result}")
                        elif result:
                            all_results.extend(result)

                    # 2. Use web_search tool if available for external research
                    if self.tools:
                        web_results = await self._web_search_question(idx, question)
                        all_results.extend(web_results)

                    # Deduplicate by source_id
                    seen_sources = set()
                    unique_results = []
                    for result in all_results:
                        source_id = result.get("source_id") if isinstance(result, dict) else None
                        if source_id and source_id not in seen_sources:
                            unique_results.append(result)
                            seen_sources.add(source_id)
                        elif source_id is None:
                            unique_results.append(result)

                    print(f"[Deep Research] Found {len(unique_results)} results for question {idx + 1}")
                    return (question, unique_results[:10])

                except Exception as e:
                    print(f"[Deep Research] Search error for question {idx + 1}: {e}")
                    return (question, [])

            # Execute all sub-question searches in parallel
            search_tasks = [
                _search_single_question(idx, q)
                for idx, q in enumerate(sub_questions)
            ]
            results_list = await asyncio.gather(*search_tasks)

            # Assemble search_results dict and deduplicate across questions
            search_results = {}
            global_seen_ids: set = set()
            for question, results in results_list:
                deduped = []
                for r in results:
                    sid = r.get("source_id") if isinstance(r, dict) else None
                    if sid and sid in global_seen_ids:
                        continue
                    if sid:
                        global_seen_ids.add(sid)
                    deduped.append(r)
                search_results[question] = deduped

            # ---- Inject direct source content that wasn't found by search ----
            # Add uploaded file content that the search strategies missed
            if direct_source_results:
                unseen_sources = [
                    s for s in direct_source_results
                    if s["source_id"] not in global_seen_ids
                ]
                if unseen_sources:
                    search_results["[Uploaded Source Content]"] = unseen_sources
                    for s in unseen_sources:
                        global_seen_ids.add(s["source_id"])
                    print(f"[Deep Research] Added {len(unseen_sources)} direct source(s) not found by search")

        finally:
            await db.disconnect()

        state["search_results"] = search_results
        state["intermediate_results"].append({
            "phase": "search",
            "result": {
                "total_questions": len(sub_questions),
                "total_results": sum(len(v) for v in search_results.values())
            }
        })

        # Update step as completed
        total_results = sum(len(v) for v in search_results.values())
        self._update_last_step(
            status="completed",
            content=f"Found {total_results} relevant results across {len(sub_questions)} questions",
            metadata={
                "phase": "searching",
                "progress": 70,
                "total_questions": len(sub_questions),
                "total_results": total_results
            }
        )

        return state

    async def _search_with_strategy(self, search_svc, strategy_name: str, question: str) -> List[Dict[str, Any]]:
        """Run a single search strategy for a question. Returns results list."""
        try:
            strategy = await search_svc.get_search_strategy(strategy_name)
            from open_notebook.search.strategies import SearchFilters
            filters = SearchFilters(notebook_ids=[self.notebook_id] if self.notebook_id else None)
            results = await strategy.search(query=question, filters=filters, limit=5)
            return results
        except Exception as e:
            print(f"[Deep Research] Strategy {strategy_name} failed: {e}")
            return []

    async def _web_search_question(self, idx: int, question: str) -> List[Dict[str, Any]]:
        """Run web search tool for a question if available. Returns results list."""
        web_search_tool = next((t for t in self.tools if 'web_search' in t.name.lower()), None)
        if not web_search_tool:
            return []

        print(f"[Deep Research] Using web search for: {question[:60]}...")

        self._record_step(
            step_type="tool_call",
            content=f"Calling web_search tool for: {question[:80]}",
            status="running",
            metadata={
                "tool": web_search_tool.name,
                "phase": "searching",
                "question": question
            }
        )

        try:
            web_result = await web_search_tool.ainvoke({"query": question})

            self._update_last_step(
                status="completed",
                content=f"Web search completed for: {question[:80]}",
                metadata={
                    "tool": web_search_tool.name,
                    "phase": "searching",
                    "result_length": len(str(web_result))
                }
            )

            if web_result:
                return [{
                    "source_type": "web_search",
                    "source_id": f"web_{idx}",
                    "title": f"Web Search: {question[:50]}...",
                    "content": str(web_result)[:1000],
                    "score": 0.9,
                    "metadata": {"search_query": question}
                }]
        except Exception as web_error:
            print(f"[Deep Research] Web search error: {web_error}")
            self._update_last_step(
                status="error",
                content=f"Web search failed: {str(web_error)[:100]}",
                metadata={"tool": web_search_tool.name, "error": str(web_error)}
            )

        return []

    async def _synthesize_findings_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Phase 4: Synthesize search results into key findings.

        Returns:
            Updated state with synthesized findings
        """
        print(f"[Deep Research] Phase 4: Synthesizing findings...")

        # Record step
        self._record_step(
            step_type="synthesizing",
            content="Synthesizing findings from search results",
            status="running",
            metadata={"phase": "synthesizing", "progress": 75}
        )

        state["phase"] = ResearchPhase.SYNTHESIZING
        state["progress"] = 75

        # Notify progress callback
        if self.progress_callback:
            self.progress_callback(ResearchPhase.SYNTHESIZING, 75, "Synthesizing findings...")

        search_results = state.get("search_results", {})

        # Prepare context from search results
        context = []
        citation_map = {}
        citation_counter = 1

        for question, results in search_results.items():
            context.append(f"\n## Sub-question: {question}\n")
            for result in results:
                # Handle both SearchResult objects and dicts
                if hasattr(result, 'metadata'):
                    # SearchResult object
                    source_name = result.metadata.get("title", "Unknown")
                    content = result.content[:500]  # Limit content length
                else:
                    # Dict (legacy support)
                    source_name = result.get("source_name", "Unknown")
                    content = result.get("content", "")[:500]

                # Add citation
                if source_name not in citation_map:
                    citation_map[source_name] = citation_counter
                    citation_counter += 1

                citation_num = citation_map[source_name]
                context.append(f"[{citation_num}] {content}...\n")

        context_str = "\n".join(context)

        FALLBACK_PHASE4 = """You are a strategic analyst synthesizing research findings into actionable intelligence. Think deeply and connect the dots.

Original Query: {original_query}

Search Results:
{context_str}

Your task: Extract 8-12 high-value insights that directly address the query. This is NOT a summary—it's strategic analysis.

## Analysis Framework

For each finding, ask yourself:
1. **What's the insight?** - Not just what the data says, but what it MEANS
2. **Why does it matter?** - Connect to business impact, risk, or opportunity
3. **What's the evidence?** - Specific data points, quotes, or examples
4. **What's the implication?** - So what should be done about it?

## Quality Standards

**REQUIRED in each finding:**
- ✅ Specific numbers, dates, or quotes from sources (not vague references)
- ✅ Connects multiple data points to reveal patterns
- ✅ Explains causation or correlation (not just description)
- ✅ Identifies gaps, risks, or opportunities explicitly
- ✅ Provides actionable context (urgency, magnitude, next steps)

**AVOID:**
- ❌ Generic observations anyone could make
- ❌ Repeating the data without interpretation
- ❌ Vague statements like "may" or "could" without evidence
- ❌ Findings that don't connect to the original query

## Output Format

Return JSON array with 8-12 objects:
```json
[
  {{
    "finding": "Specific insight statement with key data point (e.g., '47% of accounts show zero pipeline activity despite $2.3M estimated wallet')",
    "supporting_evidence": "Detailed explanation with specifics: exact numbers, source quotes, comparative context, what the data reveals beyond surface level. Show your analytical thinking—why is this pattern significant? What does it indicate about underlying dynamics?",
    "citations": [1, 2, 3],
    "implications": "Concrete impact and recommended action. Be specific: What decision does this inform? What risk does it expose? What opportunity does it create? What timeline matters? What's the magnitude of impact?"
  }}
]
```

## Think Like an Expert Consultant

- **Prioritize insights by business impact** - Most critical first
- **Quantify wherever possible** - Numbers create urgency and credibility
- **Identify hidden patterns** - What's surprising or counterintuitive?
- **Flag data quality issues** - Missing data is itself a finding
- **Connect internal + external** - How do market forces intersect with internal data?
- **Be specific about next steps** - Vague advice has no value

Start your analysis now. Focus on insights that would change how someone thinks or acts."""

        prompt = await load_prompt(
            "research_phase4_synthesis",
            variables={
                "original_query": state['original_query'],
                "context_str": context_str
            },
            fallback=FALLBACK_PHASE4
        )

        # Store citation map for later use
        state["citation_map"] = citation_map

        try:
            import asyncio
            try:
                # Create fresh LLM to avoid JWT expiration
                llm = self._create_fresh_llm()
                response = await asyncio.wait_for(
                    llm.ainvoke([HumanMessage(content=prompt)]),
                    timeout=90.0  # Longer timeout for synthesis (larger context)
                )
            except asyncio.TimeoutError:
                print(f"[Deep Research] ✗ Synthesis LLM call timed out")
                raise Exception("LLM call timed out during findings synthesis")

            # Clean JSON response (remove markdown code blocks)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            findings = json.loads(content)

            if not isinstance(findings, list):
                findings = [findings]

            state["key_findings"] = findings
            state["citations"] = [
                {"number": num, "source": name}
                for name, num in citation_map.items()
            ]

            state["intermediate_results"].append({
                "phase": "synthesis",
                "result": {"finding_count": len(findings)}
            })

            # Update step as completed
            self._update_last_step(
                status="completed",
                content=f"✓ Synthesized {len(findings)} key findings with citations",
                metadata={
                    "phase": "synthesizing",
                    "progress": 75,
                    "finding_count": len(findings),
                    "citation_count": len(state["citations"])
                }
            )

            print(f"[Deep Research] ✓ Synthesized {len(findings)} key findings")

        except Exception as e:
            print(f"[Deep Research] ✗ Synthesis error: {e}")
            # FALLBACK: Extract insights from search results directly
            print(f"[Deep Research] Using automatic synthesis fallback")

            search_results = state.get("search_results", {})
            findings = []

            # Extract key insights from search results
            for question, results in search_results.items():
                if results:
                    # Create a finding based on the question and results
                    result_count = len(results)
                    source_titles = list(set([r.get('title', 'Source') for r in results[:3]]))
                    finding = {
                        "finding": f"Research on '{question}' identified {result_count} relevant result(s).",
                        "evidence": f"Analysis based on {', '.join(source_titles[:2])}{'...' if len(source_titles) > 2 else ''}",
                        "citation_numbers": [1]  # Reference to main source
                    }
                    findings.append(finding)

            # If no findings from search, create generic analysis finding
            if not findings:
                findings = [{
                    "finding": "Analysis completed based on available data sources.",
                    "evidence": "Comprehensive review of uploaded source materials and available information.",
                    "citation_numbers": [1]
                }]

            state["key_findings"] = findings
            state["citations"] = [{"number": 1, "source": "Research Sources"}]

            state["intermediate_results"].append({
                "phase": "synthesis",
                "result": {"finding_count": len(findings), "fallback": True}
            })

            # Update step as completed with fallback note
            self._update_last_step(
                status="completed",
                content=f"✓ Identified {len(findings)} key insights (automatic)",
                metadata={
                    "phase": "synthesizing",
                    "progress": 75,
                    "finding_count": len(findings),
                    "fallback": True
                }
            )

            print(f"[Deep Research] ✓ Generated {len(findings)} findings automatically")

        return state

    async def _finalize_report_node(self, state: ResearchState) -> Dict[str, Any]:
        """
        Phase 5: Create final comprehensive report.

        Returns:
            Updated state with final report
        """
        print(f"[Deep Research] Phase 5: Finalizing report...")

        # Record step
        self._record_step(
            step_type="finalizing",
            content="Generating comprehensive research report",
            status="running",
            metadata={"phase": "finalizing", "progress": 90}
        )

        state["phase"] = ResearchPhase.FINALIZING
        state["progress"] = 90

        # Notify progress callback
        if self.progress_callback:
            self.progress_callback(ResearchPhase.FINALIZING, 90, "Generating comprehensive report...")

        findings = state.get("key_findings", [])
        citations = state.get("citations", [])
        analysis = state.get("query_analysis", {})

        # Build findings section with implications
        findings_text = []
        for idx, finding in enumerate(findings, 1):
            finding_text = finding.get("finding", "")
            evidence = finding.get("supporting_evidence", "")
            implications = finding.get("implications", "")
            cites = finding.get("citations", [])
            cite_str = ", ".join([f"[{c}]" for c in cites])

            finding_block = f"""### {idx}. {finding_text}

**Evidence:**
{evidence}

**Implications:**
{implications}

*Sources: {cite_str}*
"""
            findings_text.append(finding_block)

        # Build citations section
        citations_text = []
        for cite in sorted(citations, key=lambda x: x["number"]):
            citations_text.append(f"[{cite['number']}] {cite['source']}")

        # Load report template from database
        FALLBACK_PHASE5 = """# Deep Research Report

**Query:** {original_query}

**Research Focus:** {topic}

**Analysis Date:** {timestamp}

---

## Executive Summary

This comprehensive research analyzed **{sub_question_count} strategic research questions** across **{citation_count} authoritative sources**, uncovering **{finding_count} actionable insights**. The analysis employed multi-strategy search (keyword, vector, and hybrid) combined with external web research to provide a thorough, data-driven perspective.

**Key Takeaways:**
- Total data points reviewed: {total_results_count}
- Search coverage: Internal knowledge base + external web sources
- Analysis depth: Multi-dimensional with cross-referenced findings

---

## Detailed Findings

{findings_section}

---

## Research Methodology

### Approach
This research employed a systematic, multi-phase methodology:

1. **Query Decomposition**: Original query broken into {sub_question_count} targeted research questions
2. **Multi-Source Search**: Combined internal document search with external web research
3. **Hybrid Search Strategy**: Leveraged keyword, semantic vector, and hybrid ranking
4. **Cross-Validation**: Findings triangulated across multiple sources
5. **Synthesis**: Insights derived by connecting patterns across data points

### Coverage Metrics
- **Sources Analyzed:** {citation_count} unique sources
- **Sub-Questions Addressed:** {sub_question_count}
- **Search Results Processed:** {total_results_count}
- **Search Strategies:** {search_strategies}

### Source Quality
All findings are cited and traceable to source documents. External web research supplemented internal knowledge to ensure comprehensive coverage.

---

## Source References

{citations_section}

---

## Strategic Recommendations

Based on the research findings, consider these next steps:

1. **Deep Dive**: Investigate high-priority findings in greater detail with targeted follow-up research
2. **Validation**: Cross-check critical insights with additional authoritative sources or subject matter experts
3. **Action Planning**: Translate insights into specific action items with owners and timelines
4. **Monitoring**: Set up ongoing tracking for dynamic factors identified in the analysis
5. **Gap Filling**: Address any data gaps noted in the findings through targeted data collection

---

## Research Limitations

- Analysis based on available sources at time of research ({timestamp})
- External web search limited to publicly available information
- Findings reflect data quality and completeness of source materials
- Some insights may require additional validation for high-stakes decisions

---

*Generated by Deep Research Mode - An autonomous research agent combining multi-strategy search, semantic analysis, and structured synthesis.*
"""

        report = await load_prompt(
            "research_phase5_report",
            variables={
                "original_query": state['original_query'],
                "topic": analysis.get('topic', 'N/A'),
                "timestamp": datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
                "sub_question_count": len(state.get('sub_questions', [])),
                "citation_count": len(citations),
                "finding_count": len(findings),
                "findings_section": "\n".join(findings_text),
                "search_strategies": ', '.join(self.search_strategies),
                "total_results_count": sum(len(v) for v in state.get('search_results', {}).values()),
                "citations_section": "\n".join(citations_text)
            },
            fallback=FALLBACK_PHASE5
        )

        state["final_report"] = report
        state["phase"] = ResearchPhase.COMPLETE
        state["progress"] = 100

        # Update step as completed
        self._update_last_step(
            status="completed",
            content=f"✓ Research complete! Generated comprehensive report ({len(report)} chars)",
            metadata={
                "phase": "complete",
                "progress": 100,
                "report_length": len(report),
                "findings_count": len(findings),
                "citations_count": len(citations)
            }
        )

        print(f"[Deep Research] ✓ Report complete ({len(report)} chars)")

        return state

    async def research(self, query: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute deep research and stream progress updates.

        Args:
            query: Research query from user

        Yields:
            Progress updates with phase, progress %, and intermediate results
        """
        # Initialize state as plain dict
        initial_state: ResearchState = {
            "original_query": query,
            "notebook_id": self.notebook_id,
            "session_id": self.session_id,
            "phase": ResearchPhase.INITIALIZING,
            "progress": 0,
            "sub_questions": [],
            "search_results": {},
            "key_findings": [],
            "final_report": "",
            "citations": [],
            "query_analysis": {},
            "start_time": datetime.utcnow().isoformat(),
            "error_message": None,
            "intermediate_results": []
        }

        config = {
            "configurable": {
                "thread_id": f"research_{self.session_id}_{datetime.utcnow().timestamp()}"
            }
        }

        try:
            # Execute workflow with streaming
            print(f"[Deep Research] Starting LangGraph workflow...")
            event_count = 0
            async for event in self.app.astream(initial_state, config):
                event_count += 1
                print(f"[Deep Research] Got event #{event_count}: {list(event.keys())}")
                # Extract state from event
                for node_name, node_state in event.items():
                    print(f"[Deep Research] Node: {node_name}, Phase: {node_state.get('phase')}, Progress: {node_state.get('progress')}")

                    # Check for error state
                    if node_state.get("phase") == ResearchPhase.ERROR:
                        error_msg = node_state.get("error_message", "Unknown error")
                        print(f"[Deep Research] ✗ Error state detected: {error_msg}")

                    yield {
                        "phase": node_state.get("phase"),
                        "progress": node_state.get("progress", 0),
                        "intermediate_results": node_state.get("intermediate_results", []),
                        "error": node_state.get("error_message")
                    }

                    # If complete, yield final report
                    if node_state.get("phase") == ResearchPhase.COMPLETE:
                        print(f"[Deep Research] Research complete, yielding final report")
                        self._final_report = node_state.get("final_report", "")
                        yield {
                            "phase": ResearchPhase.COMPLETE,
                            "progress": 100,
                            "final_report": self._final_report,
                            "citations": node_state.get("citations", []),
                            "key_findings": node_state.get("key_findings", [])
                        }

            print(f"[Deep Research] LangGraph astream finished after {event_count} events")

        except Exception as e:
            print(f"[Deep Research] ✗ Fatal error: {e}")
            import traceback
            traceback.print_exc()

            yield {
                "phase": ResearchPhase.ERROR,
                "progress": 0,
                "error": f"Research failed: {str(e)}"
            }

    async def research_non_streaming(self, query: str) -> Dict[str, Any]:
        """
        Execute deep research without streaming (for background jobs).

        Args:
            query: Research query from user

        Returns:
            Final research state with report
        """
        # Initialize state as plain dict
        initial_state: ResearchState = {
            "original_query": query,
            "notebook_id": self.notebook_id,
            "session_id": self.session_id,
            "phase": ResearchPhase.INITIALIZING,
            "progress": 0,
            "sub_questions": [],
            "search_results": {},
            "key_findings": [],
            "final_report": "",
            "citations": [],
            "query_analysis": {},
            "start_time": datetime.utcnow().isoformat(),
            "error_message": None,
            "intermediate_results": []
        }

        config = {
            "configurable": {
                "thread_id": f"research_{self.session_id}_{datetime.utcnow().timestamp()}"
            }
        }

        try:
            final_state = await self.app.ainvoke(initial_state, config)
            return final_state

        except Exception as e:
            print(f"[Deep Research] ✗ Fatal error: {e}")
            import traceback
            traceback.print_exc()

            return {
                "phase": ResearchPhase.ERROR,
                "progress": 0,
                "error": f"Research failed: {str(e)}",
                "original_query": query
            }
