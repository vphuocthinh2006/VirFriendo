import os
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx
from loguru import logger


def _enabled() -> bool:
    return (os.environ.get("ENABLE_COMMUNITY_SEARCH", "true") or "").strip().lower() in ("1", "true", "yes")


def _tavily_key() -> str:
    return (os.environ.get("TAVILY_API_KEY") or "").strip()


def _domains() -> List[str]:
    raw = (os.environ.get("COMMUNITY_INCLUDE_DOMAINS") or "").strip()
    if not raw:
        return ["reddit.com", "fandom.com", "wiki.gg"]
    out: List[str] = []
    for part in raw.split(","):
        d = part.strip().lower()
        if not d:
            continue
        out.append(d)
    return out or ["reddit.com", "fandom.com", "wiki.gg"]


def _debug() -> bool:
    return (os.environ.get("DEBUG_COMMUNITY_SEARCH", "") or "").strip().lower() in ("1", "true", "yes")


def _is_community_url(url: str, allowed_domains: List[str]) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    for d in allowed_domains:
        if host == d or host.endswith("." + d):
            return True
    return False


def _quality_ok(url: str, title: str, snippet: str) -> bool:
    """
    Lightweight quality filter for community results.
    Keep thread/wiki pages; drop profile/login/noise pages.
    """
    low_url = (url or "").lower()
    low_title = (title or "").lower()
    low_snip = (snippet or "").lower()

    bad_markers = [
        "/user/",
        "/users/",
        "/u/",
        "/login",
        "/signup",
        "privacy policy",
        "terms of service",
    ]
    if any(m in low_url for m in bad_markers):
        return False
    if any(m in low_title for m in ["privacy policy", "terms of service"]):
        return False

    # Prefer content-like pages
    content_markers = [
        "/r/",
        "/comments/",
        "/wiki/",
        "fandom.com/wiki/",
        "wiki.gg/wiki/",
        "discussion",
        "thread",
    ]
    if any(m in low_url for m in content_markers):
        return True
    return len(low_snip.strip()) >= 80


def _extract_reddit_meta(url: str) -> Dict[str, str]:
    """Extract subreddit and post-type from a Reddit URL."""
    meta: Dict[str, str] = {}
    try:
        path = urlparse(url).path or ""
    except Exception:
        return meta
    sub_match = re.search(r"/r/([^/]+)", path)
    if sub_match:
        meta["subreddit"] = f"r/{sub_match.group(1)}"
    return meta


_VN_STRIP = re.compile(
    r"\b(cho\s+t[oôớ]i\s+xin|cho\s+m[iì]nh|t[uừ]\s+|c[uủ]a\s+|v[eề]\s+|"
    r"n[oó]i\s+g[iì]\s+v[eề]|t[oó]m\s+t[aắ]t|review\s+t[uừ]|"
    r"t[uừ]\s+c[aá]c\s+redditor[s]?|t[uừ]\s+reddit)\b",
    re.IGNORECASE,
)


def _normalize_community_query(q: str) -> str:
    """Strip Vietnamese filler so Tavily gets a cleaner English query."""
    cleaned = _VN_STRIP.sub(" ", q)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    if len(cleaned) < 3:
        return q.strip()
    return cleaned


async def community_search(query: str, *, max_results: int = 6) -> List[Dict[str, str]]:
    """
    Community-focused retrieval via Tavily with strict domain + quality filtering.
    Sources include Reddit + fan wikis (Fandom/wiki.gg).
    Returns list of sources: [{title, url, snippet, source}]
    """
    if not _enabled():
        return []
    key = _tavily_key()
    if not key:
        return []
    q = (query or "").strip()
    if not q:
        return []

    domains = _domains()
    q_clean = _normalize_community_query(q)
    # Append "review" or "discussion" if user query implies it.
    review_signal = any(w in q.lower() for w in ["review", "đánh giá", "nhận xét", "ý kiến", "opinion"])
    suffix = " review discussion" if review_signal else ""
    site_expr = " OR ".join([f"site:{d}" for d in domains])
    q2 = f"{q_clean}{suffix} ({site_expr})"

    payload: Dict[str, Any] = {
        "api_key": key,
        "query": q2,
        "max_results": max(1, min(int(max_results), 10)),
        "include_answer": False,
        "include_images": False,
        "include_raw_content": True,
        "search_depth": os.environ.get("TAVILY_SEARCH_DEPTH", "advanced"),
    }
    timeout = httpx.Timeout(12.0, connect=6.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post("https://api.tavily.com/search", json=payload)
            if r.status_code != 200:
                if _debug():
                    logger.info("community_search status={} q={!r}", r.status_code, q2)
                return []
            data = r.json()
    except Exception as e:
        logger.warning("community_search pass1 failed q={!r} err={}", q2, e)
        return []

    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []

    out: List[Dict[str, str]] = []
    seen = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        raw = str(item.get("raw_content") or "").strip()
        content = str(item.get("content") or item.get("snippet") or "").strip()
        snippet = (raw[:2000] if raw else content)
        if not url:
            continue
        if url in seen:
            continue
        if not _is_community_url(url, domains):
            continue
        if not _quality_ok(url, title, snippet):
            continue
        seen.add(url)
        entry: Dict[str, str] = {
            "title": title or url,
            "url": url,
            "snippet": snippet,
            "source": "community",
        }
        reddit_meta = _extract_reddit_meta(url)
        if reddit_meta.get("subreddit"):
            entry["subreddit"] = reddit_meta["subreddit"]
        out.append(entry)
        if len(out) >= max_results:
            break
    # Second pass: if strict filter yields nothing, retry a softer query and domain-only filter.
    if not out:
        q3 = f"{q} reddit fandom wiki.gg discussion"
        payload2 = dict(payload)
        payload2["query"] = q3
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r2 = await client.post("https://api.tavily.com/search", json=payload2)
                if r2.status_code == 200:
                    data2 = r2.json()
                    results2 = data2.get("results") if isinstance(data2, dict) else None
                    if isinstance(results2, list):
                        for item in results2:
                            if not isinstance(item, dict):
                                continue
                            title = str(item.get("title") or "").strip()
                            url = str(item.get("url") or "").strip()
                            snippet = str(item.get("content") or item.get("snippet") or "").strip()
                            if not url or url in seen:
                                continue
                            if not _is_community_url(url, domains):
                                continue
                            seen.add(url)
                            entry2: Dict[str, str] = {"title": title or url, "url": url, "snippet": snippet, "source": "community"}
                            rm = _extract_reddit_meta(url)
                            if rm.get("subreddit"):
                                entry2["subreddit"] = rm["subreddit"]
                            out.append(entry2)
                            if len(out) >= max_results:
                                break
        except Exception as e:
            if _debug():
                logger.info("community_search pass2 failed q={!r} err={}", q3, e)

    if _debug():
        logger.info("community_search q={!r} domains={} -> {} results", q, domains, len(out))
        if out:
            logger.info("community_search top: {} ({})", out[0].get("title"), out[0].get("url"))
    return out

