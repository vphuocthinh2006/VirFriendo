"""
Claude tool_use agent — replaces LangGraph workflow.

Single LLM call with tools:
  - web_search(query)     : Tavily, only when fresh info needed
  - recall_memory(topic)  : user memories from DB (future)
  - generate_image(prompt): Replicate FLUX

Claude decides when to use tools. No Python classifier, no routing nodes.
"""
from __future__ import annotations

import json
import os
from typing import Any, Sequence

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from loguru import logger


def _stringify_lc_content(content: Any) -> str:
    """Normalize LangChain message content to a single string for the Anthropic API."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text") or ""))
                elif "text" in block:
                    parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(p.strip() for p in parts if p.strip()).strip()
    return str(content).strip()


def _extract_text_from_anthropic_content(content: Any) -> str:
    """Pull user-visible text from Anthropic message.content blocks (SDK objects or dicts)."""
    parts: list[str] = []
    if not content:
        return ""
    for block in content:
        if isinstance(block, dict):
            btype = str(block.get("type") or "").lower()
            if btype == "thinking" or "tool" in btype:
                continue
            if btype == "text" or block.get("text") is not None:
                txt = block.get("text")
                if isinstance(txt, str) and txt.strip():
                    parts.append(txt)
            continue
        btype = str(getattr(block, "type", "") or "").lower()
        if btype == "thinking" or "tool" in btype:
            continue
        txt = getattr(block, "text", None)
        if isinstance(txt, str) and txt.strip():
            parts.append(txt)
    return "".join(parts).strip()


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool_use format)
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for fresh, factual information. "
            "Use ONLY when the user asks about: release dates, episode counts, "
            "latest chapters, recent news, current rankings, box office numbers, "
            "or any time-sensitive data you're not confident about. "
            "Do NOT use for general knowledge, lore, gameplay tips, or opinions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query in English for best results"
                }
            },
            "required": ["query"]
        }
    }
]

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
- KHÔNG: code chuyên sâu, toán đại học, tài chính đầu tư cụ thể

Dùng tool web_search CHỈ khi cần thông tin mới nhất (ngày phát hành, số tập mới nhất, tin tức gần đây).{mem_block}"""


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def _execute_web_search(query: str) -> str:
    """Execute Tavily web search."""
    try:
        from services.agent_service.llm.web_search import tavily_search
        results = await tavily_search(query, max_results=5)
        if not results:
            return "Không tìm thấy kết quả."
        parts = []
        for r in results:
            title = r.get("title", "")
            snippet = r.get("snippet") or r.get("content", "")[:300]
            if title or snippet:
                parts.append(f"**{title}**: {snippet}")
        return "\n\n".join(parts) if parts else "Không có kết quả hữu ích."
    except Exception as e:
        logger.warning("web_search failed: {}", e)
        return f"Tìm kiếm thất bại: {e}"


def _snippet_last_user(messages: Sequence[BaseMessage], max_len: int = 72) -> str:
    for msg in reversed(list(messages)):
        if isinstance(msg, HumanMessage):
            raw = _stringify_lc_content(msg.content).strip()
            if raw:
                if len(raw) > max_len:
                    return raw[: max_len - 1] + "…"
                return raw
    return ""


def _fallback_visible_reply(messages: Sequence[BaseMessage]) -> str:
    """Không giả vờ 'đang nghe' khi model thực chất không trả lời chủ đề."""
    snip = _snippet_last_user(messages)
    if snip:
        return (
            f"Mình đang bị lag, chưa nhả được câu hay cho 「{snip}」… "
            "Bạn thích mình đi theo kiểu so sánh vibe nhân vật, hay tóm plot/mối quan hệ? "
            "Gợi thêm một dòng là mình bám chủ đề nhé~"
        )
    return (
        "Mình chưa tạo được câu trả lời (lỗi model hay mạng). "
        "Bạn gửi lại một tin giúp mình được không nhé?"
    )


async def _anthropic_plain_retry_reply(
    client: Any,
    *,
    model: str,
    max_tokens: int,
    system: str,
    anthropic_messages: list[dict[str, Any]],
) -> str:
    """Một shot không tool — ép model trả text khi shot trước rỗng / chỉ tool."""
    nudge = (
        "[Nội bộ một lần — trả lời cho user cuối]\n"
        "Lần trước phản hồi không có đoạn chữ khả dụng. "
        "Hãy trả lời tin nhắn user cuối cùng trong cuộc trò chuyện bằng tiếng Việt "
        "(3–8 câu), có nội dung về chủ đề họ nói. Không chỉ báo là đang lắng nghe. Không gọi tool."
    )
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=min(max_tokens, 1024),
            system=system,
            messages=list(anthropic_messages) + [{"role": "user", "content": nudge}],
            temperature=0.75,
        )
        if getattr(response, "stop_reason", None) == "end_turn":
            return (_extract_text_from_anthropic_content(response.content) or "").strip()
    except Exception as e:
        logger.warning("Anthropic plain retry failed: {}", e)
    return ""


async def _execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "web_search":
        return await _execute_web_search(tool_input.get("query", ""))
    return f"Tool '{tool_name}' không được hỗ trợ."


# ---------------------------------------------------------------------------
# Main agent function
# ---------------------------------------------------------------------------

async def run_claude_agent(
    messages: Sequence[BaseMessage],
    agent_id: str = "tuq27",
    memories: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run Claude with tool_use. Returns dict with:
      - reply: str
      - intent: str (inferred)
      - emotion: str
      - avatar_action: str
    """
    provider = (os.environ.get("LLM_PROVIDER") or "auto").strip().lower()
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    use_claude = provider in {"claude", "auto"} and bool(anthropic_key)

    if not use_claude:
        # Fallback to langchain client
        from services.agent_service.llm.client import generate_with_history
        system = _build_system(agent_id, memories)
        reply = await generate_with_history(system, messages)
        reply = (reply or "").strip() or _fallback_visible_reply(messages)
        return {
            "reply": reply,
            "intent": "greeting_chitchat",
            "emotion": "neutral",
            "avatar_action": "idle_typing",
        }

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=anthropic_key)
        system = _build_system(agent_id, memories)

        # Convert LangChain messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                # Merge into system prompt
                system = _stringify_lc_content(msg.content) + "\n\n" + system
            elif isinstance(msg, HumanMessage):
                uc = _stringify_lc_content(msg.content)
                if uc:
                    anthropic_messages.append({"role": "user", "content": uc})
            elif isinstance(msg, AIMessage):
                ac = _stringify_lc_content(msg.content)
                if ac:
                    anthropic_messages.append({"role": "assistant", "content": ac})

        if not anthropic_messages:
            logger.warning("run_claude_agent: no user/assistant segments after stringify; check message format")
            return {
                "reply": _fallback_visible_reply(messages),
                "intent": "greeting_chitchat",
                "emotion": "neutral",
                "avatar_action": "idle_typing",
            }

        # Agentic loop: Claude may call tools
        max_iterations = 3
        max_tokens = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "2048"))
        model_name = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        reply = ""
        for iteration in range(max_iterations):
            response = await client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                system=system,
                messages=anthropic_messages,
                tools=TOOLS,
                temperature=0.7,
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                reply = _extract_text_from_anthropic_content(response.content)
                break

            elif response.stop_reason == "tool_use":
                # Execute tools and continue
                tool_results = []
                assistant_content = []

                for block in response.content:
                    assistant_content.append(block)
                    if block.type == "tool_use":
                        logger.info("Claude tool_use: {} query={}", block.name, block.input)
                        result = await _execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add assistant turn with tool calls
                anthropic_messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                })
                # Add tool results
                anthropic_messages.append({
                    "role": "user",
                    "content": tool_results,
                })

            elif response.stop_reason == "max_tokens":
                # Truncated mid-generation. Harvest any partial text; if empty,
                # retry once with a larger budget before giving up.
                reply = _extract_text_from_anthropic_content(response.content)
                logger.warning(
                    "Claude hit max_tokens (limit={}) iter={} text_len={} blocks={}",
                    max_tokens,
                    iteration,
                    len(reply),
                    [getattr(b, "type", type(b).__name__) for b in (response.content or [])],
                )
                if reply:
                    break
                if max_tokens < 4096:
                    max_tokens = 4096
                    continue
                break

            else:
                # Unexpected stop reason — still harvest any text blocks
                reply = _extract_text_from_anthropic_content(response.content)
                logger.warning(
                    "Claude unusual stop_reason={} blocks={} text_len={}",
                    response.stop_reason,
                    [getattr(b, "type", type(b).__name__) for b in (response.content or [])],
                    len(reply or ""),
                )
                break
        else:
            reply = reply or ""
            logger.warning("Claude tool loop exhausted iterations without end_turn reply text")

        reply = (reply or "").strip()
        if not reply:
            retry_text = await _anthropic_plain_retry_reply(
                client,
                model=model_name,
                max_tokens=max_tokens,
                system=system,
                anthropic_messages=anthropic_messages,
            )
            reply = (retry_text or "").strip()
            if reply:
                logger.info("Claude plain retry produced reply len={}", len(reply))
        if not reply:
            reply = _fallback_visible_reply(messages)

        # Infer emotion from reply for avatar
        emotion = _infer_emotion(reply)

        return {
            "reply": reply,
            "intent": "greeting_chitchat",  # Claude handles routing internally
            "emotion": emotion,
            "avatar_action": _emotion_to_action(emotion),
        }

    except Exception as e:
        logger.error("Claude agent failed: {}", e)
        # Fallback
        from services.agent_service.llm.client import generate_with_history
        system = _build_system(agent_id, memories)
        reply = await generate_with_history(system, messages)
        reply = (reply or "").strip() or _fallback_visible_reply(messages)
        return {
            "reply": reply,
            "intent": "greeting_chitchat",
            "emotion": "neutral",
            "avatar_action": "idle_typing",
        }


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
