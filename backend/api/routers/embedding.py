"""
Embedding Router

Handles embedding configuration.
"""

from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/embedding",
    tags=["embedding"],
)


# ============================================================================
# Models
# ============================================================================

class EmbeddingConfig(BaseModel):
    """Embedding configuration"""
    model_id: str = "text-embedding-ada-002"  # Changed from 'model' to 'model_id'
    chunk_size: int = 1500
    chunk_overlap: int = 150
    batch_size: int = 100


# ============================================================================
# In-Memory Storage (TODO: Move to database)
# ============================================================================

_embedding_config = EmbeddingConfig()


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/config", response_model=EmbeddingConfig)
async def get_embedding_config():
    """
    Get current embedding configuration.

    Returns:
        Embedding configuration
    """
    return _embedding_config


@router.put("/config", response_model=EmbeddingConfig)
async def update_embedding_config(config: EmbeddingConfig):
    """
    Update embedding configuration.

    Args:
        config: New embedding configuration

    Returns:
        Updated configuration
    """
    global _embedding_config
    _embedding_config = config
    return _embedding_config


@router.post("/rebuild")
async def rebuild_embeddings(source_ids: Optional[List[str]] = None):
    """
    Trigger re-embedding of sources with new model/configuration.

    Args:
        source_ids: Optional list of source IDs to re-embed. If None, re-embeds all.

    Returns:
        Job status
    """
    # TODO: Implement actual re-embedding job
    count = len(source_ids) if source_ids else "all"

    return {
        "success": True,
        "message": f"Re-embedding job started for {count} sources",
        "job_id": "rebuild-001",  # TODO: Generate actual job ID
        "status": "queued"
    }
