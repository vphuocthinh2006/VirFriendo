# services/core/context.py
"""Conversation context: load last N messages từ DB cho continuity (Character.AI style)."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.core.models import Message

# Số tin nhắn tối đa gửi vào context (tránh tràn context window)
MAX_CONTEXT_MESSAGES = 20


async def get_conversation_context(
    conversation_id: UUID,
    db: AsyncSession,
    max_messages: int = MAX_CONTEXT_MESSAGES,
) -> list[dict]:
    """
    Lấy danh sách tin nhắn gần nhất của conversation từ DB.
    Mỗi phần tử: {"role": "user" | "assistant", "content": str}.
    """
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(query)
    all_rows = result.scalars().all()
    rows = all_rows[-max_messages:] if len(all_rows) > max_messages else all_rows
    return [{"role": m.role, "content": m.content or ""} for m in rows]
