from src.api.routes.auth import router as auth_router
from src.api.routes.conversations import router as conversations_router
from src.api.routes.documents import router as documents_router
from src.api.routes.tickets import router as tickets_router

__all__ = ["auth_router", "conversations_router", "documents_router", "tickets_router"]
