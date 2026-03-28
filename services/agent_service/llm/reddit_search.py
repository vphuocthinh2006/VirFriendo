import os
from typing import Any, Dict, List

import httpx
from loguru import logger


def _enabled() -> bool:
    return (os.environ.get("ENABLE_REDDIT_SEARCH", "true") or "").strip().lower() in ("1", "true", "yes")


def _user_agent() -> str:
    return (os.environ.get("REDDIT_USER_AGENT") or "VirFriendo/1.0 (by /u/anonymous)").strip()


def _debug() -> bool:
    return (os.environ.get("DEBUG_REDDIT_SEARCH", "") or "").strip().lower() in ("1", "true", "yes")


async def reddit_search(query: str, *, max_results: int = 6) -> List[Dict[str, str]]:
    """
    Lightweight Reddit search via public JSON endpoint (read-only).
    Returns: [{title, url, snippet, source, subreddit}]
    """
    if not _enabled():
        return []
    q = (query or "").strip()
    if not q:
        return []

    limit = max(1, min(int(max_results), 12))
    url = "https://www.reddit.com/search.json"
    params = {
        "q": q,
        "sort": "relevance",
        "t": "all",
        "limit": limit,
        "include_over_18": "on",
    }
    headers = {"User-Agent": _user_agent()}
    timeout = httpx.Timeout(12.0, connect=6.0)

    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
            r = await client.get(url, params=params)
            if r.status_code != 200:
                if _debug():
                    logger.info("reddit_search status={} q={!r}", r.status_code, q)
                return []
            data: Any = r.json()
    except Exception as e:
        logger.warning("reddit_search failed q={!r} err={}", q, e)
        return []

    listing = data.get("data") if isinstance(data, dict) else None
    children = listing.get("children") if isinstance(listing, dict) else None
    if not isinstance(children, list):
        return []

    out: List[Dict[str, str]] = []
    seen = set()
    for item in children:
        if not isinstance(item, dict):
            continue
        post = item.get("data")
        if not isinstance(post, dict):
            continue
        subreddit = str(post.get("subreddit") or "").strip()
        title = str(post.get("title") or "").strip()
        permalink = str(post.get("permalink") or "").strip()
        selftext = str(post.get("selftext") or "").strip()
        if not title or not permalink:
            continue
        full_url = f"https://www.reddit.com{permalink}"
        if full_url in seen:
            continue
        seen.add(full_url)
        snippet = selftext if selftext else title
        snippet = snippet[:2000].strip()
        out.append(
            {
                "title": title,
                "url": full_url,
                "snippet": snippet,
                "source": "reddit",
                "subreddit": f"r/{subreddit}" if subreddit else "",
            }
        )
        if len(out) >= limit:
            break

    if _debug():
        logger.info("reddit_search q={!r} -> {} results", q, len(out))
        if out:
            logger.info("reddit_search top: {} ({})", out[0].get("title"), out[0].get("url"))
    return out

