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


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
