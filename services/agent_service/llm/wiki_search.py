import os
import re
from typing import Any, Dict, List

import httpx
from loguru import logger


def _enabled() -> bool:
    return (os.environ.get("ENABLE_WIKI_SEARCH", "true") or "").strip().lower() in ("1", "true", "yes")


def _lang() -> str:
    return (os.environ.get("WIKI_LANG", "vi") or "vi").strip().lower()


def _debug() -> bool:
    return (os.environ.get("DEBUG_WIKI_SEARCH", "") or "").strip().lower() in ("1", "true", "yes")


async def _search_lang(client: httpx.AsyncClient, lang: str, q: str, max_results: int) -> List[Dict[str, str]]:
    """
    Use stable MediaWiki API search, then fetch REST summary for grounding.
    """
    r = await client.get(
        f"https://{lang}.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": q,
            "srlimit": max_results,
            "format": "json",
            "utf8": 1,
        },
    )
    if r.status_code != 200:
        return []
    data: Any = r.json()
    query = data.get("query") if isinstance(data, dict) else None
    search = query.get("search") if isinstance(query, dict) else None
    if not isinstance(search, list):
        return []

    out: List[Dict[str, str]] = []
    for p in search[:max_results]:
        if not isinstance(p, dict):
            continue
        title = str(p.get("title") or "").strip()
        snippet_html = str(p.get("snippet") or "").strip()
        if not title:
            continue
        # Build URL using title (MediaWiki normalizes spaces)
        key = title.replace(" ", "_")
        url = f"https://{lang}.wikipedia.org/wiki/{key}"
        snippet = ""
        try:
            s = await client.get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{key}")
            if s.status_code == 200:
                sd: Any = s.json()
                snippet = str(sd.get("extract") or "").strip()
        except Exception:
            snippet = ""
        if not snippet:
            # Keep raw snippet (HTML-ish) if extract missing
            snippet = snippet_html
        out.append({"title": title, "url": url, "snippet": snippet, "source": "wikipedia", "lang": lang})
    return out


async def wiki_search(query: str, *, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Wikipedia-first retriever.
    Returns list of sources: [{title, url, snippet}]
    """
    if not _enabled():
        return []
    q = (query or "").strip()
    if not q:
        return []

    lang = _lang()
    max_results = max(1, min(int(max_results), 8))
    timeout = httpx.Timeout(10.0, connect=5.0)

    # Heuristics: season/arc queries often need a better title match; build candidates (generic, not AOT-only).
    q = re.sub(r"^(summary|summarize|synopsis|tl;dr)\s+", "", q, flags=re.IGNORECASE)
    # Strip router artifacts
    q = re.sub(r"\b(from\s+anilist|from\s+wiki\w*|from\s+reddit|from\s+fandom)\b", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\b(summary|review|discussion|opinion)\b", "", q, flags=re.IGNORECASE)
    q_norm = re.sub(r"\s+", " ", q).strip()
    q_lower = q_norm.lower()
    wants_season = any(t in q_lower for t in ["season", "ss", "s1", "s2", "s3", "s4", "phần", "mùa", "arc", "part", "cour", "final season"])
    # Remove common summarization qualifiers so retrieval hits titles reliably.
    q = re.sub(r"\bpremise\b", "", q, flags=re.IGNORECASE)
    q = re.sub(r"\bno\s*spoil\b", "", q, flags=re.IGNORECASE)
    q = re.sub(r"không\s*spoil", "", q, flags=re.IGNORECASE)
    # Extract potential season number if present
    m = re.search(r"(?:season|ss|s)\s*(\d+)", q_lower)
    season_num = m.group(1) if m else None
    candidates: List[str] = [q_norm]
    if wants_season:
        base = q_norm
        # remove common Vietnamese filler words
        base2 = re.sub(r"^(tóm tắt|tóm tắt lại|review|giải thích)\s+", "", base, flags=re.IGNORECASE).strip()
        if base2:
            base = base2
        if season_num:
            candidates.extend([f"{base} (season {season_num})", f"{base} season {season_num}"])
        candidates.extend([f"{base} plot", f"{base} summary"])
    # generic: try without Vietnamese filler
    candidates.append(re.sub(r"^(tóm tắt|tóm tắt lại|review|giải thích)\s+", "", q_lower).strip())
    # de-dup while preserving order
    seen = set()
    candidates = [c for c in candidates if c and not (c in seen or seen.add(c))]

    async with httpx.AsyncClient(timeout=timeout, headers={"User-Agent": "VirFriendo/1.0 (local)"}) as client:
        out: List[Dict[str, str]] = []
        # Try multiple candidate queries, lang first then en fallback
        for cand in candidates:
            out = await _search_lang(client, lang, cand, max_results)
            if not out and lang != "en":
                out = await _search_lang(client, "en", cand, max_results)
            if out:
                if _debug():
                    logger.info("wiki_search hit cand={!r} -> {} results", cand, len(out))
                break
        if _debug():
            logger.info("wiki_search lang={} q={!r} candidates={} -> {} results", lang, q_norm, len(candidates), len(out))
            if out:
                logger.info("wiki_search top: {} ({})", out[0].get("title"), out[0].get("url"))
        # Filter out empty snippets to avoid weak grounding
        out = [s for s in out if (s.get("snippet") or "").strip()]
        return out

