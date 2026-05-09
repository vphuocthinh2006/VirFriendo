# services/agent_service/llm/client.py
"""LLM client: Claude (Anthropic) / OpenAI / Groq. Dùng cho các agent generate reply."""
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
    anthropic_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    provider = (os.environ.get("LLM_PROVIDER") or "auto").strip().lower()
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))

    def _build_claude():
        if not anthropic_key:
            return None
        try:
            from langchain_anthropic import ChatAnthropic
            model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
            llm = ChatAnthropic(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=anthropic_key,
            )
            logger.info("LLM client: using claude ({})", model)
            return llm
        except ImportError:
            logger.warning("langchain-anthropic not installed")
            return None

    def _build_openai():
        if not openai_key:
            return None
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=openai_key,
            )
        except ImportError:
            logger.warning("langchain-openai not installed")
            return None

    def _build_groq():
        if not groq_key:
            return None
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=groq_key,
            )
        except ImportError:
            logger.warning("langchain-groq not installed")
            return None

    # Priority order based on LLM_PROVIDER
    if provider == "claude":
        _llm = _build_claude() or _build_groq() or _build_openai()
    elif provider == "openai":
        _llm = _build_openai() or _build_claude() or _build_groq()
    elif provider == "groq":
        _llm = _build_groq() or _build_claude() or _build_openai()
    else:
        # auto: claude > groq > openai
        _llm = _build_claude() or _build_groq() or _build_openai()

    if _llm is None:
        logger.warning("LLM client: no provider available")
    return _llm


_active_model_name: str = "unknown"


def get_active_model_info() -> dict:
    """Return info about which LLM is currently active."""
    global _active_model_name
    llm = _get_llm()
    if llm is None:
        return {"provider": "none", "model": "none"}
    
    # Detect provider from class name
    cls = type(llm).__name__
    if "Groq" in cls:
        provider = "groq"
        model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    elif "Anthropic" in cls:
        provider = "anthropic"
        model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    elif "OpenAI" in cls:
        provider = "openai"
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    else:
        provider = cls.lower()
        model = "unknown"
    
    return {"provider": provider, "model": model}


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


# Số tin nhắn tối đa gửi vào LLM (context window) — trùng với core/context.
# Lowered 20 → 12: faster generation, less compute, still keeps recent context.
MAX_HISTORY_MESSAGES = int(os.environ.get("LLM_MAX_HISTORY", "12"))


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
