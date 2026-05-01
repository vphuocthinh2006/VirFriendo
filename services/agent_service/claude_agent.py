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
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not anthropic_key:
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
                system = msg.content + "\n\n" + system
            elif isinstance(msg, HumanMessage):
                anthropic_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                anthropic_messages.append({"role": "assistant", "content": msg.content})

        if not anthropic_messages:
            return {
                "reply": "Mình đang lắng nghe nè~",
                "intent": "greeting_chitchat",
                "emotion": "neutral",
                "avatar_action": "idle_typing",
            }

        # Agentic loop: Claude may call tools
        max_iterations = 3
        for iteration in range(max_iterations):
            response = await client.messages.create(
                model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=1024,
                system=system,
                messages=anthropic_messages,
                tools=TOOLS,
                temperature=0.7,
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Extract text reply
                reply = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        reply += block.text
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
            else:
                # Unexpected stop reason
                reply = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        reply += block.text
                break
        else:
            reply = "Mình đang xử lý, bạn thử lại nhé~"

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
