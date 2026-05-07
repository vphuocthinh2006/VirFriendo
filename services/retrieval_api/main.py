from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

from services.agent_service.llm.web_search import tavily_search


class TavilySearchRequest(BaseModel):
    query: str
    max_results: int = 6


app = FastAPI(title="VirFriendo Retrieval Service", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "retrieval"}


@app.post("/tavily-search")
async def tavily_search_endpoint(req: TavilySearchRequest) -> List[Dict[str, str]]:
    return await tavily_search(req.query, max_results=req.max_results)

