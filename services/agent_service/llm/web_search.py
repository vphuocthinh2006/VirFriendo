import os
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger


def _enabled() -> bool:
    return (os.environ.get("ENABLE_WEB_SEARCH", "true") or "").strip().lower() in ("1", "true", "yes")


def _tavily_key() -> str:
    return (os.environ.get("TAVILY_API_KEY") or "").strip()


async def tavily_search(query: str, *, max_results: int = 6) -> List[Dict[str, str]]:
    """
    Returns list of sources: [{title, url, snippet}]
    Empty list if disabled / no key / failed.
    """
    if not _enabled():
        return []
    key = _tavily_key()
    if not key:
        return []
    q = (query or "").strip()
    if not q:
        return []

    payload: Dict[str, Any] = {
        "api_key": key,
        "query": q,
        "max_results": max(1, min(int(max_results), 10)),
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
        "search_depth": os.environ.get("TAVILY_SEARCH_DEPTH", "basic"),
    }
    timeout = httpx.Timeout(12.0, connect=6.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post("https://api.tavily.com/search", json=payload)
            if r.status_code != 200:
                return []
            data = r.json()
    except Exception as e:
        logger.warning("tavily_search failed q={!r} err={}", q, e)
        return []
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []
    out: List[Dict[str, str]] = []
    for item in results[: payload["max_results"]]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("content") or item.get("snippet") or "").strip()
        if not url:
            continue
        out.append({"title": title or url, "url": url, "snippet": snippet})
    return out

