import os
import re
from typing import Any, Dict, List, Optional

import httpx
import html
from loguru import logger


def _enabled() -> bool:
    return (os.environ.get("ENABLE_ANILIST", "true") or "").strip().lower() in ("1", "true", "yes")


def _debug() -> bool:
    return (os.environ.get("DEBUG_ANILIST", "") or "").strip().lower() in ("1", "true", "yes")

def _normalize_query(q: str) -> str:
    t = (q or "").strip()
    t = re.sub(r"^(tóm tắt|tóm tắt lại|review|giải thích|tóm lược)\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(summary|summarize|synopsis|tl;dr)\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\barc\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bpremise\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bno\s*spoil\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"không\s*spoil", "", t, flags=re.IGNORECASE)
    # Strip router artifacts like "summary from AniList", "from wiki", "review discussion"
    t = re.sub(r"\b(from\s+anilist|from\s+wiki\w*|from\s+reddit|from\s+fandom)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(summary|review|discussion|opinion|lore)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _build_candidates(q: str) -> List[str]:
    """
    AniList search nhạy query. Tự tạo biến thể để hit đúng entry theo "season/arc".
    """
    qn = _normalize_query(q)
    q_lower = qn.lower()

    candidates: List[str] = [qn]

    # Detect season/part numbers in various formats
    # e.g. "season 4", "ss4", "s4", "mùa 4", "phần 4"
    m = re.search(r"(?:season|ss|s)\s*(\d+)|(?:mùa|phần)\s*(\d+)", q_lower)
    season_num = m.group(1) or m.group(2) if m else None
    part2 = any(t in q_lower for t in ["part 2", "part ii", "phần 2", "phần hai"])

    # AOT shortcuts
    if any(t in q_lower for t in ["aot", "attack on titan", "shingeki", "titan"]):
        if part2:
            candidates.extend(
                [
                    "Attack on Titan: The Final Season Part 2",
                    "Attack on Titan Final Season Part 2",
                    "Shingeki no Kyojin: The Final Season Part 2",
                    "Shingeki no Kyojin The Final Season Part 2",
                ]
            )

        if season_num:
            candidates.extend([f"Attack on Titan (season {season_num})", f"Attack on Titan season {season_num}"])
            candidates.extend([f"Shingeki no Kyojin (season {season_num})", f"Shingeki no Kyojin season {season_num}"])

        if any(t in q_lower for t in ["final season", "final", "the final season", "ss4", "s4", "season 4", "mùa 4", "phần 4"]):
            # For Season 4 / Final Season (Part 1 or generic final season)
            candidates.extend(
                [
                    "Attack on Titan: The Final Season",
                    "Attack on Titan Final Season",
                    "Shingeki no Kyojin: The Final Season",
                    "Shingeki no Kyojin The Final Season",
                ]
            )

        candidates.extend(["Attack on Titan", "Shingeki no Kyojin"])

    # Generic season variants
    if season_num:
        candidates.extend([f"{qn} (season {season_num})", f"{qn} season {season_num}"])

    # de-dup while preserving order
    seen = set()
    out: List[str] = []
    for c in candidates:
        c2 = (c or "").strip()
        if not c2 or c2 in seen:
            continue
        seen.add(c2)
        out.append(c2)
    return out


def _strip_html(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    # AniList descriptions may contain HTML tags and entities
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"</p\s*>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    # Convert HTML entities (e.g. &rsquo;, &quot;) into proper unicode characters
    t = html.unescape(t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


ANILIST_QUERY = """
query ($search: String, $perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    media(search: $search, sort: [SEARCH_MATCH, POPULARITY_DESC]) {
      id
      type
      format
      title { romaji english native }
      description(asHtml: true)
      siteUrl
      episodes
      chapters
      season
      seasonYear
      status
      startDate { year month day }
      endDate { year month day }
      synonyms
    }
  }
}
"""


async def anilist_search(query: str, *, max_results: int = 3) -> List[Dict[str, str]]:
    """
    AniList-first retriever for anime/manga. No API key required.
    Returns list of sources: [{title, url, snippet, source}]
    """
    if not _enabled():
        return []
    q = (query or "").strip()
    if not q:
        return []
    max_results = max(1, min(int(max_results), 6))
    timeout = httpx.Timeout(18.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "VirFriendo/1.0 (local)"}) as client:
        candidates = _build_candidates(q)
        last_err: str = ""
        for cand in candidates:
            try:
                r = await client.post(
                    "https://graphql.anilist.co",
                    json={"query": ANILIST_QUERY, "variables": {"search": cand, "perPage": max_results}},
                )
            except Exception as e:
                last_err = str(e)
                if _debug():
                    logger.warning("anilist_search request failed cand={!r}: {}", cand, e)
                continue
            if r.status_code != 200:
                last_err = f"status={r.status_code}"
                if _debug():
                    logger.warning("anilist_search status={} cand={!r} body={}", r.status_code, cand, (r.text or "")[:200])
                continue
            try:
                data: Any = r.json()
            except Exception:
                last_err = "invalid_json"
                if _debug():
                    logger.warning("anilist_search invalid json cand={!r}", cand)
                continue

            page = (((data or {}).get("data") or {}).get("Page") or {}) if isinstance(data, dict) else {}
            media = page.get("media")
            if not isinstance(media, list) or len(media) == 0:
                continue

            out: List[Dict[str, str]] = []
            for m in media[:max_results]:
                if not isinstance(m, dict):
                    continue
                title_obj = m.get("title") if isinstance(m.get("title"), dict) else {}
                title = (
                    str(title_obj.get("english") or "").strip()
                    or str(title_obj.get("romaji") or "").strip()
                    or str(title_obj.get("native") or "").strip()
                )
                url = str(m.get("siteUrl") or "").strip()
                desc = _strip_html(str(m.get("description") or ""))
                if not title or not url:
                    continue

                meta_bits: List[str] = []
                typ = str(m.get("type") or "").strip()
                fmt = str(m.get("format") or "").strip()
                if typ:
                    meta_bits.append(typ)
                if fmt:
                    meta_bits.append(fmt)
                sy = m.get("seasonYear")
                if sy:
                    meta_bits.append(str(sy))
                eps = m.get("episodes")
                if eps:
                    meta_bits.append(f"{eps} eps")
                ch = m.get("chapters")
                if ch:
                    meta_bits.append(f"{ch} ch")
                meta = " | ".join(meta_bits)

                snippet = (meta + "\n" if meta else "") + (desc[:1200] if desc else "")
                out.append({"title": title, "url": url, "snippet": snippet.strip(), "source": "anilist"})

            if out:
                if _debug():
                    logger.info("anilist_search hit cand={!r} q={!r} -> {} results", cand, q, len(out))
                    logger.info("anilist_search top: {} ({})", out[0].get("title"), out[0].get("url"))
                return out

        if _debug():
            logger.info("anilist_search no results q={!r} candidates={} last_err={}", q, len(candidates), last_err)
        return []

