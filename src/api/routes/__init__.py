from src.api.routes.documents import router as documents_router
from src.api.routes.health import router as health_router
from src.api.routes.market import router as market_router
from src.api.routes.research import router as research_router

__all__ = [
    "documents_router",
    "health_router",
    "market_router",
    "research_router",
]
