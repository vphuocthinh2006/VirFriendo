from __future__ import annotations

from fastapi import Depends, FastAPI, Form
from sqlalchemy.ext.asyncio import AsyncSession

from services.core.api.chat import MediaAnalysisResponse, _analyze_web_url, _analyze_youtube
from services.core.database import get_db
from services.core.security import get_current_user_id

app = FastAPI(title="VirFriendo Knowledge Service", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "knowledge"}


@app.post("/chat/analyze-youtube", response_model=MediaAnalysisResponse)
async def analyze_youtube_route(
    url: str = Form(...),
    message: str = Form(""),
    conversation_id: str | None = Form(None),
    agent_id: str | None = Form(None),
    entry_mode: str | None = Form(None),
    persona: str | None = Form(None),
    character_name: str | None = Form(None),
    gender: str | None = Form(None),
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await _analyze_youtube(
        url,
        message,
        conversation_id,
        agent_id,
        entry_mode,
        persona,
        character_name,
        gender,
        current_user_id,
        db,
    )


@app.post("/chat/analyze-web", response_model=MediaAnalysisResponse)
async def analyze_web_route(
    url: str = Form(...),
    message: str = Form(""),
    conversation_id: str | None = Form(None),
    agent_id: str | None = Form(None),
    entry_mode: str | None = Form(None),
    persona: str | None = Form(None),
    character_name: str | None = Form(None),
    gender: str | None = Form(None),
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await _analyze_web_url(
        url,
        message,
        conversation_id,
        agent_id,
        entry_mode,
        persona,
        character_name,
        gender,
        current_user_id,
        db,
    )
