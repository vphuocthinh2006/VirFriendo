"""
VirFriendo Retrieval Service (port 8031).

Currently exposes ONLY ``POST /tavily-search`` — a thin HTTP proxy over
``agent_service.llm.web_search.tavily_search``. Other retrievers in
``agent_service/llm/`` (anilist, reddit_search, community_search,
fanwiki_search, wiki_search, retriever_router, retrieval_auditor,
knowledge_judge) are called IN-PROCESS by the agent service, not via this
HTTP boundary. The system-design diagram should reflect this: only Tavily
crosses the network here.
"""
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

