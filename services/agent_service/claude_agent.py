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
            if block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        else:
            btype = getattr(block, "type", None)
            if btype == "text":
                parts.append(str(getattr(block, "text", "") or ""))
            elif hasattr(block, "text"):
                txt = getattr(block, "text", None)
                if txt:
                    parts.append(str(txt))
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
        return {
            "reply": reply or "Mình đang lắng nghe nè~",
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
            return {
                "reply": "Mình đang lắng nghe nè~",
                "intent": "greeting_chitchat",
                "emotion": "neutral",
                "avatar_action": "idle_typing",
            }

        # Agentic loop: Claude may call tools
        max_iterations = 3
        max_tokens = int(os.environ.get("ANTHROPIC_MAX_TOKENS", "2048"))
        reply = ""
        for iteration in range(max_iterations):
            response = await client.messages.create(
                model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
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
            reply = reply or "Mình đang xử lý, bạn thử lại nhé~"

        reply = (reply or "").strip()
        if not reply:
            reply = "Mình đang lắng nghe nè~"

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
        return {
            "reply": reply or "Mình đang lắng nghe nè~",
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
