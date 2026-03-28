"""Quickstart mode: store user lines in Redis and periodically summarize personality via LLM."""

from __future__ import annotations

import os

from loguru import logger

from services.core.config import settings
from services.core.redis_client import get_redis


def _msgs_key(user_id: str, agent_id: str) -> str:
    return f"vf:q:{user_id}:{agent_id}:msgs"


def _sum_key(user_id: str, agent_id: str) -> str:
    return f"vf:q:{user_id}:{agent_id}:sum"


async def get_quickstart_summary(user_id: str, agent_id: str) -> str | None:
    if not agent_id:
        return None
    r = await get_redis()
    if not r:
        return None
    try:
        return await r.get(_sum_key(user_id, agent_id))
    except Exception as e:
        logger.debug("Redis get summary: {}", e)
        return None


async def append_user_line_and_maybe_summarize(user_id: str, agent_id: str, user_text: str) -> None:
    if not agent_id or not (user_text or "").strip():
        return
    r = await get_redis()
    if not r:
        return
    try:
        key = _msgs_key(user_id, agent_id)
        await r.rpush(key, user_text.strip()[:3000])
        await r.ltrim(key, -50, -1)
        n = await r.llen(key)
        if n > 0 and n % 3 == 0:
            lines = await r.lrange(key, 0, -1)
            summary = await _summarize_lines(lines)
            if summary:
                await r.set(_sum_key(user_id, agent_id), summary[:4000])
    except Exception as e:
        logger.warning("quickstart redis/summarize: {}", e)


async def _summarize_lines(lines: list[str]) -> str | None:
    if not lines:
        return None
    key = (settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        return None
    try:
        from langchain_groq import ChatGroq

        model = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        llm = ChatGroq(model=model, temperature=0.25, api_key=key)
        joined = "\n".join(f"- {t}" for t in lines[-40:])
        prompt = (
            "You are summarizing the human user's personality, tone, and emotional patterns "
            "from their chat messages. Output 2-4 short sentences in English. "
            "Do not invent facts; stay grounded in the text.\n\nMessages:\n"
            f"{joined}"
        )
        out = await llm.ainvoke(prompt)
        text = (getattr(out, "content", None) or str(out)).strip()
        return text or None
    except Exception as e:
        logger.warning("Personality LLM summarize failed: {}", e)
        return None
