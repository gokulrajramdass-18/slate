"""
Context Service for Chat

Builds context from notebook sources and notes for chat functionality.
Includes token counting and intelligent truncation.
"""

import tiktoken
from typing import List, Dict, Any, Optional
from open_notebook.domain.notebook import Notebook, Source
from open_notebook.database.repository import repo_query


class ContextService:
    """
    Service for building context from notebook content.

    Features:
    - Fetch and format source content
    - Token counting and truncation
    - Prioritize most relevant chunks
    - Support for multiple sources
    """

    def __init__(self, max_tokens: int = 32000, model: str = "gpt-4"):
        """
        Initialize context service.

        Args:
            max_tokens: Maximum tokens for context (default: 4000)
            model: Model name for token counting (default: gpt-4)
        """
        self.max_tokens = max_tokens
        self.model = model
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to cl100k_base for unknown models
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def truncate_text(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens

        Returns:
            Truncated text
        """
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text

        # Truncate and add ellipsis
        truncated_tokens = tokens[:max_tokens]
        truncated_text = self.encoding.decode(truncated_tokens)
        return truncated_text + "..."

    async def build_source_context(
        self,
        source_id: str,
        max_chunks: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build context from a single source.

        Args:
            source_id: Source ID
            max_chunks: Optional maximum number of chunks to include

        Returns:
            Dict with context info: {
                'source_id': str,
                'source_name': str,
                'content': str,
                'tokens': int,
                'chunks_included': int,
                'chunks_total': int
            }
        """
        # Get source
        source = await Source.get(source_id)
        if not source:
            raise ValueError(f"Source not found: {source_id}")

        # Try to get source chunks/embeddings first
        sql = """
            SELECT content, order_num
            FROM source_embeddings
            WHERE source_id = :source_id
            ORDER BY order_num
        """

        if max_chunks:
            sql += f" LIMIT {max_chunks}"

        chunks = await repo_query(sql, {"source_id": source_id})

        # If no chunks exist, fall back to full_text field
        if not chunks:
            print(f"⚠️ No embeddings found for source {source_id}, using full_text as fallback")
            content = source.full_text or ""
            if not content:
                print(f"⚠️ No full_text found for source {source_id}")
                return {
                    "source_id": source_id,
                    "source_name": source.title,
                    "content": "",
                    "tokens": 0,
                    "chunks_included": 0,
                    "chunks_total": 0
                }

            # Truncate to fit token limit
            tokens = self.count_tokens(content)
            if tokens > self.max_tokens:
                content = self.truncate_text(content, self.max_tokens)
                tokens = self.max_tokens

            return {
                "source_id": source_id,
                "source_name": source.title,
                "content": content,
                "tokens": tokens,
                "chunks_included": 1,
                "chunks_total": 1
            }

        # Build context from chunks
        content_parts = []
        total_tokens = 0
        chunks_included = 0

        for chunk in chunks:
            chunk_text = chunk["content"]
            chunk_tokens = self.count_tokens(chunk_text)

            # Check if adding this chunk would exceed limit
            if total_tokens + chunk_tokens > self.max_tokens:
                # Truncate the last chunk if needed
                remaining_tokens = self.max_tokens - total_tokens
                if remaining_tokens > 100:  # Only include if meaningful
                    truncated_chunk = self.truncate_text(chunk_text, remaining_tokens)
                    content_parts.append(truncated_chunk)
                    chunks_included += 1
                break

            content_parts.append(chunk_text)
            total_tokens += chunk_tokens
            chunks_included += 1

        combined_content = "\n\n".join(content_parts)

        return {
            "source_id": source_id,
            "source_name": source.title,
            "content": combined_content,
            "tokens": total_tokens,
            "chunks_included": chunks_included,
            "chunks_total": len(chunks)
        }

    async def build_notebook_context(
        self,
        notebook_id: str,
        selected_source_ids: Optional[List[str]] = None,
        selected_note_ids: Optional[List[str]] = None,
        include_notes: bool = False
    ) -> Dict[str, Any]:
        """
        Build context from notebook sources and optionally notes.

        Args:
            notebook_id: Notebook ID
            selected_source_ids: Optional list of source IDs to include (all if None)
            selected_note_ids: Optional list of note IDs to include (all if None when include_notes=True)
            include_notes: Whether to include notes in context

        Returns:
            Dict with context info: {
                'notebook_id': str,
                'notebook_name': str,
                'content': str,
                'tokens': int,
                'sources': List[Dict],
                'notes_included': int
            }
        """
        print(f"\n[Context Service] build_notebook_context called:")
        print(f"  - notebook_id: {notebook_id}")
        print(f"  - selected_source_ids: {selected_source_ids}")
        print(f"  - selected_note_ids: {selected_note_ids}")
        print(f"  - include_notes: {include_notes}")
        print(f"  - max_tokens: {self.max_tokens}")

        # Get notebook
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise ValueError(f"Notebook not found: {notebook_id}")

        # Get sources
        sources = await notebook.get_sources()
        print(f"  - Total sources in notebook: {len(sources)}")

        # Filter to selected sources if specified
        if selected_source_ids is not None:  # Explicitly check for None (empty list [] means select none)
            sources = [s for s in sources if s.id in selected_source_ids]
            print(f"  - Filtered sources: {len(sources)}")
        # If selected_source_ids is None, use all sources (backward compatibility)

        # If no sources but notes are requested, still build notes-only context
        if not sources and not include_notes:
            print(f"  - No sources and notes not requested, returning empty")
            return {
                "notebook_id": notebook_id,
                "notebook_name": notebook.name,
                "content": "",
                "tokens": 0,
                "sources": [],
                "notes_included": 0
            }

        print(f"  - Proceeding with context building (sources: {len(sources)}, include_notes: {include_notes})")

        # Calculate tokens per source (leave some room for notes)
        tokens_for_notes = 500 if include_notes else 0
        if sources:
            tokens_per_source = (self.max_tokens - tokens_for_notes) // len(sources)
        else:
            # No sources, so all tokens available for notes
            tokens_per_source = 0

        # Build context from each source
        context_parts = []
        source_contexts = []
        total_tokens = 0

        for idx, source in enumerate(sources, 1):
            # Create a temporary context service with per-source limit
            source_service = ContextService(
                max_tokens=tokens_per_source,
                model=self.model
            )

            try:
                source_ctx = await source_service.build_source_context(source.id)

                # Format source content with numbered header for citations
                source_content = f"## [{idx}] Source: {source.title}\n\n{source_ctx['content']}"
                context_parts.append(source_content)
                source_contexts.append(source_ctx)
                total_tokens += source_ctx['tokens']

            except Exception as e:
                print(f"Error building context for source {source.id}: {e}")
                continue

        # Add notes if requested
        notes_included = 0
        if include_notes and total_tokens < self.max_tokens:
            remaining_tokens = self.max_tokens - total_tokens
            notes = await notebook.get_notes()

            # Filter notes if specific note IDs provided
            if selected_note_ids:
                notes = [n for n in notes if n.id in selected_note_ids]
                print(f"[Context Service] Filtered notes to selected: {len(notes)}")

            print(f"[Context Service] Building notes context:")
            print(f"  - Total notes: {len(notes)}")
            print(f"  - Remaining tokens: {remaining_tokens}")
            print(f"  - Note titles: {[n.title for n in notes]}")

            # Prioritize final deliverable note
            final_deliverable = None
            other_notes = []

            for note in notes:
                if "🎯 FINAL DELIVERABLE" in note.title or "FINAL DELIVERABLE" in note.title:
                    final_deliverable = note
                else:
                    other_notes.append(note)

            print(f"  - Final deliverable found: {final_deliverable is not None}")
            if final_deliverable:
                print(f"  - Final deliverable title: {final_deliverable.title}")
                print(f"  - Final deliverable content length: {len(final_deliverable.content)}")

            notes_parts = []
            notes_tokens = 0

            # Add final deliverable first if it exists
            if final_deliverable:
                # Extract clean text content from HTML (remove tags for token counting)
                import re
                clean_content = re.sub(r'<[^>]+>', '', final_deliverable.content)
                note_text = f"**📊 FINAL DELIVERABLE - Comprehensive Analysis:**\n\n{clean_content}"
                print(f"  - Clean content length: {len(clean_content)}")
                note_tokens = self.count_tokens(note_text)

                # Give final deliverable ALL remaining tokens if it's the only selected note
                if selected_note_ids and len(selected_note_ids) == 1 and final_deliverable.id in selected_note_ids:
                    max_final_tokens = remaining_tokens
                    print(f"  - Final deliverable is ONLY selected note, giving all {max_final_tokens} tokens")
                else:
                    # Give final deliverable up to 50% of remaining tokens
                    max_final_tokens = int(remaining_tokens * 0.5)
                    print(f"  - Allocating 50% of tokens ({max_final_tokens}) to final deliverable")

                if note_tokens > max_final_tokens:
                    # Truncate if too long
                    note_text = self.truncate_text(note_text, max_final_tokens)
                    note_tokens = max_final_tokens

                notes_parts.append(note_text)
                notes_tokens += note_tokens
                notes_included += 1

            # Add other notes with remaining space
            for note in other_notes:
                if notes_tokens >= remaining_tokens:
                    break

                import re
                clean_content = re.sub(r'<[^>]+>', '', note.content)
                note_text = f"**Note:** {clean_content}"
                note_tokens = self.count_tokens(note_text)

                if notes_tokens + note_tokens > remaining_tokens:
                    break

                notes_parts.append(note_text)
                notes_tokens += note_tokens
                notes_included += 1

            if notes_parts:
                notes_content = "\n\n## Notes\n\n" + "\n\n".join(notes_parts)
                context_parts.append(notes_content)
                total_tokens += notes_tokens
                print(f"  - Notes added to context: {notes_included}")
                print(f"  - Notes tokens: {notes_tokens}")

        combined_content = "\n\n".join(context_parts)

        print(f"[Context Service] Final context:")
        print(f"  - Total context parts: {len(context_parts)}")
        print(f"  - Total tokens: {total_tokens}")
        print(f"  - Content length: {len(combined_content)}")
        print(f"  - Notes included: {notes_included}")

        return {
            "notebook_id": notebook_id,
            "notebook_name": notebook.name,
            "content": combined_content,
            "tokens": total_tokens,
            "sources": source_contexts,
            "notes_included": notes_included
        }

    async def build_relevant_context(
        self,
        notebook_id: str,
        query: str,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Build context from most relevant chunks based on query.

        Uses vector similarity search to find relevant chunks.

        Args:
            notebook_id: Notebook ID
            query: User query to find relevant chunks
            top_k: Number of top chunks to include

        Returns:
            Dict with context info similar to build_notebook_context
        """
        # Get notebook
        notebook = await Notebook.get(notebook_id)
        if not notebook:
            raise ValueError(f"Notebook not found: {notebook_id}")

        # Get sources
        sources = await notebook.get_sources()
        source_ids = [s.id for s in sources]

        if not source_ids:
            return {
                "notebook_id": notebook_id,
                "notebook_name": notebook.name,
                "content": "",
                "tokens": 0,
                "chunks": []
            }

        # TODO: In a real implementation, we would:
        # 1. Generate embedding for query
        # 2. Search for similar chunks across all sources
        # 3. Rank by relevance
        # For now, we'll return chunks from all sources

        placeholders = ", ".join([f":source_{i}" for i in range(len(source_ids))])
        params = {f"source_{i}": sid for i, sid in enumerate(source_ids)}

        sql = f"""
            SELECT
                se.content,
                se.source_id,
                se.order_num,
                s.title as source_name
            FROM source_embeddings se
            JOIN sources s ON s.id = se.source_id
            WHERE se.source_id IN ({placeholders})
            ORDER BY se.source_id, se.order_num
            LIMIT {top_k}
        """

        chunks = await repo_query(sql, params)

        # Build context from chunks
        context_parts = []
        total_tokens = 0
        chunk_info = []

        for chunk in chunks:
            chunk_text = chunk["content"]
            chunk_tokens = self.count_tokens(chunk_text)

            if total_tokens + chunk_tokens > self.max_tokens:
                remaining_tokens = self.max_tokens - total_tokens
                if remaining_tokens > 100:
                    truncated_chunk = self.truncate_text(chunk_text, remaining_tokens)
                    formatted = f"**From {chunk['source_name']}:**\n{truncated_chunk}"
                    context_parts.append(formatted)
                    chunk_info.append({
                        "source_id": chunk["source_id"],
                        "source_name": chunk["source_name"],
                        "order_num": chunk["order_num"],
                        "truncated": True
                    })
                break

            formatted = f"**From {chunk['source_name']}:**\n{chunk_text}"
            context_parts.append(formatted)
            total_tokens += chunk_tokens
            chunk_info.append({
                "source_id": chunk["source_id"],
                "source_name": chunk["source_name"],
                "order_num": chunk["order_num"],
                "truncated": False
            })

        combined_content = "\n\n---\n\n".join(context_parts)

        return {
            "notebook_id": notebook_id,
            "notebook_name": notebook.name,
            "content": combined_content,
            "tokens": total_tokens,
            "chunks": chunk_info
        }


# Singleton instance
_context_service: Optional[ContextService] = None


def get_context_service(
    max_tokens: int = 4000,
    model: str = "gpt-4"
) -> ContextService:
    """
    Get or create context service instance.

    Args:
        max_tokens: Maximum tokens for context
        model: Model name for token counting

    Returns:
        ContextService instance
    """
    global _context_service
    if _context_service is None:
        _context_service = ContextService(max_tokens=max_tokens, model=model)
    return _context_service


async def get_llm_for_credential(credential_id: str):
    """
    Get LangChain LLM instance for a credential.

    Args:
        credential_id: Credential ID from credential store

    Returns:
        LangChain LLM instance (ChatOpenAI, ChatAnthropic, ChatSAPAICore, etc.)
    """
    from api.routers.credentials import _credentials_store
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic

    credential = _credentials_store.get(credential_id)
    if not credential:
        raise ValueError(f"Credential not found: {credential_id}")

    model_name = credential.get("model_name")
    base_url = credential.get("base_url", "http://localhost:6655/litellm/v1")
    api_key = credential.get("api_key", "42cf7b97-46a1-4613-a082-d5f1d60e1678")
    provider = credential.get("provider", "litellm")

    # SAP AI Core provider - calls standalone API via HTTP
    if provider == "sap_ai_core":
        from open_notebook.llm.chat_sap_ai_core_sdk import ChatSAPAICore

        # Get deployment ID and SDK model name from credential
        deployment_id = credential.get("deployment_id")
        sdk_model_name = credential.get("model_name")  # This is the SDK-compatible name (e.g., "gpt-4o")

        if not deployment_id:
            raise ValueError(
                f"Missing deployment_id for SAP AI Core credential {credential_id}"
            )

        logger.info(f"[SAP AI Core] Using deployment {deployment_id} with SDK model {sdk_model_name}")

        # Create ChatSAPAICore instance - calls standalone API on port 5056
        # Pass SDK model name (e.g., "gpt-4o") not deployment model name (e.g., "gpt-5.4")
        return ChatSAPAICore(
            model_name=sdk_model_name,
            deployment_id=deployment_id,
            temperature=0.7,
            max_tokens=4096,
            api_base_url="http://localhost:5056"
        )

    # LiteLLM provider - always use OpenAI-compatible endpoint
    # regardless of model name (LiteLLM proxies all models)
    elif provider == "litellm":
        return ChatOpenAI(
            model=model_name,
            openai_api_base=base_url,
            openai_api_key=api_key,
            temperature=0.7,
            max_tokens=4096
        )
    # Only use native clients when provider is not litellm
    elif provider == "anthropic" or (provider != "litellm" and "anthropic" in model_name.lower()):
        return ChatAnthropic(
            model=model_name,
            anthropic_api_key=api_key,
            temperature=0.7,
            max_tokens=4096
        )
    elif provider == "openai" or "gpt" in model_name.lower():
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,
            temperature=0.7,
            max_tokens=4096
        )
    else:
        # Fallback: use OpenAI-compatible endpoint
        return ChatOpenAI(
            model=model_name,
            openai_api_base=base_url,
            openai_api_key=api_key,
            temperature=0.7,
            max_tokens=4096
        )
