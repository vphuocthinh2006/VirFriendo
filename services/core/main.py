# Chạy được dù uvicorn start từ đâu; load .env từ project root (để GROQ_API_KEY có khi gọi LLM)
import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except Exception:
    pass

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from services.core.config import settings
from services.core.api import agents, auth, chat, diary, external_game, game
from services.core.api.caro import router as caro_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create missing tables (additive only; no schema migrations for existing tables)."""
    import services.core.models  # noqa: F401 — register models on Base.metadata
    from services.core.database import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


_docs = settings.DEBUG or (settings.APP_ENV or "").lower() != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

_hosts = settings.trusted_host_list()
if _hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=_hosts)

_cors = settings.cors_origin_list()
if not _cors:
    _cors = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(chat.router)
app.include_router(diary.router)
app.include_router(game.router)
app.include_router(external_game.router)
app.include_router(caro_router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
