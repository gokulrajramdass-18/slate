"""
Embedding Generation Service

Handles background generation of embeddings for sources.
Chunks content and generates embeddings using configured models.
"""

import asyncio
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from open_notebook.domain.notebook import Source
from open_notebook.database.repository import repo_query, repo_execute
import httpx


class EmbeddingService:
    """
    Service for generating and managing source embeddings.

    Features:
    - Background embedding generation
    - Chunking with configurable size/overlap
    - Progress tracking
    - Retry on failure
    """

    def __init__(
        self,
        chunk_size: int = 1500,
        chunk_overlap: int = 150,
        model_id: str = "text-embedding-ada-002"
    ):
        """
        Initialize embedding service.

        Args:
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Overlap between chunks
            model_id: Embedding model to use
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model_id = model_id
        self._active_jobs: Dict[str, Dict[str, Any]] = {}

    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if not text:
            return []

        # Simple character-based chunking (could be improved with tiktoken)
        # Approximate: 1 token ≈ 4 characters
        char_chunk_size = self.chunk_size * 4
        char_overlap = self.chunk_overlap * 4

        chunks = []
        start = 0

        while start < len(text):
            end = start + char_chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)

                if break_point > char_chunk_size * 0.7:  # At least 70% of chunk
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1

            chunks.append(chunk.strip())
            start = end - char_overlap

        return [c for c in chunks if c]  # Remove empty chunks

    async def _generate_embedding(self, text: str, api_url: str, api_key: str, model_name: str = None) -> List[float]:
        """
        Generate embedding for text using LiteLLM proxy or SAP AI Core.

        Args:
            text: Text to embed
            api_url: LiteLLM API URL or "sap-ai-core" for SAP AI Core
            api_key: API key (or deployment_id for SAP AI Core)
            model_name: Model name to use (defaults to self.model_id if not provided)

        Returns:
            Embedding vector
        """
        # Use provided model_name or fall back to instance default
        model = model_name or self.model_id

        # Check if this is SAP AI Core
        if model and model.startswith("sap-ai-core-"):
            try:
                from gen_ai_hub.proxy.langchain import OpenAIEmbeddings
                from gen_ai_hub.proxy import get_proxy_client

                # Extract deployment ID from model name
                deployment_id = model.replace("sap-ai-core-", "")

                # Get proxy client
                proxy_client = get_proxy_client('gen-ai-hub')

                # Create embedding model
                embedding_model = OpenAIEmbeddings(
                    proxy_model_name=deployment_id,
                    proxy_client=proxy_client
                )

                # Generate embedding
                embedding = await embedding_model.aembed_query(text)
                return embedding

            except ImportError:
                raise Exception("gen-ai-hub SDK not installed. Install with: pip install generative-ai-hub-sdk")
            except Exception as e:
                raise Exception(f"SAP AI Core embedding error: {str(e)}")

        # LiteLLM proxy or SAP AI Core API
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Build headers (skip Authorization if no API key)
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = await client.post(
                f"{api_url}/embeddings",
                headers=headers,
                json={
                    "model": model,
                    "input": text
                }
            )

            if response.status_code != 200:
                raise Exception(f"Embedding API error: {response.status_code} - {response.text}")

            result = response.json()
            return result["data"][0]["embedding"]

    async def generate_embeddings_for_source(
        self,
        source_id: str
    ) -> Dict[str, Any]:
        """
        Generate embeddings for a source.

        Args:
            source_id: Source ID

        Returns:
            Dict with status and statistics
        """
        print(f"🔄 Starting embedding generation for source {source_id}")

        # Get embedding model credentials
        try:
            from api.routers.credentials import _credentials_store
            from api.services.settings import get_setting

            # Get the embedding model ID from settings
            embedding_model_id = await get_setting("embedding_model_id", "")

            if not embedding_model_id:
                error_msg = "No embedding model configured. Please configure in Settings → Models."
                print(f"❌ {error_msg}")
                # Note: sync_status and error_message columns don't exist
                return {
                    "success": False,
                    "error": error_msg,
                    "message": error_msg
                }

            credential = _credentials_store.get(embedding_model_id)

            if not credential:
                error_msg = f"Embedding model '{embedding_model_id}' not found in credentials"
                print(f"❌ {error_msg}")
                # Note: sync_status and error_message columns don't exist
                return {
                    "success": False,
                    "error": error_msg,
                    "message": error_msg
                }

            # Check if this is SAP AI Core provider
            provider = credential.get("provider", "")

            if provider == "sap_ai_core":
                # Auto-configure for SAP AI Core
                api_url = "http://slate-sap-ai-core-api:5056"
                api_key = ""  # Not needed for internal service
                # Use text-embedding-3-large as default for SAP AI Core
                model_name = credential.get("deployment_model_name") or credential.get("model_name", "text-embedding-3-large")
                print(f"🔧 Using SAP AI Core: {api_url} with model: {model_name}")
            else:
                # Use configured values for other providers
                api_url = credential["base_url"]
                api_key = credential["api_key"]
                # Get model name from credential, fallback to default
                model_name = credential.get("deployment_model_name") or credential.get("model_name", credential.get("name", "text-embedding-ada-002"))

        except Exception as e:
            error_msg = f"Failed to get embedding credentials: {str(e)}"
            print(f"❌ {error_msg}")
            # Note: sync_status and error_message columns don't exist
            return {
                "success": False,
                "error": error_msg,
                "message": error_msg
            }

        try:
            # Get source
            source = await Source.get(source_id)
            if not source:
                raise ValueError(f"Source not found: {source_id}")

            # Get content
            content = source.full_text or ""
            if not content:
                print(f"⚠️ No content to embed for source {source_id}")
                # Note: sync_status and error_message columns don't exist
                return {
                    "success": True,
                    "chunks_created": 0,
                    "message": "No content to embed"
                }

            print(f"📝 Chunking {len(content)} characters")

            # Chunk content
            chunks = self._chunk_text(content)
            print(f"✂️ Created {len(chunks)} chunks")

            # Delete existing embeddings
            await repo_execute(
                "DELETE FROM source_embeddings WHERE source_id = :source_id",
                {"source_id": source_id}
            )

            # Generate embeddings for each chunk
            for idx, chunk in enumerate(chunks):
                print(f"🔢 Generating embedding {idx + 1}/{len(chunks)}")

                try:
                    embedding = await self._generate_embedding(chunk, api_url, api_key, model_name)

                    # Store embedding as JSON string
                    import json
                    embedding_str = json.dumps(embedding)

                    # Insert into database
                    await repo_execute(
                        """
                        INSERT INTO source_embeddings (id, source_id, order_num, content, embedding, created)
                        VALUES (:id, :source_id, :order_num, :content, :embedding, :created)
                        """,
                        {
                            "id": str(uuid.uuid4()),
                            "source_id": source_id,
                            "order_num": idx,
                            "content": chunk,
                            "embedding": embedding_str,
                            "created": datetime.utcnow().isoformat()
                        }
                    )
                except Exception as e:
                    print(f"❌ Error generating embedding for chunk {idx}: {e}")
                    # Continue with other chunks
                    continue

            # Update source timestamp
            # Note: sync_status, chunk_count, last_synced, error_message columns don't exist
            # Chunk count is computed via JOIN query when needed
            await repo_execute(
                "UPDATE sources SET updated = :updated WHERE id = :id",
                {
                    "updated": datetime.utcnow().isoformat(),
                    "id": source_id
                }
            )

            print(f"✅ Successfully generated {len(chunks)} embeddings for source {source_id}")

            # Compute semantic similarities for graph visualization
            try:
                from api.services import graph_service
                print(f"🔗 Computing semantic similarities for source {source_id}")
                await graph_service.compute_source_similarities(source_id)
                print(f"✅ Computed similarities for source {source_id}")
            except Exception as sim_error:
                # Log error but don't fail embedding generation
                print(f"⚠️  Failed to compute similarities for {source_id}: {sim_error}")

            return {
                "success": True,
                "chunks_created": len(chunks),
                "message": f"Generated {len(chunks)} embeddings"
            }

        except Exception as e:
            print(f"❌ Error generating embeddings for source {source_id}: {e}")

            # Note: sync_status and error_message columns don't exist
            # Errors are logged but not persisted to database
            # Consider adding error tracking to sync_history table if needed

            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to generate embeddings: {str(e)}"
            }

    async def start_background_job(self, source_id: str) -> str:
        """
        Start background embedding generation job.

        Args:
            source_id: Source ID

        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())

        self._active_jobs[job_id] = {
            "source_id": source_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        }

        # Start background task
        asyncio.create_task(self._run_background_job(job_id, source_id))

        return job_id

    async def _run_background_job(self, job_id: str, source_id: str):
        """
        Run embedding generation in background.

        Args:
            job_id: Job ID
            source_id: Source ID
        """
        try:
            print(f"🔧 Background job {job_id} starting for source {source_id}")
            result = await self.generate_embeddings_for_source(source_id)
            print(f"🔧 Background job {job_id} completed: {result}")

            self._active_jobs[job_id] = {
                **self._active_jobs[job_id],
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "result": result
            }
        except Exception as e:
            print(f"❌ Background job {job_id} failed with error: {e}")
            import traceback
            traceback.print_exc()

            self._active_jobs[job_id] = {
                **self._active_jobs[job_id],
                "status": "error",
                "completed_at": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a background job.

        Args:
            job_id: Job ID

        Returns:
            Job status dict or None if not found
        """
        return self._active_jobs.get(job_id)


# Singleton instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    Get or create embedding service instance.

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
