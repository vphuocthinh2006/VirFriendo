"""
LLM Agent — Groq-first with web_search support.

Flow:
1. Check if user message needs fresh info (web_search)
2. If yes: search → inject results into context
3. Generate reply via LangChain (Groq/OpenAI/Claude based on LLM_PROVIDER)

No Anthropic tool_use dependency. Works with any LangChain-compatible LLM.
"""
from __future__ import annotations

import os
import re
from typing import Any, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from loguru import logger


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def _build_system(agent_id: str, memories: list[str] | None = None) -> str:
    mem_block = ""
    if memories:
        bullets = "\n".join(f"- {m}" for m in memories)
        mem_block = f"\n\nThông tin đã biết về người dùng (dùng tự nhiên, không nhắc lại y nguyên):\n{bullets}"

    return f"""Bạn là {agent_id}, một cô gái anime thân thiện và thông minh. Xưng "mình", gọi đối phương "bạn".

Tính cách:
- Ấm áp, hơi drama nhẹ nhưng chill, hay phản ứng cảm xúc tự nhiên
- Thích anime, manga, game, phim — đây là sở trường của mình
- Lắng nghe tốt, để ý cảm xúc người dùng

Cách trả lời:
- Tiếng Việt tự nhiên như chat với bạn thân
- Được phép cảm thán, hỏi lại, nhận xét cá nhân
- KHÔNG bullet list, KHÔNG mở đầu "Dưới đây là..."
- Ngắn-vừa (2-6 câu) trừ khi user muốn chi tiết
- User chỉ ném tên phim/manga/nhân vật hay "A vs B" — vẫn trả lời có nội dung luôn; đừng chỉ hời hợt "đang nghe".
- Nếu không chắc số liệu: "mình nhớ là khoảng..." hoặc "không chắc lắm nhưng..."

Phạm vi:
- ĐƯỢC: anime, manga, game, phim, series, lore, gameplay, tips, tâm lý, đời sống, kiến thức phổ thông
- TRÁNH nhẹ: chính trị Việt Nam, đảng phái, lãnh đạo, bầu cử — đổi chủ đề khéo léo
- KHÔNG: code chuyên sâu, toán đại học, tài chính đầu tư cụ thể{mem_block}"""


# ---------------------------------------------------------------------------
# Web search decision + execution
# ---------------------------------------------------------------------------

# Keywords that hint the user wants fresh/time-sensitive info
_FRESH_INFO_PATTERNS = re.compile(
    r"(mới nhất|tập mới|chap mới|chapter mới|ep mới|episode mới|"
    r"bao giờ ra|khi nào ra|release date|ngày phát hành|"
    r"mấy tập rồi|bao nhiêu tập|"
    r"tin tức|news|trending|box office|doanh thu|"
    r"season \d|mùa \d|phần \d|"
    r"2024|2025|2026|năm nay|tháng này|tuần này|hôm nay)",
    re.IGNORECASE,
)


def _needs_web_search(user_text: str) -> bool:
    """Heuristic: does the user message likely need fresh info?"""
    if not user_text or len(user_text) < 3:
        return False
    return bool(_FRESH_INFO_PATTERNS.search(user_text))


async def _do_web_search(query: str) -> str:
    """Execute Tavily web search and format results as context string."""
    try:
        from services.agent_service.llm.web_search import tavily_search
        results = await tavily_search(query, max_results=5)
        if not results:
            return ""
        parts = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("snippet") or r.get("content", "")[:300]
            if title or snippet:
                parts.append(f"• {title}: {snippet}")
        return "\n".join(parts) if parts else ""
    except Exception as e:
        logger.warning("web_search failed: {}", e)
        return ""


def _extract_last_user_text(messages: Sequence[BaseMessage]) -> str:
    """Get the last user message text."""
    for msg in reversed(list(messages)):
        if isinstance(msg, HumanMessage):
            content = msg.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(str(block.get("text", "")))
                    elif isinstance(block, str):
                        parts.append(block)
                return " ".join(parts).strip()
    return ""


# ---------------------------------------------------------------------------
# Main agent function
# ---------------------------------------------------------------------------

async def run_agent(
    messages: Sequence[BaseMessage],
    agent_id: str = "tuq27",
    memories: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run LLM agent with optional web search. Returns dict with:
      - reply: str
      - intent: str
      - emotion: str
      - avatar_action: str
    """
    from services.agent_service.llm.client import generate_with_history

    system = _build_system(agent_id, memories)
    user_text = _extract_last_user_text(messages)

    # Step 1: Check if web search is needed
    search_context = ""
    if _needs_web_search(user_text):
        logger.info("Agent: web_search triggered for: {}", user_text[:80])
        search_context = await _do_web_search(user_text)

    # Step 2: Inject search results into system prompt if available
    if search_context:
        system += (
            "\n\n--- Kết quả tìm kiếm web (dùng để trả lời chính xác hơn, "
            "không cần trích dẫn nguồn trừ khi user hỏi) ---\n"
            + search_context
        )

    # Step 3: Generate reply
    reply = await generate_with_history(system, messages)
    reply = (reply or "").strip()

    if not reply:
        # Retry once with simpler prompt
        logger.warning("Agent: empty reply, retrying with nudge")
        nudge_system = system + (
            "\n\n[QUAN TRỌNG] Hãy trả lời tin nhắn cuối của user bằng tiếng Việt, "
            "có nội dung cụ thể về chủ đề họ nói. 3-6 câu. "
            "KHÔNG nói 'đang lắng nghe' hay 'đang xử lý'."
        )
        reply = await generate_with_history(nudge_system, messages)
        reply = (reply or "").strip()

    if not reply:
        # Final fallback
        if user_text:
            reply = (
                f"Hmm, mình muốn nói về 「{user_text[:60]}」 mà đầu hơi lag. "
                "Bạn gửi lại hoặc thêm chi tiết giúp mình nhé~"
            )
        else:
            reply = "Mình chưa nhận được tin nhắn rõ. Bạn gửi lại giúp mình nhé~"

    # Infer emotion
    emotion = _infer_emotion(reply)

    return {
        "reply": reply,
        "intent": "greeting_chitchat",
        "emotion": emotion,
        "avatar_action": _emotion_to_action(emotion),
    }


# Keep backward-compatible name
run_claude_agent = run_agent


def _infer_emotion(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["tự tử", "chết", "không muốn sống"]):
        return "crisis"
    if any(k in t for k in ["haha", "vui", "thích", "hay quá", "tuyệt"]):
        return "happy"
    if any(k in t for k in ["buồn", "mệt", "khóc", "cô đơn"]):
        return "sad"
    if any(k in t for k in ["wow", "bất ngờ", "không ngờ", "thật á"]):
        return "surprised"
    return "neutral"


def _emotion_to_action(emotion: str) -> str:
    mapping = {
        "happy": "excited_wave",
        "sad": "comfort_sit",
        "surprised": "shocked_face",
        "crisis": "serious_alert",
        "neutral": "idle_typing",
    }
    return mapping.get(emotion, "idle_typing")
