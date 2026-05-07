from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from services.core.api import chat as core_chat

app = FastAPI(title="VirFriendo Media Service", version="0.1.0")


def _allowed(route_path: str) -> bool:
    # Core router prefix is /chat, but route_path already includes it.
    return route_path in {"/chat/transcribe", "/chat/analyze-media", "/chat/imagine"}


# Reuse the already-implemented handlers in `services.core.api.chat`
# but run them inside a separate container for microservice diagram clarity.
for r in core_chat.router.routes:
    if isinstance(r, APIRoute) and _allowed(r.path):
        app.router.routes.append(r)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "media"}

