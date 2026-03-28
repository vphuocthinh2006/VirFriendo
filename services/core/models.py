from sqlalchemy import String, Integer, DateTime, func, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import List, Optional
import uuid
from sqlalchemy.dialects.postgresql import UUID

from services.core.database import Base

# 1. Model cho Người dùng (User)
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    relationship_level: Mapped[int] = mapped_column(Integer, default=1)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Quan hệ (Relationship): Một user có nhiều cuộc hội thoại
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="user", cascade="all, delete-orphan")

# 2. Model cho Cuộc hội thoại (Conversation)
class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")

# 3. Model cho Tin nhắn (Message)
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False) # 'user' hoặc 'assistant'
    content: Mapped[str] = mapped_column(nullable=False)
    detected_intent: Mapped[Optional[str]] = mapped_column(String(50))
    detected_emotion: Mapped[Optional[str]] = mapped_column(String(50))
    avatar_action: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# 4. Model cho User Memory (facts/preferences/goals...)
class AgentStat(Base):
    """Aggregated play opens per agent (likes counted via user_agent_likes)."""

    __tablename__ = "agent_stats"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plays: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class UserAgentLike(Base):
    __tablename__ = "user_agent_likes"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserMemory(Base):
    __tablename__ = "user_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="fact")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=datetime.utcnow)


class DiaryEntry(Base):
    """User-written diary lines per companion (for team review)."""

    __tablename__ = "diary_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserAgentRelationship(Base):
    """Per-companion stats: user message count drives relationship level (1000 msgs / level)."""

    __tablename__ = "user_agent_relationships"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_fun_fact_level_ack: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
