"""
API Routers Module

FastAPI routers for all API endpoints.
"""

from api.routers.search import router as search_router
from api.routers.search_config import router as search_config_router
from api.routers.chat import router as chat_router
from api.routers.source_chat import router as source_chat_router
from api.routers.auth import router as auth_router
from api.routers.models import router as models_router
from api.routers.embedding import router as embedding_router
from api.routers.credentials import router as credentials_router

__all__ = [
    'search_router',
    'search_config_router',
    'chat_router',
    'source_chat_router',
    'auth_router',
    'models_router',
    'embedding_router',
    'credentials_router',
]
