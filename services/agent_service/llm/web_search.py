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
    # Optional microservice proxy: route Tavily calls through retrieval-service.
    # This helps the system design show clearer service boundaries.
    proxy_enabled = (os.environ.get("RETRIEVAL_PROXY_ENABLED", "false") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    proxy_url = (os.environ.get("RETRIEVAL_SERVICE_URL") or "").strip()
    if proxy_enabled and proxy_url:
        try:
            payload: Dict[str, Any] = {
                "query": (query or "").strip(),
                "max_results": max(1, min(int(max_results), 10)),
            }
            if not payload["query"]:
                return []
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=6.0),
            ) as client:
                r = await client.post(proxy_url.rstrip("/") + "/tavily-search", json=payload)
                if not r.ok:
                    return []
                data = r.json()
                if isinstance(data, list):
                    out: List[Dict[str, str]] = []
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        title = str(item.get("title") or "").strip()
                        url = str(item.get("url") or "").strip()
                        snippet = str(item.get("snippet") or "").strip()
                        if not url:
                            continue
                        out.append({"title": title or url, "url": url, "snippet": snippet})
                    return out
        except Exception as e:
            logger.warning("tavily_search proxy failed err={}", e)
            # fall back to direct Tavily below

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

