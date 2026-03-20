# services/agent_service/llm/retriever_router.py
"""
Groq-based reasoning router: analyzes user message and picks the best
retriever *before* we hit any API, so we don't waste calls on irrelevant
sources (e.g. AniList for a game question).
"""
import json
import re
from typing import Any, Dict

from loguru import logger

from services.agent_service.llm.client import generate

VALID_RETRIEVERS = {"anilist", "wiki", "community", "tavily"}
DEFAULT_RETRIEVER = "wiki"

ROUTER_SYSTEM = """You are a retriever router for an entertainment chatbot.
Given a user message (may be in Vietnamese or English), decide which data source
is BEST to answer it. Output ONLY a JSON object — no markdown, no explanation.

Sources:
- "anilist"   : anime, manga, light novel specific info (synopsis, season, characters, episodes). Use when user asks about a specific anime/manga title or season.
- "wiki"      : factual knowledge — game lore, movie plot, historical facts about any entertainment topic (e.g. Baldur's Gate 3 story, Elden Ring lore, film summary).
- "community" : opinions, reviews, discussions, comparisons, "what does reddit think", recommendations from community. Use when user wants community perspectives, ratings, or debates.
- "tavily"    : general web search — news, events, release dates, anything that doesn't clearly fit above, or when the query is too vague.

Rules:
1. If user explicitly mentions "reddit", "review", "đánh giá", "ý kiến", "opinion", "cộng đồng" → "community"
2. If user asks about a specific anime/manga title with words like "season", "arc", "tập", "chapter", "nhân vật" → "anilist"
3. If user asks factual/lore about a game, movie, or general entertainment → "wiki"
4. If unclear or too general → "tavily"

Also translate the core query to clean English in "query_en" to help the retriever search better.
IMPORTANT for query_en:
- Extract ONLY the title/subject. Example: "Cho mình xin tóm tắt Takopi Original Sin từ AniList" → "Takopi Original Sin" (NOT "Takopi Original Sin summary from AniList").
- Strip ALL filler: "cho tôi xin", "bạn có biết", "tóm tắt", "review", "từ reddit", "từ anilist", "từ wiki", etc.
- For review queries, keep the subject + "review": "review BG3 từ reddit" → "Baldur's Gate 3"
- query_en should be a clean search term, not a sentence.

Output format (strict JSON, no extra text):
{"retriever": "anilist|wiki|community|tavily", "query_en": "clean search term", "reason": "one-line explanation"}
"""


def _parse_router_json(raw: str) -> Dict[str, Any] | None:
    """Try to extract a JSON object from LLM output, tolerating markdown fences."""
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict) and "retriever" in obj:
            return obj
    except json.JSONDecodeError:
        pass
    # Fallback: find first {...} in text
    match = re.search(r"\{[^}]+\}", cleaned, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict) and "retriever" in obj:
                return obj
        except json.JSONDecodeError:
            pass
    return None


def _keyword_fallback(text: str) -> Dict[str, str]:
    """Fast keyword-based routing when Groq is unavailable or fails."""
    low = text.lower()
    community_signals = ["reddit", "redditor", "review", "đánh giá", "ý kiến",
                         "opinion", "cộng đồng", "discussion", "nhận xét"]
    if any(w in low for w in community_signals):
        return {"retriever": "community", "query_en": text, "reason": "keyword: community signal"}
    anime_signals = ["anime", "manga", "one piece", "naruto", "jujutsu", "demon slayer",
                     "attack on titan", "aot", "season", "arc", "tập", "chapter",
                     "light novel", "anilist"]
    if any(w in low for w in anime_signals):
        return {"retriever": "anilist", "query_en": text, "reason": "keyword: anime/manga signal"}
    wiki_signals = ["lore", "cốt truyện", "plot", "story", "wiki", "gameplay",
                    "game", "phim", "movie", "ending"]
    if any(w in low for w in wiki_signals):
        return {"retriever": "wiki", "query_en": text, "reason": "keyword: wiki/factual signal"}
    return {"retriever": DEFAULT_RETRIEVER, "query_en": text, "reason": "keyword: default"}


async def route_retriever(user_msg: str) -> Dict[str, str]:
    """
    Analyze user message via Groq and return routing decision.
    Returns dict with keys: retriever, query_en, reason.
    Falls back to keyword heuristic on any failure.
    """
    msg = (user_msg or "").strip()
    if not msg:
        return {"retriever": DEFAULT_RETRIEVER, "query_en": "", "reason": "empty message"}

    try:
        raw = await generate(ROUTER_SYSTEM, msg)
        if raw:
            parsed = _parse_router_json(raw)
            if parsed:
                retriever = str(parsed.get("retriever", "")).strip().lower()
                if retriever not in VALID_RETRIEVERS:
                    retriever = DEFAULT_RETRIEVER
                query_en = str(parsed.get("query_en", "")).strip() or msg
                reason = str(parsed.get("reason", "")).strip()
                return {"retriever": retriever, "query_en": query_en, "reason": reason}
            else:
                logger.warning("retriever_router: failed to parse JSON from: {!r}", raw[:200])
    except Exception as e:
        logger.warning("retriever_router: Groq call failed, using keyword fallback: {}", e)

    return _keyword_fallback(msg)
