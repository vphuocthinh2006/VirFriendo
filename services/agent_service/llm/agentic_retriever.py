import asyncio
import json
import os
import re
import time
from typing import Any, Dict, List, Tuple

from loguru import logger

from services.agent_service.llm.client import generate
from services.agent_service.llm.anilist import anilist_search
from services.agent_service.llm.wiki_search import wiki_search
from services.agent_service.llm.fanwiki_search import fanwiki_search
from services.agent_service.llm.reddit_search import reddit_search
from services.agent_service.llm.community_search import community_search
from services.agent_service.llm.web_search import tavily_search


TOOL_REGISTRY = {
    "anilist": lambda q: anilist_search(q, max_results=4),
    "wiki": lambda q: wiki_search(q, max_results=4),
    "fanwiki": lambda q: fanwiki_search(q, max_results=4),
    "reddit": lambda q: reddit_search(q, max_results=6),
    "community": lambda q: community_search(q, max_results=6),
    "tavily": lambda q: tavily_search(q, max_results=6),
}

FACTUAL_SOURCES = {"anilist", "wiki", "fanwiki", "tavily"}
CONTEXT_SOURCES = {"reddit", "community"}
AUTHORITATIVE_FACTUAL_SOURCES = {"anilist", "wiki", "tavily"}

_STOPWORDS = {
    "cho", "mình", "xin", "chi", "tiết", "về", "nhân", "vật", "từ", "của", "toi", "minh",
    "please", "detail", "details", "about", "the", "a", "an", "in", "on", "for", "and", "or",
    "character", "story", "plot", "lore", "game", "phim", "anime", "manga",
    "cốt", "truyện", "bao", "quanh", "vấn", "đề", "gì",
    "nếu", "xét", "với", "thì", "ai", "hơn", "so", "sánh", "đánh", "đấu", "hay",
    "who", "wins", "stronger", "better", "versus", "vs",
}
_GENERIC_QUERY_TERMS = {
    "baldur", "gate", "baldur's", "details", "detail", "character", "nhân", "vật",
    "game", "story", "plot", "lore", "info", "information",
}
_ENTITY_FRANCHISE_HINTS = {
    # Chỉ nhân vật gắn chặt BG3 — KHÔNG thêm "raphael" (dễ nhầm Honkai / nhạc).
    "zariel": "Baldur's Gate 3",
    "cazador": "Baldur's Gate 3",
    "astarion": "Baldur's Gate 3",
    "dark urge": "Baldur's Gate 3",
    "durge": "Baldur's Gate 3",
}


def _franchise_hint_from_query(user_query: str) -> str:
    """Gợi ý franchise để rewrite — tránh Raphael + Final Act -> BG3."""
    low = (user_query or "").lower()
    if any(k in low for k in ["honkai", "star rail", "hsr", "hoyoverse", "mihoyo"]):
        return "Honkai Star Rail"
    if "raphael" in low and "final act" in low:
        return "Honkai Star Rail"
    if any(k in low for k in ["baldur", "bg3", "baldur's gate", "dark urge", "astarion", "shadowheart", "laezel", "minthara"]):
        return "Baldur's Gate 3"
    if "raphael" in low and any(k in low for k in ["baldur", "bg3", "cambion", "house of hope", "moonrise"]):
        return "Baldur's Gate 3"
    for e in _extract_entities(user_query):
        h = _ENTITY_FRANCHISE_HINTS.get(e.lower())
        if h:
            return h
    return ""

_REWRITE_CACHE: Dict[str, Tuple[float, Dict[str, str]]] = {}
_CIRCUIT_STATE: Dict[str, Dict[str, float]] = {}


PLANNER_SYSTEM = """You are a retrieval planner for an entertainment assistant.
Choose next tool call based on query type and current evidence.

Tools:
- anilist: anime/manga/light-novel synopsis + metadata
- wiki: factual encyclopedia summaries
- fanwiki: fandom/wiki character/game lore
- reddit: community discussions/opinions
- community: fan forums/wikis via web search
- tavily: broad web search fallback

Rules:
- Return STRICT JSON only.
- action=finish only when evidence is enough for grounded answer.
- Use concise query (2-10 terms), never the raw user sentence.
- Domain routing:
  * game/character/lore -> fanwiki + tavily
  * anime chapter/season -> anilist + wiki
  * review/opinion -> reddit + community

Output:
{"action":"search|finish","tool":"anilist|wiki|fanwiki|reddit|community|tavily","query":"...","reason":"..."}
"""

SEMANTIC_QUERY_SYSTEM = """Normalize user query into retrieval-friendly forms.
Return strict JSON only:
{
  "concise":"...",
  "factual":"...",
  "community":"...",
  "character_story":"..."
}
Rules:
- Keep named entities/franchise terms.
- Remove filler/chitchat.
- Each query should be 2-10 terms.
- Never return the raw user sentence.
- For character/lore asks, character_story should include "character backstory".
- "Raphael" + "Final Act" / Honkai / Star Rail / HSR => Honkai Star Rail (NOT Baldur's Gate).
- Do NOT assume Baldur's Gate 3 unless the user names BG3, Baldur, or typical BG3 companions/locations.
"""


def _parse_json(raw: str) -> Dict[str, Any] | None:
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _evidence_brief(sources: List[Dict[str, str]], max_items: int = 8) -> str:
    lines: List[str] = []
    for s in sources[:max_items]:
        src = s.get("source", "")
        title = (s.get("title") or "")[:120]
        snip = (s.get("snippet") or "")[:180].replace("\n", " ")
        lines.append(f"- [{src}] {title} :: {snip}")
    return "\n".join(lines) if lines else "(none)"


def _cache_ttl_s() -> int:
    return max(900, min(3600, int(os.environ.get("RETRIEVER_QUERY_CACHE_S", "1800") or "1800")))


async def _semantic_query_pack(user_query: str) -> Dict[str, str]:
    now = time.time()
    cached = _REWRITE_CACHE.get(user_query)
    if cached and cached[0] > now:
        return dict(cached[1])

    raw = await generate(SEMANTIC_QUERY_SYSTEM, user_query)
    data = _parse_json(raw or "")
    out: Dict[str, str] = {}
    if data:
        for k in ("concise", "factual", "community", "character_story"):
            v = str(data.get(k) or "").strip()
            if v:
                out[k] = v

    if not out:
        out = _fallback_semantic_pack(user_query)
    else:
        # Ensure all query variants are always available for tool-specific fallback.
        fallback = _fallback_semantic_pack(user_query)
        for k in ("concise", "factual", "community", "character_story"):
            if not out.get(k):
                out[k] = fallback.get(k, "")
    _REWRITE_CACHE[user_query] = (now + _cache_ttl_s(), out)
    return out


def _query_keywords(q: str) -> List[str]:
    toks = re.findall(r"[A-Za-zÀ-ỹ0-9][A-Za-zÀ-ỹ0-9'’\-]{1,}", (q or "").lower())
    out = []
    for t in toks:
        tt = t.strip(" -_'’")
        if len(tt) < 3 or tt in _STOPWORDS:
            continue
        out.append(tt)
    seen = set()
    return [t for t in out if not (t in seen or seen.add(t))]


def _extract_entities(q: str) -> List[str]:
    # Keep title-cased entities in user text (e.g., Zariel, Raphael, Baldur's Gate 3).
    out: List[str] = []
    seen = set()
    for m in re.finditer(r"\b[A-Z][A-Za-z0-9'’\\-]{2,}\b", q or ""):
        ent = m.group(0).strip()
        key = ent.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ent)
    low = (q or "").lower()
    if ("baldur gate 3" in low or "bg3" in low) and "Baldur's Gate 3" not in out:
        out.append("Baldur's Gate 3")
    return out


def _fallback_semantic_pack(user_query: str) -> Dict[str, str]:
    low = (user_query or "").lower()
    kws = _query_keywords(user_query)
    entities = _extract_entities(user_query)
    base_tokens = entities[:] if entities else [k.title() for k in kws[:4]]
    base = " ".join(base_tokens[:5]).strip() or " ".join(kws[:6]).strip() or user_query.strip()
    franchise = "Baldur's Gate 3" if ("baldur gate 3" in low or "bg3" in low) else ""
    if not franchise:
        if "dark urge" in low or "durge" in low:
            franchise = "Baldur's Gate 3"
    if not franchise:
        for e in entities:
            hint = _ENTITY_FRANCHISE_HINTS.get(e.lower())
            if hint:
                franchise = hint
                break
    preference = any(k in low for k in ["fandom", "cộng đồng", "thích hơn", "ưa hơn", "preference", "opinion"])
    versus = any(k in low for k in [" vs ", "versus", "đánh với", "đấu với", "so sánh", "ai hơn"])

    if versus:
        concise = f"{base} {franchise}".strip()
        factual = f"{base} lore comparison {franchise}".strip()
        community = f"{base} discussion comparison {franchise}".strip()
        character_story = f"{base} character backstory {franchise}".strip()
    elif preference:
        if "dark urge" in low and any(k in low for k in ["cốt truyện gốc", "origin", "custom"]):
            concise = f"Dark Urge vs Tav {franchise}".strip()
            factual = f"Dark Urge vs Tav origin story {franchise}".strip()
            community = f"Dark Urge vs Tav community preference reddit {franchise}".strip()
            character_story = f"Dark Urge and Tav origin story {franchise}".strip()
        else:
            concise = f"{base} {franchise}".strip()
            factual = f"{base} lore {franchise}".strip()
            community = f"{base} community preference discussion {franchise}".strip()
            character_story = f"{base} origin story {franchise}".strip()
    else:
        concise = base
        factual = f"{base} {franchise}".strip()
        community = f"{base} discussion {franchise}".strip()
        character_story = f"{base} character backstory {franchise}".strip()

    return {
        "concise": re.sub(r"\s+", " ", concise).strip(),
        "factual": re.sub(r"\s+", " ", factual).strip(),
        "community": re.sub(r"\s+", " ", community).strip(),
        "character_story": re.sub(r"\s+", " ", character_story).strip(),
    }


def _allow_tavily_first_hybrid(user_query: str, domain: str) -> bool:
    """Domain general / voice-nhạc: cho Tavily ngay bước 1 — tránh fanwiki lệch IP."""
    if domain == "general":
        return True
    low = (user_query or "").lower()
    return any(
        k in low
        for k in (
            "voice actor",
            "seiyuu",
            "nhạc",
            "soundtrack",
            "theme song",
            "music",
            "final act",
        )
    )


def _detect_domain(user_query: str) -> str:
    low = (user_query or "").lower()
    if any(k in low for k in [
        "review", "redditor", "đánh giá", "opinion", "nhận xét", "ý kiến",
        "fandom", "cộng đồng", "thích hơn", "ưa hơn", "consensus", "preference",
    ]):
        return "review"
    # Named IPs / franchises often omitted in short follow-ups (e.g. "Eren Yeager sacrifice reason").
    if any(k in low for k in [
        "attack on titan", "shingeki", "eren yeager", "mikasa", "armin arlert", "levi ackerman",
        "scout regiment", "rumbling",
    ]):
        return "anime"
    if any(k in low for k in ["anime", "manga", "anilist", "chapter", "season", "arc", "light novel"]):
        return "anime"
    if any(k in low for k in ["voice actor", "seiyuu", "nhạc", "soundtrack", "ost ", "music", "theme song"]):
        return "general"
    if any(k in low for k in ["game", "character", "nhân vật", "lore", "cốt truyện", "plot", "story", "bg3", "baldur"]):
        return "character"
    return "general"


def _mode_default_tools(mode: str) -> List[str]:
    if mode == "tavily_only":
        return ["tavily"]
    if mode in {"phase_fanwiki", "tavily_fanwiki"}:
        return ["fanwiki", "tavily"]
    if mode == "phase_community":
        return ["fanwiki", "tavily", "reddit", "community"]
    return ["anilist", "wiki", "fanwiki", "reddit", "community", "tavily"]


def _domain_tools(domain: str) -> List[str]:
    if domain == "character":
        return ["fanwiki", "tavily"]
    if domain == "anime":
        return ["anilist", "wiki", "tavily"]
    if domain == "review":
        return ["reddit", "community", "tavily"]
    return ["wiki", "fanwiki", "tavily"]


def _hybrid_domain_tools(domain: str) -> List[str]:
    # In hybrid mode, prefer domain-native + community/fandom signals first,
    # and keep tavily as strict last-resort fallback.
    if domain == "character":
        return ["fanwiki", "community", "reddit", "wiki", "anilist", "tavily"]
    if domain == "anime":
        return ["anilist", "wiki", "community", "reddit", "fanwiki", "tavily"]
    if domain == "review":
        return ["reddit", "community", "fanwiki", "wiki", "anilist", "tavily"]
    return ["wiki", "fanwiki", "community", "reddit", "anilist", "tavily"]


def _is_preference_style_query(low_q: str) -> bool:
    return any(
        k in low_q
        for k in [
            "fandom",
            "cộng đồng",
            "thích hơn",
            "ưa hơn",
            "preference",
            "opinion",
        ]
    )


def _is_relevant(
    user_query: str,
    item: Dict[str, str],
    *,
    tool: str = "",
) -> bool:
    """Keep results unless clearly empty. Prefer search ranking over brittle keyword stacks."""
    low_q = (user_query or "").lower()
    hay = " ".join(
        [
            (item.get("title") or ""),
            (item.get("snippet") or ""),
            (item.get("url") or ""),
            (item.get("subreddit") or ""),
        ]
    ).lower()
    if not hay.strip():
        return False

    kws = _query_keywords(user_query)

    # Preference / "what does fandom think" — still need topical guardrails.
    if _is_preference_style_query(low_q):
        if not kws:
            return True
        hits = sum(1 for k in kws if k in hay)
        if hits <= 0:
            return False
        if "dark urge" in low_q:
            durge_origin_markers = ["dark urge", "durge", "tav", "custom origin", "origin character"]
            if not any(m in hay for m in durge_origin_markers):
                return False
        if any(k in low_q for k in ["baldur", "bg3", "dark urge", "astarion", "raphael", "zariel"]):
            if not any(m in hay for m in ["baldur", "bg3", "dark urge", "astarion", "raphael", "zariel"]):
                return False
        return True

    if not kws:
        return True

    if any(k in hay for k in kws):
        return True

    # No substring keyword hit: still trust ranked search output (overview-style), not drop all.
    t = (tool or "").strip().lower()
    if t in FACTUAL_SOURCES | CONTEXT_SOURCES and len(hay) >= 20:
        return True
    return False


def _has_anchor_evidence(user_query: str, sources: List[Dict[str, str]]) -> bool:
    low_q = (user_query or "").lower()
    if not any(k in low_q for k in ["nhân vật", "character", "cốt truyện", "plot", "story"]):
        return True
    kws = _query_keywords(user_query)
    anchors = [k for k in kws if len(k) >= 5 and k not in _GENERIC_QUERY_TERMS]
    if not anchors:
        anchors = [k for k in kws if len(k) == 4 and k not in _GENERIC_QUERY_TERMS]
    if not anchors:
        return True
    joined = " ".join(((s.get("title") or "") + " " + (s.get("snippet") or "")).lower() for s in sources[:25])
    if any(a in joined for a in anchors):
        return True
    # Overview-style: multi-source bundle is acceptable; downstream judge checks grounding.
    return len(sources) >= 2


def _evidence_quality(sources: List[Dict[str, str]]) -> Dict[str, int]:
    factual = sum(1 for s in sources if (s.get("source") or "") in FACTUAL_SOURCES)
    context = sum(1 for s in sources if (s.get("source") or "") in CONTEXT_SOURCES)
    return {"factual": factual, "context": context}


def _enough_evidence(user_query: str, sources: List[Dict[str, str]]) -> bool:
    if not _has_anchor_evidence(user_query, sources):
        return False
    q = _evidence_quality(sources)
    # AI-overview style: one solid web/encyclopedia hit is enough; or cross-source mix.
    if q["factual"] >= 1:
        return True
    if len(sources) >= 2 and q["context"] >= 1:
        return True
    return q["context"] >= 2


def _requires_authoritative_factual(user_query: str, domain: str) -> bool:
    low = (user_query or "").lower()
    # Anime/series structure queries should not stop on fanwiki-only evidence.
    if domain == "anime" or any(k in low for k in ["episode", "tập", "season", "chapter", "arc", "phần", "part"]):
        return True
    # For character asks that look non-game (e.g. anime/manga characters), ask for at least one
    # authoritative factual source before stopping in hybrid mode.
    if domain == "character":
        game_markers = [
            "game", "bg3", "baldur", "elden", "resident evil", "witcher",
            "hollow knight", "persona", "companion",
        ]
        if not any(g in low for g in game_markers):
            return True
    return False


def _enough_evidence_for_mode(user_query: str, sources: List[Dict[str, str]], mode: str, domain: str) -> bool:
    if not _enough_evidence(user_query, sources):
        return False
    if mode != "hybrid":
        return True
    if not _requires_authoritative_factual(user_query, domain):
        return True
    srcs = {(s.get("source") or "").strip().lower() for s in sources}
    return any(s in srcs for s in AUTHORITATIVE_FACTUAL_SOURCES)


def _fallback_sequence(user_query: str, allowed_tools: List[str]) -> List[str]:
    domain = _detect_domain(user_query)
    if domain == "review":
        seq = ["reddit", "community", "tavily", "fanwiki", "wiki", "anilist"]
    elif domain == "anime":
        seq = ["anilist", "wiki", "tavily", "fanwiki", "reddit", "community"]
    elif domain == "character":
        seq = ["fanwiki", "tavily", "wiki", "reddit", "community", "anilist"]
    else:
        seq = ["tavily", "wiki", "fanwiki", "reddit", "community", "anilist"]
    seen = set()
    out = [t for t in seq if t in allowed_tools and not (t in seen or seen.add(t))]
    return out or allowed_tools[:]


def _fallback_sequence_for_mode(user_query: str, allowed_tools: List[str], mode: str) -> List[str]:
    if mode != "hybrid":
        return _fallback_sequence(user_query, allowed_tools)
    domain = _detect_domain(user_query)
    seq = _hybrid_domain_tools(domain)
    seen = set()
    out = [t for t in seq if t in allowed_tools and not (t in seen or seen.add(t))]
    return out or allowed_tools[:]


def _next_fallback_tool(seq: List[str], idx: int, *, avoid: str = "") -> Tuple[str, int]:
    if not seq:
        return "", idx
    n = len(seq)
    for _ in range(n):
        tool = seq[idx % n]
        idx += 1
        if avoid and tool == avoid and n > 1:
            continue
        return tool, idx
    return seq[0], idx


def _choose_query_for_tool(user_query: str, tool: str, semantic_pack: Dict[str, str]) -> str:
    concise = (semantic_pack.get("concise") or "").strip()
    factual = (semantic_pack.get("factual") or concise).strip()
    community = (semantic_pack.get("community") or concise).strip()
    character_story = (semantic_pack.get("character_story") or factual).strip()
    low = (user_query or "").lower()
    preference = any(k in low for k in ["fandom", "cộng đồng", "thích hơn", "ưa hơn", "preference", "opinion"])
    is_bg3 = any(k in low for k in ["baldur", "bg3", "dark urge", "astarion", "zariel", "tav"]) or (
        "raphael" in low
        and any(k in low for k in ["baldur", "bg3", "cambion", "house of hope", "moonrise"])
    )

    if any(k in low for k in ["nhân vật", "character", "cốt truyện", "story", "plot", "lore"]):
        if tool in {"fanwiki", "wiki", "anilist"}:
            return character_story or factual or concise or user_query.strip()
        if tool == "reddit" and preference and is_bg3:
            return "subreddit:BaldursGate3 Dark Urge Tav origin story preference"
        return community or concise or user_query.strip()
    if tool in {"reddit", "community"}:
        if tool == "reddit" and preference and is_bg3:
            return "subreddit:BaldursGate3 Dark Urge Tav origin story preference"
        return community or concise or user_query.strip()
    return factual or concise or user_query.strip()


def _sanitize_planner_query(user_query: str, planner_query: str, tool: str, semantic_pack: Dict[str, str]) -> str:
    q = (planner_query or "").strip()
    raw = (user_query or "").strip()
    if not q:
        return _choose_query_for_tool(user_query, tool, semantic_pack)
    # Never pass full raw sentence; enforce short normalized query.
    if q.lower() == raw.lower() or len(q.split()) > 12:
        return _choose_query_for_tool(user_query, tool, semantic_pack)
    return q


def _circuit_cfg() -> Tuple[int, int]:
    fails = max(2, min(10, int(os.environ.get("RETRIEVER_CIRCUIT_FAILS", "3") or "3")))
    cooldown = max(300, min(1800, int(os.environ.get("RETRIEVER_CIRCUIT_COOLDOWN_S", "600") or "600")))
    return fails, cooldown


def _is_circuit_open(tool: str) -> bool:
    state = _CIRCUIT_STATE.get(tool) or {}
    return float(state.get("disabled_until", 0.0) or 0.0) > time.time()


def _record_tool_failure(tool: str) -> None:
    fails_threshold, cooldown = _circuit_cfg()
    state = _CIRCUIT_STATE.setdefault(tool, {"fails": 0.0, "disabled_until": 0.0})
    state["fails"] = float(state.get("fails", 0.0) + 1.0)
    if state["fails"] >= fails_threshold:
        state["disabled_until"] = time.time() + cooldown
        state["fails"] = 0.0
        logger.warning("retriever circuit open tool={} cooldown_s={}", tool, cooldown)


def _record_tool_success(tool: str) -> None:
    state = _CIRCUIT_STATE.setdefault(tool, {"fails": 0.0, "disabled_until": 0.0})
    state["fails"] = 0.0


def _overview_parallel_enabled() -> bool:
    return (os.environ.get("RETRIEVER_OVERVIEW_PARALLEL", "true") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _overview_parallel_tool_order(domain: str, allowed: List[str]) -> List[str]:
    """Multi-engine order (web + encyclopedia + specialist), like AI overview breadth."""
    if domain == "review":
        seq = ["reddit", "community", "tavily", "fanwiki", "wiki", "anilist"]
    elif domain == "anime":
        seq = ["tavily", "wiki", "anilist", "fanwiki", "reddit", "community"]
    elif domain == "character":
        seq = ["tavily", "fanwiki", "wiki", "reddit", "community", "anilist"]
    else:
        seq = ["tavily", "wiki", "fanwiki", "reddit", "community", "anilist"]
    seen: set[str] = set()
    out: List[str] = []
    for t in seq:
        if t in allowed and t not in seen and t in TOOL_REGISTRY:
            seen.add(t)
            out.append(t)
    for t in allowed:
        if t not in seen and t in TOOL_REGISTRY:
            seen.add(t)
            out.append(t)
    return out[:4]


async def _overview_parallel_fetch(
    user_query: str,
    *,
    allowed: List[str],
    semantic_pack: Dict[str, str],
    domain: str,
    seen_urls: set,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], bool, bool]:
    """Parallel fetch across several search backends; merge with URL dedup. Returns (sources, steps, tavily_used, tried_non_tavily)."""
    tools = _overview_parallel_tool_order(domain, allowed)
    if len(tools) < 2:
        return [], [], False, False

    async def _call(tool: str) -> Tuple[str, List[Dict[str, str]], str]:
        try:
            out = await TOOL_REGISTRY[tool](_choose_query_for_tool(user_query, tool, semantic_pack))
            _record_tool_success(tool)
            return tool, list(out) if out else [], ""
        except Exception as e:
            _record_tool_failure(tool)
            logger.warning("overview_parallel tool {} failed: {}", tool, e)
            return tool, [], str(e)

    gathered = await asyncio.gather(*[_call(t) for t in tools])
    merged: List[Dict[str, str]] = []
    steps: List[Dict[str, Any]] = []
    tavily_used = False
    tried_non_tavily = False
    sub = 0
    for tool, results, err in gathered:
        sub += 1
        if tool == "tavily":
            tavily_used = True
        q = _choose_query_for_tool(user_query, tool, semantic_pack)
        filtered = 0
        added = 0
        for r in results:
            if not _is_relevant(user_query, r, tool=tool):
                filtered += 1
                continue
            url = (r.get("url") or "").strip()
            if url and url in seen_urls:
                filtered += 1
                continue
            if url:
                seen_urls.add(url)
            if not r.get("source"):
                r["source"] = tool
            merged.append(r)
            added += 1
        if results and tool != "tavily":
            tried_non_tavily = True
        quality = _evidence_quality(merged)
        steps.append(
            {
                "step": 0,
                "substep": sub,
                "action": "parallel_overview",
                "tool": tool,
                "query": q,
                "reason": "parallel_overview_bootstrap",
                "results": len(results),
                "filtered_count": filtered,
                "added": added,
                "total": len(merged),
                "factual_count": quality["factual"],
                "context_count": quality["context"],
                "error": err,
            }
        )
    return merged, steps, tavily_used, tried_non_tavily


async def agentic_retrieve(
    user_query: str,
    *,
    allowed_tools: List[str] | None = None,
    max_steps: int = 4,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    mode = (os.environ.get("RETRIEVER_MODE") or "tavily_only").strip().lower()
    domain = _detect_domain(user_query)
    default_tools = _mode_default_tools(mode)
    routed_tools = _hybrid_domain_tools(domain) if mode == "hybrid" else _domain_tools(domain)

    if allowed_tools is None:
        allowed = [t for t in default_tools if t in TOOL_REGISTRY and (t in routed_tools or t == "tavily")]
    else:
        allowed = [t for t in allowed_tools if t in TOOL_REGISTRY]
        # Enforce domain routing in hybrid/phase modes.
        if mode != "tavily_only":
            allowed = [t for t in allowed if t in routed_tools or t == "tavily"]

    if not allowed:
        return [], {"steps": [], "finished": False, "reason": "no_allowed_tools"}

    sources: List[Dict[str, str]] = []
    seen_urls = set()
    steps: List[Dict[str, Any]] = []
    finished_reason = "max_steps"
    fallback_seq = _fallback_sequence_for_mode(user_query, allowed, mode)
    fallback_idx = 0
    consecutive_nohit = 0
    last_tool = ""
    tried_non_tavily = False
    tavily_used = False
    semantic_pack = await _semantic_query_pack(user_query)
    logger.info(
        "retriever.telemetry query_rewrite domain={} mode={} concise={} factual={} community={} character_story={}",
        domain,
        mode,
        semantic_pack.get("concise", ""),
        semantic_pack.get("factual", ""),
        semantic_pack.get("community", ""),
        semantic_pack.get("character_story", ""),
    )

    # AI-overview style: hit several major search backends in parallel first, then let the planner refine.
    if mode == "hybrid" and _overview_parallel_enabled() and len(allowed) >= 2:
        pb_merged, pb_steps, pb_tavily, pb_non_tavily = await _overview_parallel_fetch(
            user_query,
            allowed=allowed,
            semantic_pack=semantic_pack,
            domain=domain,
            seen_urls=seen_urls,
        )
        for s in pb_steps:
            steps.append(s)
        sources.extend(pb_merged)
        if pb_tavily:
            tavily_used = True
        if pb_non_tavily:
            tried_non_tavily = True
        if _enough_evidence_for_mode(user_query, sources, mode, domain):
            trace = {
                "steps": steps,
                "finished": True,
                "reason": "enough_evidence_after_overview",
                "domain": domain,
                "mode": mode,
                "allowed_tools": allowed,
            }
            logger.info(
                "retriever.telemetry final_reason={} evidence={}",
                "enough_evidence_after_overview",
                _evidence_quality(sources),
            )
            return sources, trace

    for step_idx in range(1, max_steps + 1):
        planner_input = (
            f"User query:\n{user_query}\n\n"
            f"Domain: {domain}\n"
            f"Allowed tools: {', '.join(allowed)}\n\n"
            f"Current evidence count: {len(sources)}\n"
            f"Current evidence summary:\n{_evidence_brief(sources)}\n\n"
            f"Semantic rewrite hints: {semantic_pack}\n"
            "Decide next action."
        )
        decision_raw = await generate(PLANNER_SYSTEM, planner_input)
        decision = _parse_json(decision_raw or "")

        if not decision:
            tool, fallback_idx = _next_fallback_tool(fallback_seq, fallback_idx)
            q = _choose_query_for_tool(user_query, tool, semantic_pack)
            decision = {"action": "search", "tool": tool, "query": q, "reason": "fallback: parse failed"}

        action = str(decision.get("action") or "search").strip().lower()
        tool = str(decision.get("tool") or "").strip().lower()
        q_raw = str(decision.get("query") or "").strip()
        reason = str(decision.get("reason") or "").strip()

        if action == "finish" and sources:
            finished_reason = reason or "planner_finish"
            steps.append({"step": step_idx, "action": "finish", "reason": finished_reason})
            break

        if tool not in allowed or _is_circuit_open(tool):
            tool, fallback_idx = _next_fallback_tool(fallback_seq, fallback_idx, avoid=tool)
            reason = f"fallback after invalid/open-circuit -> {tool}"

        if mode == "hybrid" and tool == "tavily":
            # Mặc định hybrid: fanwiki/reddit trước; general / voice-nhạc: Tavily được ưu tiên ngay.
            if not _allow_tavily_first_hybrid(user_query, domain):
                if not tried_non_tavily and any(t != "tavily" for t in allowed):
                    tool, fallback_idx = _next_fallback_tool(fallback_seq, fallback_idx, avoid="tavily")
                    reason = f"hybrid prefers fandom/community first -> {tool}"
                elif consecutive_nohit < 1 and step_idx < max_steps and len(sources) > 0:
                    tool, fallback_idx = _next_fallback_tool(fallback_seq, fallback_idx, avoid="tavily")
                    reason = f"hybrid keeps tavily as late fallback -> {tool}"

        if consecutive_nohit >= 1 and tool == last_tool:
            tool, fallback_idx = _next_fallback_tool(fallback_seq, fallback_idx, avoid=last_tool)
            reason = f"fallback rotate after no-hit -> {tool}"

        q = _sanitize_planner_query(user_query, q_raw, tool, semantic_pack)
        fn = TOOL_REGISTRY[tool]
        results: List[Dict[str, str]]
        err = ""
        try:
            results = await fn(q)
            _record_tool_success(tool)
        except Exception as e:
            err = str(e)
            _record_tool_failure(tool)
            logger.warning("agentic_retrieve tool {} failed: {}", tool, e)
            results = []

        added = 0
        filtered = 0
        for r in results:
            if not _is_relevant(user_query, r, tool=tool):
                filtered += 1
                continue
            url = (r.get("url") or "").strip()
            if url and url in seen_urls:
                filtered += 1
                continue
            if url:
                seen_urls.add(url)
            if not r.get("source"):
                r["source"] = tool
            sources.append(r)
            added += 1

        quality = _evidence_quality(sources)
        step_log = {
            "step": step_idx,
            "action": "search",
            "tool": tool,
            "query": q,
            "reason": reason,
            "results": len(results),
            "filtered_count": filtered,
            "added": added,
            "total": len(sources),
            "factual_count": quality["factual"],
            "context_count": quality["context"],
            "error": err,
        }
        steps.append(step_log)
        logger.info("retriever.telemetry step={}", step_log)

        if added <= 0:
            consecutive_nohit += 1
        else:
            consecutive_nohit = 0
        last_tool = tool
        if tool != "tavily":
            tried_non_tavily = True
        if tool == "tavily":
            tavily_used = True

        if _enough_evidence_for_mode(user_query, sources, mode, domain):
            finished_reason = "enough_evidence"
            break

    if mode == "hybrid" and not tavily_used and "tavily" in allowed and not _enough_evidence_for_mode(user_query, sources, mode, domain):
        # Final hard fallback: when hybrid cannot ground enough, do one tavily pass.
        q = _choose_query_for_tool(user_query, "tavily", semantic_pack)
        err = ""
        try:
            results = await TOOL_REGISTRY["tavily"](q)
            _record_tool_success("tavily")
        except Exception as e:
            err = str(e)
            _record_tool_failure("tavily")
            logger.warning("agentic_retrieve tool tavily failed: {}", e)
            results = []

        added = 0
        filtered = 0
        for r in results:
            if not _is_relevant(user_query, r, tool="tavily"):
                filtered += 1
                continue
            url = (r.get("url") or "").strip()
            if url and url in seen_urls:
                filtered += 1
                continue
            if url:
                seen_urls.add(url)
            if not r.get("source"):
                r["source"] = "tavily"
            sources.append(r)
            added += 1

        quality = _evidence_quality(sources)
        step_log = {
            "step": len(steps) + 1,
            "action": "search",
            "tool": "tavily",
            "query": q,
            "reason": "hybrid final fallback",
            "results": len(results),
            "filtered_count": filtered,
            "added": added,
            "total": len(sources),
            "factual_count": quality["factual"],
            "context_count": quality["context"],
            "error": err,
        }
        steps.append(step_log)
        logger.info("retriever.telemetry step={}", step_log)
        if _enough_evidence_for_mode(user_query, sources, mode, domain):
            finished_reason = "hybrid_tavily_fallback"

    trace = {
        "steps": steps,
        "finished": True,
        "reason": finished_reason,
        "domain": domain,
        "mode": mode,
        "allowed_tools": allowed,
    }
    logger.info("retriever.telemetry final_reason={} evidence={}", finished_reason, _evidence_quality(sources))
    return sources, trace

