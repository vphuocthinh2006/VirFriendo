# services/agent_service/llm/client.py
"""LLM client: OpenAI (GPT-4o) hoặc Groq. Dùng cho các agent generate reply."""
import os
from typing import Optional, Sequence

from langchain_core.messages import BaseMessage, SystemMessage
from loguru import logger

_llm = None


def _get_llm():
    global _llm
    if _llm is not None:
        return _llm
    groq_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    # Ưu tiên Groq trước (nhanh, .env thường dùng GROQ_API_KEY)
    if groq_key:
        try:
            from langchain_groq import ChatGroq
            _llm = ChatGroq(
                model=os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant"),
                temperature=0.7,
                api_key=groq_key,
            )
            logger.info("LLM client: using Groq")
            return _llm
        except ImportError:
            logger.warning("langchain-groq not installed")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            _llm = ChatOpenAI(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
                temperature=0.7,
                api_key=openai_key,
            )
            logger.info("LLM client: using OpenAI")
            return _llm
        except ImportError:
            logger.warning("langchain-openai not installed")
    return None


async def generate(system_prompt: str, user_message: str) -> Optional[str]:
    """
    Gọi LLM với system + user message. Trả về nội dung reply hoặc None nếu lỗi/không cấu hình.
    """
    llm = _get_llm()
    if llm is None:
        return None
    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]
        if hasattr(llm, "ainvoke"):
            response = await llm.ainvoke(messages)
        else:
            response = llm.invoke(messages)
        if response and hasattr(response, "content"):
            text = (response.content or "").strip()
            return text if text else None
        return None
    except Exception as e:
        logger.warning("LLM generate failed: {}", e)
        return None


# Số tin nhắn tối đa gửi vào LLM (context window) — trùng với core/context
MAX_HISTORY_MESSAGES = 21  # ~10 cặp user/assistant + 1 tin mới


async def generate_with_history(
    system_prompt: str,
    messages: Sequence[BaseMessage],
) -> Optional[str]:
    """
    Gọi LLM với system + toàn bộ đoạn hội thoại gần nhất (để bot nhớ mạch, reply liền như Character.AI).
    messages: list HumanMessage/AIMessage (đã gồm tin mới nhất của user).
    Chỉ lấy last MAX_HISTORY_MESSAGES để tránh tràn context.
    """
    llm = _get_llm()
    if llm is None:
        return None
    slice_msgs = list(messages)[-MAX_HISTORY_MESSAGES:] if len(messages) > MAX_HISTORY_MESSAGES else list(messages)
    if not slice_msgs:
        return None
    try:
        full = [SystemMessage(content=system_prompt)] + slice_msgs
        if hasattr(llm, "ainvoke"):
            response = await llm.ainvoke(full)
        else:
            response = llm.invoke(full)
        if response and hasattr(response, "content"):
            text = (response.content or "").strip()
            return text if text else None
        return None
    except Exception as e:
        logger.warning("LLM generate_with_history failed: {}", e)
        return None
