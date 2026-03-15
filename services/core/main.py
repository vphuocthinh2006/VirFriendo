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

from fastapi import FastAPI
from services.core.config import settings
from services.core.api import auth, chat

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)

app.include_router(auth.router)
app.include_router(chat.router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION
    }
