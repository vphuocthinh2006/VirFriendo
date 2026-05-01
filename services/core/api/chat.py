from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from uuid import UUID
from datetime import datetime
import asyncio
import json
import re
import base64
import os
from typing import Any, Mapping
from pathlib import Path

from services.core.database import get_db, AsyncSessionLocal
from services.core.models import Conversation, Message, UserMemory, UserAgentRelationship
from services.core.security import get_current_user_id
from services.core.config import settings
from pydantic import BaseModel
from pydantic import ConfigDict
from jose import jwt
from loguru import logger

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from services.agent_service.claude_agent import run_claude_agent
from services.core.context import get_conversation_context, MAX_CONTEXT_MESSAGES
from services.agent_service.llm.memory import extract_user_memories
from services.core.quickstart_personality import (
    append_user_line_and_maybe_summarize,
    get_quickstart_summary,
)

router = APIRouter(prefix="/chat", tags=["Chat"])

_DEFAULT_AGENT_ID = "tuq27"


def _session_agent_id(session: dict | None) -> str:
    return ((session or {}).get("agent_id") or "").strip() or _DEFAULT_AGENT_ID


def _client_ip(request: Request) -> str:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _sanitize_agent_handle_typo(text: str, agent_id: str) -> str:
    """Fix common LLM typos like tuq26 when canonical id is tuq27."""
    if not text or not agent_id:
        return text
    aid = agent_id.strip()
    m = re.fullmatch(r"tuq(\d+)", aid.lower())
    if not m:
        return text
    n = int(m.group(1))
    for wrong in (n - 1, n + 1):
        text = re.sub(rf"\btuq{wrong}\b", aid, text, flags=re.IGNORECASE)
    return text


def _extract_assistant_content(msg: Any) -> str:
    """LangChain may return str or list of content blocks."""
    c = getattr(msg, "content", None)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts: list[str] = []
        for block in c:
            if isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(c or "")


_FALLBACK_EMPTY_REPLY = (
    "Mình chưa tạo được câu trả lời (lỗi model hoặc mạng). Bạn gửi lại giúp mình một lần nữa nhé~"
)


def _ensure_assistant_reply(text: str) -> str:
    t = (text or "").strip()
    return t if t else _FALLBACK_EMPTY_REPLY


# Schema nhận tin nhắn
class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None  # None = tạo conversation mới
    agent_id: str | None = None
    entry_mode: str | None = None  # quickstart | character
    persona: str | None = None
    character_name: str | None = None
    gender: str | None = None

# Schema trả về
class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    detected_intent: str | None = None
    detected_emotion: str | None = None
    avatar_action: str | None = None
    bibliotherapy_suggestion: str | None = None
    user_message_count: int | None = None
    relationship_level: int | None = None
    relationship_level_up: bool = False
    new_relationship_level: int | None = None


async def _bump_user_agent_relationship(
    db: AsyncSession,
    user_uuid: UUID,
    agent_id: str | None,
) -> dict[str, Any]:
    """Count user messages per agent; level = user_message_count // 1000 + 1."""
    if not agent_id or not str(agent_id).strip():
        return {}
    aid = str(agent_id).strip()
    q = await db.execute(
        select(UserAgentRelationship).where(
            UserAgentRelationship.user_id == user_uuid,
            UserAgentRelationship.agent_id == aid,
        )
    )
    row = q.scalar_one_or_none()
    old_count = row.user_message_count if row else 0
    old_level = old_count // 1000 + 1
    if row:
        row.user_message_count += 1
        new_count = row.user_message_count
    else:
        row = UserAgentRelationship(
            user_id=user_uuid,
            agent_id=aid,
            user_message_count=1,
            last_fun_fact_level_ack=0,
        )
        db.add(row)
        new_count = 1
    new_level = new_count // 1000 + 1
    level_up = new_level > old_level
    await db.flush()
    return {
        "user_message_count": new_count,
        "relationship_level": new_level,
        "relationship_level_up": level_up,
        "new_relationship_level": new_level,
    }


def _relationship_payload(rel: Mapping[str, Any] | None) -> dict[str, Any]:
    if not rel:
        return {}
    return {
        "user_message_count": rel.get("user_message_count"),
        "relationship_level": rel.get("relationship_level"),
        "relationship_level_up": bool(rel.get("relationship_level_up")),
        "new_relationship_level": rel.get("new_relationship_level"),
    }


def _conversation_title_from_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "Hội thoại mới"
    return (raw[:80] + "…") if len(raw) > 80 else raw


async def _get_or_create_conversation(
    db: AsyncSession, user_uuid: UUID, message: str, conversation_id: str | None
) -> Conversation:
    if conversation_id:
        try:
            conv_id = UUID(conversation_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
        query = select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_uuid)
        result = await db.execute(query)
        conversation = result.scalars().first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
        return conversation

    conversation = Conversation(user_id=user_uuid, title=_conversation_title_from_text(message))
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


def _session_dict_from_request(req: ChatRequest) -> dict:
    return {
        "entry_mode": (req.entry_mode or "").strip().lower(),
        "agent_id": (req.agent_id or "").strip(),
        "persona": (req.persona or "").strip(),
        "character_name": (req.character_name or "").strip(),
        "gender": (req.gender or "").strip(),
    }


def _session_dict_from_ws(data: dict) -> dict:
    return {
        "entry_mode": (data.get("entry_mode") or "").strip().lower(),
        "agent_id": (data.get("agent_id") or "").strip(),
        "persona": (data.get("persona") or "").strip(),
        "character_name": (data.get("character_name") or "").strip(),
        "gender": (data.get("gender") or "").strip(),
    }


async def _build_lc_messages(
    db: AsyncSession,
    conversation_id: UUID,
    user_uuid: UUID,
    fallback_user_text: str,
    session: dict | None = None,
):
    session = session or {}
    history = await get_conversation_context(conversation_id, db, max_messages=MAX_CONTEXT_MESSAGES)
    lc_messages = []
    for h in history:
        if h.get("role") == "assistant":
            lc_messages.append(AIMessage(content=h.get("content") or ""))
        else:
            lc_messages.append(HumanMessage(content=h.get("content") or ""))
    if not lc_messages:
        lc_messages = [HumanMessage(content=fallback_user_text)]

    prefix_blocks: list[str] = []
    em = (session.get("entry_mode") or "").strip().lower()
    agent_id = (session.get("agent_id") or "").strip()

    aid = _session_agent_id(session)
    prefix_blocks.append(
        f"[Identity — bắt buộc]\n"
        f'- Tên nhân vật assistant là CHÍNH XÁC "{aid}" (giữ nguyên chữ và số).\n'
        f"- KHÔNG ký tên sai (ví dụ tuq26, tuq28) và không đổi chữ số.\n"
    )

    if em == "character" and (session.get("persona") or "").strip():
        name = (session.get("character_name") or "User").strip()
        gender = (session.get("gender") or "").strip()
        persona = (session.get("persona") or "").strip()
        prefix_blocks.append(
            f"The user is roleplaying as their character named {name}."
            + (f" Stated gender: {gender}." if gender else "")
            + f"\nPersona / background:\n{persona}\n"
            "Honor this persona in tone, word choice, and how you treat them."
        )
    elif em == "quickstart" and agent_id:
        summary = await get_quickstart_summary(str(user_uuid), agent_id)
        if summary:
            prefix_blocks.append(
                "Inferred user traits from past messages (use subtly; do not quote verbatim):\n"
                + summary
            )

    mem_result = await db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_uuid, UserMemory.is_active == True)  # noqa: E712
        .order_by(UserMemory.updated_at.desc(), UserMemory.created_at.desc())
        .limit(20)
    )
    memories = mem_result.scalars().all()
    if memories:
        bullets = "\n".join([f"- ({m.type}) {m.content}" for m in memories if m.content])
        memory_block = (
            "Thông tin đã biết về bạn (dùng để trả lời tự nhiên hơn, không cần nhắc lại y nguyên):\n"
            + bullets
        )
        prefix_blocks.append(memory_block)

    if prefix_blocks:
        combined = "\n\n---\n\n".join(prefix_blocks)
        lc_messages = [SystemMessage(content=combined)] + lc_messages
    return lc_messages


async def _extract_and_store_user_memories(
    db: AsyncSession,
    *,
    lc_messages: list[Any],
    user_uuid: UUID,
    source_message_id: UUID,
) -> None:
    try:
        extract_window = [m for m in lc_messages if not isinstance(m, SystemMessage)][-12:]
        extracted = await extract_user_memories(extract_window)
        for mem in extracted:
            mtype = (mem.get("type") or "fact").strip()[:32]
            mcontent = (mem.get("content") or "").strip()
            if not mcontent:
                continue
            dup_q = await db.execute(
                select(UserMemory.id).where(
                    UserMemory.user_id == user_uuid,
                    UserMemory.is_active == True,  # noqa: E712
                    UserMemory.type == mtype,
                    UserMemory.content == mcontent,
                ).limit(1)
            )
            if dup_q.scalar() is not None:
                continue
            db.add(
                UserMemory(
                    user_id=user_uuid,
                    type=mtype,
                    content=mcontent,
                    source_message_id=source_message_id,
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()


async def _refresh_conversation_title(db: AsyncSession, conversation: Conversation, latest_user_text: str) -> None:
    count_result = await db.execute(select(func.count(Message.id)).where(Message.conversation_id == conversation.id))
    total = count_result.scalar() or 0
    if total > 0 and total % 21 == 0:
        conversation.title = _conversation_title_from_text(latest_user_text)
        await db.commit()

@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user_id),  # Xác thực JWT
    db: AsyncSession = Depends(get_db)
):
    user_uuid = UUID(current_user_id)
    conversation = await _get_or_create_conversation(db, user_uuid, request.message, request.conversation_id)

    user_msg = Message(conversation_id=conversation.id, role="user", content=request.message)
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    session = _session_dict_from_request(request)
    rel = await _bump_user_agent_relationship(db, user_uuid, session.get("agent_id"))
    if rel:
        await db.commit()

    lc_messages = await _build_lc_messages(db, conversation.id, user_uuid, request.message, session)
    aid = _session_agent_id(session)
    result = await run_claude_agent(lc_messages, agent_id=aid)

    bot_reply = _sanitize_agent_handle_typo(result["reply"], aid)
    bot_reply = _ensure_assistant_reply(bot_reply)

    intent = result.get("intent")
    emotion = result.get("emotion")
    avatar_action = result.get("avatar_action")
    bibliotherapy = result.get("bibliotherapy_suggestion")

    # BƯỚC 4: Lưu phản hồi bot vào DB
    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=bot_reply,
        detected_intent=intent,
        detected_emotion=emotion,
        avatar_action=avatar_action,
    )
    db.add(bot_msg)
    await db.commit()
    await db.refresh(bot_msg)

    await _extract_and_store_user_memories(
        db,
        lc_messages=lc_messages,
        user_uuid=user_uuid,
        source_message_id=bot_msg.id,
    )
    await _refresh_conversation_title(db, conversation, request.message)

    if session.get("entry_mode") == "quickstart" and session.get("agent_id"):
        await append_user_line_and_maybe_summarize(str(user_uuid), session["agent_id"], request.message)

    rel_ex = _relationship_payload(rel) if rel else {}
    # BƯỚC 5: Trả về response
    return ChatResponse(
        conversation_id=str(conversation.id),
        reply=bot_reply,
        detected_intent=intent,
        detected_emotion=emotion,
        avatar_action=avatar_action,
        bibliotherapy_suggestion=bibliotherapy,
        user_message_count=rel_ex.get("user_message_count"),
        relationship_level=rel_ex.get("relationship_level"),
        relationship_level_up=bool(rel_ex.get("relationship_level_up")),
        new_relationship_level=rel_ex.get("new_relationship_level"),
    )
# Schema trả về cho 1 conversation
class ConversationSummary(BaseModel):
    id: UUID          # ← đổi từ str sang UUID
    title: str | None
    model_config = ConfigDict(from_attributes=True)


# Schema trả về cho 1 tin nhắn
class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    detected_intent: str | None = None
    detected_emotion: str | None = None
    avatar_action: str | None = None
    model_config = ConfigDict(from_attributes=True)



@router.get("/conversations")
async def get_conversations(
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """Lấy danh sách conversations của user (có pagination)"""
    logger.info("chat.refresh ip={} user_id={}", _client_ip(request), current_user_id)
    user_uuid = UUID(current_user_id)
    limit = max(1, min(limit, 100))  # clamp 1-100
    query = (
        select(Conversation)
        .where(Conversation.user_id == user_uuid)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    conversations = result.scalars().all()
    return [ConversationSummary.model_validate(conv) for conv in conversations]


class UserMemoryOut(BaseModel):
    id: UUID
    type: str
    content: str
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


@router.get("/memories", response_model=list[UserMemoryOut])
async def list_user_memories(
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Tóm tắt / facts đã trích từ hội thoại (Memory tab)."""
    user_uuid = UUID(current_user_id)
    q = (
        select(UserMemory)
        .where(UserMemory.user_id == user_uuid, UserMemory.is_active == True)  # noqa: E712
        .order_by(UserMemory.updated_at.desc(), UserMemory.created_at.desc())
        .limit(200)
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    return [UserMemoryOut.model_validate(m) for m in rows]


@router.get("/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Lấy toàn bộ tin nhắn của 1 conversation"""
    try:
        conv_id = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
    user_uuid = UUID(current_user_id)
    query = select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.user_id == user_uuid,
    )
    result = await db.execute(query)
    conversation = result.scalars().first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")

    query = select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    result = await db.execute(query)
    messages = result.scalars().all()
    
    return [MessageResponse.model_validate(msg) for msg in messages]


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Xóa một conversation (và toàn bộ tin nhắn trong đó). Chỉ owner mới xóa được."""
    try:
        conv_id = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
    user_uuid = UUID(current_user_id)
    query = select(Conversation).where(
        Conversation.id == conv_id,
        Conversation.user_id == user_uuid,
    )
    result = await db.execute(query)
    conversation = result.scalars().first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
    await db.delete(conversation)
    await db.commit()


class RelationshipOut(BaseModel):
    user_message_count: int
    relationship_level: int
    last_fun_fact_level_ack: int
    pending_fun_fact: bool


class AckFunFactBody(BaseModel):
    agent_id: str
    level: int


@router.get("/relationship", response_model=RelationshipOut)
async def get_agent_relationship(
    agent_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Per-agent relationship stats (persisted). Level increases by 1 each 1000 user messages."""
    user_uuid = UUID(current_user_id)
    aid = (agent_id or "").strip()
    if not aid:
        raise HTTPException(status_code=400, detail="agent_id required")
    q = await db.execute(
        select(UserAgentRelationship).where(
            UserAgentRelationship.user_id == user_uuid,
            UserAgentRelationship.agent_id == aid,
        )
    )
    row = q.scalar_one_or_none()
    if not row:
        return RelationshipOut(
            user_message_count=0,
            relationship_level=1,
            last_fun_fact_level_ack=0,
            pending_fun_fact=False,
        )
    count = row.user_message_count
    level = count // 1000 + 1
    ack = row.last_fun_fact_level_ack
    pending = level > ack and level >= 2
    return RelationshipOut(
        user_message_count=count,
        relationship_level=level,
        last_fun_fact_level_ack=ack,
        pending_fun_fact=pending,
    )


@router.post("/relationship/ack-fun-fact")
async def ack_fun_fact(
    body: AckFunFactBody,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Mark fun-fact modal seen for this relationship level (stored in DB)."""
    user_uuid = UUID(current_user_id)
    aid = (body.agent_id or "").strip()
    if not aid:
        raise HTTPException(status_code=400, detail="agent_id required")
    q = await db.execute(
        select(UserAgentRelationship).where(
            UserAgentRelationship.user_id == user_uuid,
            UserAgentRelationship.agent_id == aid,
        )
    )
    row = q.scalar_one_or_none()
    if row:
        row.last_fun_fact_level_ack = max(row.last_fun_fact_level_ack, body.level)
    else:
        db.add(
            UserAgentRelationship(
                user_id=user_uuid,
                agent_id=aid,
                user_message_count=0,
                last_fun_fact_level_ack=body.level,
            )
        )
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# TEST ENDPOINT - Voice & Vision Features
# ---------------------------------------------------------------------------

@router.get("/test-voice-vision")
async def test_voice_vision_endpoint():
    """Test endpoint to verify voice and vision features are loaded."""
    return {
        "status": "ok",
        "message": "Voice and vision endpoints are loaded!",
        "endpoints": ["/chat/transcribe", "/chat/analyze-media"]
    }


# ---------------------------------------------------------------------------
# WebSocket streaming: /chat/ws
# ---------------------------------------------------------------------------

def _verify_ws_token(token: str) -> str | None:
    """Decode JWT and return user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None


STREAM_CHUNK_WORDS = 5
STREAM_DELAY_S = 0.08


@router.websocket("/ws")
async def websocket_chat(ws: WebSocket):
    """
    WebSocket endpoint for streaming chat.

    Protocol
    --------
    Client → Server  (JSON):
        {"type": "message", "content": "...", "conversation_id": "..." | null}

    Server → Client  (JSON):
        {"type": "stream_start", "conversation_id": "..."}
        {"type": "token",        "content": "..."}
        {"type": "stream_end",   "detected_intent": ..., "detected_emotion": ..., "avatar_action": ...}
        {"type": "error",        "detail": "..."}
    """
    # --- Auth via query param ---
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return
    user_id = _verify_ws_token(token)
    if not user_id:
        await ws.close(code=4001, reason="Invalid token")
        return

    await ws.accept()
    user_uuid = UUID(user_id)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            msg_type = data.get("type")
            if msg_type != "message":
                await ws.send_json({"type": "error", "detail": f"Unknown type: {msg_type}"})
                continue

            content = (data.get("content") or "").strip()
            if not content:
                await ws.send_json({"type": "error", "detail": "Empty message"})
                continue

            conv_id_str = data.get("conversation_id")
            session = _session_dict_from_ws(data)

            # --- Process in a fresh DB session ---
            async with AsyncSessionLocal() as db:
                try:
                    result = await _process_ws_message(
                        db, ws, user_uuid, content, conv_id_str, session
                    )
                except Exception as e:
                    logger.error("WS processing error: {}", e)
                    await ws.send_json({"type": "error", "detail": str(e)})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WS closed: {}", e)


async def _process_ws_message(
    db: AsyncSession,
    ws: WebSocket,
    user_uuid: UUID,
    content: str,
    conv_id_str: str | None,
    session: dict | None = None,
):
    """Handle one user message: save, invoke LangGraph, stream reply back."""
    session = session or {}

    # 1) Get or create conversation
    try:
        conversation = await _get_or_create_conversation(db, user_uuid, content, conv_id_str)
    except HTTPException:
        await ws.send_json({"type": "error", "detail": "Conversation not found"})
        return

    # 2) Save user message
    user_msg = Message(conversation_id=conversation.id, role="user", content=content)
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    rel = await _bump_user_agent_relationship(db, user_uuid, session.get("agent_id"))
    if rel:
        await db.commit()

    # 3) Build LangChain messages (same as POST /chat)
    lc_messages = await _build_lc_messages(db, conversation.id, user_uuid, content, session)

    # 4) Invoke Claude agent
    aid = _session_agent_id(session)
    result = await run_claude_agent(lc_messages, agent_id=aid)

    bot_reply = _sanitize_agent_handle_typo(result["reply"], aid)
    bot_reply = _ensure_assistant_reply(bot_reply)
    intent = result.get("intent")
    emotion = result.get("emotion")
    avatar_action = result.get("avatar_action")

    # 5) Save bot message
    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=bot_reply,
        detected_intent=intent,
        detected_emotion=emotion,
        avatar_action=avatar_action,
    )
    db.add(bot_msg)
    await db.commit()
    await db.refresh(bot_msg)

    # 6) Stream reply word-by-word (whitespace-only replies yield split() == [] — send whole text)
    await ws.send_json({"type": "stream_start", "conversation_id": str(conversation.id)})

    words = bot_reply.split()
    if not words:
        if bot_reply:
            await ws.send_json({"type": "token", "content": bot_reply})
    else:
        buf = []
        for w in words:
            buf.append(w)
            if len(buf) >= STREAM_CHUNK_WORDS:
                await ws.send_json({"type": "token", "content": " ".join(buf) + " "})
                buf = []
                await asyncio.sleep(STREAM_DELAY_S)
        if buf:
            await ws.send_json({"type": "token", "content": " ".join(buf)})

    end_payload: dict[str, Any] = {
        "type": "stream_end",
        "detected_intent": intent,
        "detected_emotion": emotion,
        "avatar_action": avatar_action,
    }
    end_payload.update(_relationship_payload(rel) if rel else {})
    await ws.send_json(end_payload)

    await _extract_and_store_user_memories(
        db,
        lc_messages=lc_messages,
        user_uuid=user_uuid,
        source_message_id=bot_msg.id,
    )
    await _refresh_conversation_title(db, conversation, content)

    if session.get("entry_mode") == "quickstart" and session.get("agent_id"):
        await append_user_line_and_maybe_summarize(str(user_uuid), session["agent_id"], content)


# ---------------------------------------------------------------------------
# Voice Transcription (Speech-to-Text) - Groq Whisper
# ---------------------------------------------------------------------------

class TranscribeResponse(BaseModel):
    text: str
    language: str | None = None


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    Transcribe audio to text using Deepgram Nova-3 (primary) → Groq Whisper (fallback).
    Supports: mp3, mp4, mpeg, mpga, m4a, wav, webm
    Max file size: 25MB
    """
    logger.info(f"[TRANSCRIBE] Request from user {current_user_id}")
    logger.info(f"[TRANSCRIBE] Filename: {file.filename}, Content-Type: {file.content_type}")

    allowed_extensions = [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"]
    file_ext = Path(file.filename or "").suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")

    content = await file.read()
    logger.info(f"[TRANSCRIBE] File size: {len(content)/1024:.2f} KB")

    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max size: 25MB")

    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()

    # --- Primary: Deepgram Nova-3 (fast, accurate, multilingual) ---
    if deepgram_key:
        try:
            logger.info("[TRANSCRIBE] Attempting Deepgram Nova-3...")
            from deepgram import DeepgramClient, PrerecordedOptions
            dg = DeepgramClient(deepgram_key)
            options = PrerecordedOptions(
                model="nova-3",
                language="vi",
                smart_format=True,
                punctuate=True,
            )
            mime = file.content_type or "audio/webm"
            payload = {"buffer": content, "mimetype": mime}
            response = dg.listen.rest.v("1").transcribe_file(payload, options)
            result_text = response.results.channels[0].alternatives[0].transcript
            logger.info(f"[TRANSCRIBE] ✅ Deepgram SUCCESS: '{result_text[:100]}'")
            return TranscribeResponse(text=result_text, language="vi")
        except ImportError:
            logger.warning("[TRANSCRIBE] deepgram-sdk not installed, falling back to Groq")
        except Exception as e:
            logger.error(f"[TRANSCRIBE] Deepgram failed: {e}, falling back to Groq")

    # --- Fallback: Groq Whisper ---
    if groq_key:
        try:
            logger.info("[TRANSCRIBE] Attempting Groq Whisper fallback...")
            from groq import Groq
            from io import BytesIO
            client = Groq(api_key=groq_key)
            audio_file = BytesIO(content)
            audio_file.name = file.filename or "audio.webm"
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                language="vi",
                response_format="json"
            )
            result_text = transcription.text
            logger.info(f"[TRANSCRIBE] ✅ Groq fallback SUCCESS: '{result_text[:100]}'")
            return TranscribeResponse(text=result_text, language="vi")
        except Exception as e:
            logger.error(f"[TRANSCRIBE] Groq fallback failed: {e}")
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

    raise HTTPException(status_code=500, detail="No transcription service available. Set DEEPGRAM_API_KEY or GROQ_API_KEY")
    
    logger.error("[TRANSCRIBE] No transcription service available")
    raise HTTPException(
        status_code=500,
        detail="No transcription service available. Set GROQ_API_KEY or OPENAI_API_KEY"
    )


# ---------------------------------------------------------------------------
# Image/Video Analysis - Vision Models
# ---------------------------------------------------------------------------

class MediaAnalysisResponse(BaseModel):
    conversation_id: str
    reply: str
    detected_intent: str | None = None
    detected_emotion: str | None = None
    avatar_action: str | None = None
    user_message_count: int | None = None
    relationship_level: int | None = None
    relationship_level_up: bool = False
    new_relationship_level: int | None = None


@router.post("/analyze-media", response_model=MediaAnalysisResponse)
async def analyze_media(
    file: UploadFile = File(...),
    message: str = Form(""),
    conversation_id: str | None = Form(None),
    agent_id: str | None = Form(None),
    entry_mode: str | None = Form(None),
    persona: str | None = Form(None),
    character_name: str | None = Form(None),
    gender: str | None = Form(None),
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze image/video/YouTube URL using vision models and web scraping.
    Supports: 
    - Images: jpg, jpeg, png, gif, webp (max 20MB)
    - Videos: mp4, mov, avi, webm (max 50MB) 
    - YouTube URLs in message field
    - Web URLs in message field
    """
    logger.info(f"analyze_media called: file={file.filename}, message={message[:100] if message else 'empty'}")
    
    # Check if message contains YouTube URL
    youtube_pattern = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
    youtube_match = re.search(youtube_pattern, message) if message else None
    
    # Check if message contains web URL
    url_pattern = r'https?://[^\s]+'
    url_match = re.search(url_pattern, message) if message else None
    
    # If YouTube URL detected
    if youtube_match:
        logger.info(f"YouTube URL detected: {youtube_match.group(0)}")
        return await _analyze_youtube(
            youtube_match.group(0), message, conversation_id, 
            agent_id, entry_mode, persona, character_name, gender,
            current_user_id, db
        )
    
    # If web URL detected (not YouTube)
    if url_match and not youtube_match:
        logger.info(f"Web URL detected: {url_match.group(0)}")
        return await _analyze_web_url(
            url_match.group(0), message, conversation_id,
            agent_id, entry_mode, persona, character_name, gender,
            current_user_id, db
        )
    
    # Validate file type for images/videos
    allowed_image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    allowed_video_extensions = [".mp4", ".mov", ".avi", ".webm"]
    allowed_extensions = allowed_image_extensions + allowed_video_extensions
    
    file_ext = Path(file.filename or "").suffix.lower()
    logger.info(f"File extension: {file_ext}")
    
    if file_ext not in allowed_extensions:
        logger.error(f"Unsupported file type: {file_ext}")
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Read and encode image/video
    content = await file.read()
    logger.info(f"File size: {len(content)} bytes")
    
    # Check file size
    is_video = file_ext in [".mp4", ".mov", ".avi", ".webm"]
    max_size = 50 * 1024 * 1024 if is_video else 20 * 1024 * 1024
    
    if len(content) > max_size:
        max_mb = 50 if is_video else 20
        logger.error(f"File too large: {len(content)} bytes > {max_size} bytes")
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {max_mb}MB")
    
    base64_content = base64.b64encode(content).decode('utf-8')
    
    # Determine MIME type
    mime_type = "image/jpeg"
    if file_ext in [".png"]:
        mime_type = "image/png"
    elif file_ext in [".gif"]:
        mime_type = "image/gif"
    elif file_ext in [".webp"]:
        mime_type = "image/webp"
    elif file_ext in [".mp4"]:
        mime_type = "video/mp4"
    elif file_ext in [".mov"]:
        mime_type = "video/quicktime"
    elif file_ext in [".avi"]:
        mime_type = "video/x-msvideo"
    elif file_ext in [".webm"]:
        mime_type = "video/webm"
    
    logger.info(f"MIME type: {mime_type}")

    # Build session/persona context
    user_uuid = UUID(current_user_id)
    session = {
        "entry_mode": (entry_mode or "").strip().lower(),
        "agent_id": (agent_id or "").strip(),
        "persona": (persona or "").strip(),
        "character_name": (character_name or "").strip(),
        "gender": (gender or "").strip(),
    }
    aid = _session_agent_id(session)
    vision_prompt = message or ("Bạn thấy gì trong video này?" if is_video else "Bạn thấy gì trong ảnh này?")

    # Get vision analysis - Gemini 1.5 Pro (primary) → GPT-4o (fallback)
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if not gemini_key and not openai_key:
        raise HTTPException(status_code=500, detail="Vision analysis requires GEMINI_API_KEY or OPENAI_API_KEY")

    vision_system = f"""Bạn là {aid}, một cô gái anime thân thiện. Xưng "mình", gọi đối phương "bạn".

NHIỆM VỤ: Phân tích {'video' if is_video else 'ảnh'} và trả lời bằng tiếng Việt.

QUAN TRỌNG về nhận diện:
- Nếu thấy NHÂN VẬT từ phim/show/game/manga/anime quen thuộc, hãy ĐOÁN MẠNH DẠN tên + nguồn — đừng từ chối hay nói "không thể xác định". Đoán dựa trên đặc điểm: kiểu tóc, trang phục, biểu tượng (vd. mặt cười đỏ → Red John từ The Mentalist; tai mèo + tóc đỏ → có thể là Anya/anime nào đó...).
- Đối với người thật/diễn viên: nếu nhận ra (Simon Baker, Tom Cruise...) cứ tự nhiên đoán theo trí nhớ phổ biến.
- Nếu vẫn không chắc: liệt kê các đặc điểm hình ảnh nổi bật (màu tóc, trang phục, biểu tượng, phong cách nghệ thuật) để có thể tra trên Google.

Trả lời CHI TIẾT bao gồm:
1. Nhận diện người/nhân vật + nguồn nếu có
2. Vật thể, hành động, bối cảnh
3. Phong cách nghệ thuật + màu sắc chủ đạo

Trả lời TỰ NHIÊN như chat, KHÔNG bullet points, KHÔNG giọng trợ lý AI.

CUỐI câu trả lời, BẮT BUỘC thêm 2 dòng RIÊNG BIỆT theo format CHÍNH XÁC:
SEARCH_QUERY: <2-6 từ tiếng Anh để tra Google. Ưu tiên: "<tên nhân vật> <nguồn>" (vd "Patrick Jane The Mentalist", "Naruto Uzumaki anime"). Nếu không đoán được nhân vật, vẫn PHẢI cho query mô tả: "<đặc điểm chính> <phong cách>" (vd "blonde curly hair man red smiley face fanart", "anime girl pink hair school uniform"). KHÔNG BAO GIỜ để NONE.>
SUBJECT_TAG: <tên nhân vật + nguồn ngắn gọn nếu nhận diện, ví dụ "Patrick Jane (The Mentalist)". Nếu không, để "ảnh chung">"""

    raw_vision = ""

    # --- Primary: Gemini 1.5 Pro Vision ---
    if gemini_key:
        try:
            logger.info("[VISION] Attempting Gemini 1.5 Pro...")
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-pro",
                system_instruction=vision_system,
            )
            import PIL.Image
            from io import BytesIO
            img = PIL.Image.open(BytesIO(content))
            response = model.generate_content(
                [vision_prompt, img],
                generation_config={"max_output_tokens": 900, "temperature": 0.7},
            )
            raw_vision = response.text or ""
            logger.info(f"[VISION] ✅ Gemini SUCCESS: {raw_vision[:80]}")
        except ImportError:
            logger.warning("[VISION] google-generativeai not installed, falling back to GPT-4o")
        except Exception as e:
            logger.error(f"[VISION] Gemini failed: {e}, falling back to GPT-4o")

    # --- Fallback: GPT-4o ---
    if not raw_vision and openai_key:
        try:
            logger.info("[VISION] Attempting GPT-4o fallback...")
            from openai import OpenAI
            oai = OpenAI(api_key=openai_key)
            response = oai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": vision_system},
                    {"role": "user", "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_content}", "detail": "high"}},
                    ]},
                ],
                max_tokens=900,
                temperature=0.7,
            )
            raw_vision = response.choices[0].message.content or ""
            logger.info(f"[VISION] ✅ GPT-4o fallback SUCCESS")
        except Exception as e:
            logger.error(f"[VISION] GPT-4o fallback failed: {e}")
            raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")

    if not raw_vision:
        raise HTTPException(status_code=500, detail="Vision analysis failed: no response from any provider")

    # Extract SEARCH_QUERY + SUBJECT_TAG, strip them from user-facing reply
    search_query: str = ""
    subject_tag: str = ""
    cleaned_lines: list[str] = []
    for line in raw_vision.splitlines():
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("SEARCH_QUERY:"):
            q = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if q and q.upper() != "NONE":
                search_query = q
            continue
        if up.startswith("SUBJECT_TAG:"):
            t = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if t and t.lower() not in ("none", "ảnh chung"):
                subject_tag = t
            continue
        cleaned_lines.append(line)
    vision_reply = "\n".join(cleaned_lines).strip()

    logger.info(f"Vision pass done. search_query={search_query!r} subject_tag={subject_tag!r}")

    # PASS 2: reverse-image-search via Tavily on the extracted subject
    if search_query and not is_video:
        try:
            from services.agent_service.llm.web_search import tavily_search
            hits = await tavily_search(search_query, max_results=4)
            logger.info(f"Tavily hits for {search_query!r}: {len(hits)}")
            if hits:
                sources_text = "\n".join(
                    f"- {h.get('title','')}: {h.get('snippet','')[:240]} ({h.get('url','')})"
                    for h in hits if h.get('snippet') or h.get('title')
                )
                if sources_text.strip():
                    from services.agent_service.llm.client import generate
                    enrich_system = (
                        f"Bạn là {aid}, cô gái anime thân thiện. Xưng 'mình', gọi đối phương 'bạn'. "
                        "Hãy MỞ RỘNG câu trả lời gốc bằng thông tin từ web (chỉ dùng nếu liên quan): "
                        "thêm 1-3 câu nói về danh tính nhân vật/chủ thể, nguồn gốc, sự thật thú vị. "
                        "Giữ giọng chat tự nhiên tiếng Việt, KHÔNG bullet, KHÔNG dán link. "
                        "Tránh lặp lại nguyên văn câu trả lời gốc."
                    )
                    enrich_user = (
                        f"CÂU TRẢ LỜI GỐC (phân tích ảnh):\n{vision_reply}\n\n"
                        f"THÔNG TIN TỪ WEB ('{search_query}'):\n{sources_text}\n\n"
                        "Hãy viết lại câu trả lời tự nhiên hơn, nhẹ nhàng đan xen thông tin web vào. "
                        "Phần đầu vẫn giữ là phân tích ảnh, sau đó dẫn dắt vào thông tin tìm được."
                    )
                    enriched = await generate(enrich_system, enrich_user)
                    if enriched and len(enriched.strip()) > 40:
                        vision_reply = enriched.strip()
                        logger.info("Vision reply enriched with web search context.")
        except Exception as e:
            logger.warning(f"Reverse image search enrichment failed: {e}")

    vision_reply = _sanitize_agent_handle_typo(vision_reply, aid)
    vision_reply = _ensure_assistant_reply(vision_reply)
    logger.info(f"Vision analysis successful: {vision_reply[:100]}")
    
    # Save to conversation
    media_type = "video" if is_video else "ảnh"
    conversation = await _get_or_create_conversation(
        db, user_uuid, 
        f"[Đã gửi {media_type}] {message}" if message else f"[Đã gửi {media_type}]",
        conversation_id
    )
    
    # Save user message with media indicator + identified subject (so follow-up turns
    # know what "nó/this" refers to without re-uploading the image).
    media_label = f"[Đã gửi {media_type}: {file.filename}"
    if subject_tag:
        media_label += f" — chủ thể: {subject_tag}"
    media_label += "]"
    user_msg_content = f"{media_label}\n{message}" if message else media_label
    user_msg = Message(conversation_id=conversation.id, role="user", content=user_msg_content)
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)
    
    # Update relationship
    rel = await _bump_user_agent_relationship(db, user_uuid, session.get("agent_id"))
    if rel:
        await db.commit()
    
    # Save bot reply
    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=vision_reply,
        detected_intent="entertainment_knowledge",
        detected_emotion="surprised",
        avatar_action="shocked_face",
    )
    db.add(bot_msg)
    await db.commit()
    await db.refresh(bot_msg)
    
    await _refresh_conversation_title(db, conversation, user_msg_content)
    
    if session.get("entry_mode") == "quickstart" and session.get("agent_id"):
        await append_user_line_and_maybe_summarize(
            str(user_uuid), 
            session["agent_id"], 
            user_msg_content
        )
    
    rel_ex = _relationship_payload(rel) if rel else {}
    
    logger.info(f"analyze_media completed successfully")
    
    return MediaAnalysisResponse(
        conversation_id=str(conversation.id),
        reply=vision_reply,
        detected_intent="entertainment_knowledge",
        detected_emotion="surprised",
        avatar_action="shocked_face",
        user_message_count=rel_ex.get("user_message_count"),
        relationship_level=rel_ex.get("relationship_level"),
        relationship_level_up=bool(rel_ex.get("relationship_level_up")),
        new_relationship_level=rel_ex.get("new_relationship_level"),
    )


# Helper functions for YouTube and Web URL analysis
async def _analyze_youtube(
    youtube_url: str,
    message: str,
    conversation_id: str | None,
    agent_id: str | None,
    entry_mode: str | None,
    persona: str | None,
    character_name: str | None,
    gender: str | None,
    current_user_id: str,
    db: AsyncSession,
) -> MediaAnalysisResponse:
    """Analyze YouTube video using transcript and metadata."""
    logger.info(f"Analyzing YouTube URL: {youtube_url}")
    
    try:
        import httpx
        from youtube_transcript_api import YouTubeTranscriptApi
        
        # Extract video ID
        video_id_match = re.search(r'(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})', youtube_url)
        if not video_id_match:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        video_id = video_id_match.group(1)
        logger.info(f"Video ID: {video_id}")
        
        # Get video metadata
        async with httpx.AsyncClient() as client:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            response = await client.get(oembed_url)
            metadata = response.json() if response.status_code == 200 else {}
        
        video_title = metadata.get("title", "Unknown video")
        video_author = metadata.get("author_name", "Unknown channel")
        
        # Get transcript
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['vi', 'en'])
            transcript_text = " ".join([item['text'] for item in transcript_list[:50]])  # First 50 segments
            transcript_text = transcript_text[:2000]  # Limit to 2000 chars
        except Exception as e:
            logger.warning(f"Could not get transcript: {e}")
            transcript_text = "Không lấy được transcript"
        
        # Build analysis prompt
        user_uuid = UUID(current_user_id)
        session = {
            "entry_mode": (entry_mode or "").strip().lower(),
            "agent_id": (agent_id or "").strip(),
            "persona": (persona or "").strip(),
            "character_name": (character_name or "").strip(),
            "gender": (gender or "").strip(),
        }
        aid = _session_agent_id(session)
        
        user_question = message.replace(youtube_url, "").strip() or "Tóm tắt video này cho mình"
        
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not openai_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY required")
        
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        analysis_prompt = f"""Video: "{video_title}" by {video_author}

Transcript (đoạn đầu):
{transcript_text}

Câu hỏi: {user_question}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""Bạn là {aid}, một cô gái anime thân thiện. Xưng "mình", gọi đối phương "bạn".
Phân tích video YouTube và trả lời bằng tiếng Việt, giọng tự nhiên như chat với bạn.
Không dùng bullet points, không giọng trợ lý AI."""
                },
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=600,
            temperature=0.7
        )
        
        analysis_reply = response.choices[0].message.content or ""
        analysis_reply = _sanitize_agent_handle_typo(analysis_reply, aid)
        analysis_reply = _ensure_assistant_reply(analysis_reply)
        
        # Save to conversation
        conversation = await _get_or_create_conversation(
            db, user_uuid,
            f"[YouTube] {video_title}",
            conversation_id
        )
        
        user_msg_content = f"[YouTube: {video_title}]\n{youtube_url}\n{user_question}"
        user_msg = Message(conversation_id=conversation.id, role="user", content=user_msg_content)
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)
        
        rel = await _bump_user_agent_relationship(db, user_uuid, session.get("agent_id"))
        if rel:
            await db.commit()
        
        bot_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=analysis_reply,
            detected_intent="entertainment_knowledge",
            detected_emotion="surprised",
            avatar_action="shocked_face",
        )
        db.add(bot_msg)
        await db.commit()
        await db.refresh(bot_msg)
        
        await _refresh_conversation_title(db, conversation, user_msg_content)
        
        if session.get("entry_mode") == "quickstart" and session.get("agent_id"):
            await append_user_line_and_maybe_summarize(str(user_uuid), session["agent_id"], user_msg_content)
        
        rel_ex = _relationship_payload(rel) if rel else {}
        
        return MediaAnalysisResponse(
            conversation_id=str(conversation.id),
            reply=analysis_reply,
            detected_intent="entertainment_knowledge",
            detected_emotion="surprised",
            avatar_action="shocked_face",
            user_message_count=rel_ex.get("user_message_count"),
            relationship_level=rel_ex.get("relationship_level"),
            relationship_level_up=bool(rel_ex.get("relationship_level_up")),
            new_relationship_level=rel_ex.get("new_relationship_level"),
        )
        
    except ImportError as e:
        logger.error(f"Missing package: {e}")
        raise HTTPException(status_code=500, detail="youtube-transcript-api package required")
    except Exception as e:
        logger.error(f"YouTube analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"YouTube analysis failed: {str(e)}")


async def _analyze_web_url(
    web_url: str,
    message: str,
    conversation_id: str | None,
    agent_id: str | None,
    entry_mode: str | None,
    persona: str | None,
    character_name: str | None,
    gender: str | None,
    current_user_id: str,
    db: AsyncSession,
) -> MediaAnalysisResponse:
    """Analyze web URL by scraping content."""
    logger.info(f"Analyzing web URL: {web_url}")
    
    try:
        import httpx
        from bs4 import BeautifulSoup
        
        # SSRF protection: block private/internal IPs
        import ipaddress
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(web_url)
            hostname = parsed.hostname or ""
            # Block private IP ranges
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise HTTPException(status_code=400, detail="URL not allowed")
            except ValueError:
                pass  # hostname is a domain, not IP - OK
            # Block localhost variants
            if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                raise HTTPException(status_code=400, detail="URL not allowed")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid URL")

        # Fetch web content
        async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
            response = await client.get(web_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            html_content = response.text
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get title
        title = soup.title.string if soup.title else "Unknown page"
        
        # Get main text content
        text_content = soup.get_text(separator='\n', strip=True)
        text_content = text_content[:3000]  # Limit to 3000 chars
        
        # Build analysis prompt
        user_uuid = UUID(current_user_id)
        session = {
            "entry_mode": (entry_mode or "").strip().lower(),
            "agent_id": (agent_id or "").strip(),
            "persona": (persona or "").strip(),
            "character_name": (character_name or "").strip(),
            "gender": (gender or "").strip(),
        }
        aid = _session_agent_id(session)
        
        user_question = message.replace(web_url, "").strip() or "Tóm tắt nội dung trang web này"
        
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not openai_key:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY required")
        
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        
        analysis_prompt = f"""Trang web: "{title}"
URL: {web_url}

Nội dung (đoạn đầu):
{text_content}

Câu hỏi: {user_question}"""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""Bạn là {aid}, một cô gái anime thân thiện. Xưng "mình", gọi đối phương "bạn".
Phân tích nội dung web và trả lời bằng tiếng Việt, giọng tự nhiên như chat với bạn.
Không dùng bullet points, không giọng trợ lý AI."""
                },
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=600,
            temperature=0.7
        )
        
        analysis_reply = response.choices[0].message.content or ""
        analysis_reply = _sanitize_agent_handle_typo(analysis_reply, aid)
        analysis_reply = _ensure_assistant_reply(analysis_reply)
        
        # Save to conversation
        conversation = await _get_or_create_conversation(
            db, user_uuid,
            f"[Web] {title}",
            conversation_id
        )
        
        user_msg_content = f"[Web: {title}]\n{web_url}\n{user_question}"
        user_msg = Message(conversation_id=conversation.id, role="user", content=user_msg_content)
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)
        
        rel = await _bump_user_agent_relationship(db, user_uuid, session.get("agent_id"))
        if rel:
            await db.commit()
        
        bot_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=analysis_reply,
            detected_intent="entertainment_knowledge",
            detected_emotion="surprised",
            avatar_action="shocked_face",
        )
        db.add(bot_msg)
        await db.commit()
        await db.refresh(bot_msg)
        
        await _refresh_conversation_title(db, conversation, user_msg_content)
        
        if session.get("entry_mode") == "quickstart" and session.get("agent_id"):
            await append_user_line_and_maybe_summarize(str(user_uuid), session["agent_id"], user_msg_content)
        
        rel_ex = _relationship_payload(rel) if rel else {}
        
        return MediaAnalysisResponse(
            conversation_id=str(conversation.id),
            reply=analysis_reply,
            detected_intent="entertainment_knowledge",
            detected_emotion="surprised",
            avatar_action="shocked_face",
            user_message_count=rel_ex.get("user_message_count"),
            relationship_level=rel_ex.get("relationship_level"),
            relationship_level_up=bool(rel_ex.get("relationship_level_up")),
            new_relationship_level=rel_ex.get("new_relationship_level"),
        )
        
    except ImportError as e:
        logger.error(f"Missing package: {e}")
        raise HTTPException(status_code=500, detail="beautifulsoup4 and httpx packages required")
    except Exception as e:
        logger.error(f"Web scraping failed: {e}")
        raise HTTPException(status_code=500, detail=f"Web scraping failed: {str(e)}")



# ============================================================
# Generative image (Replicate flux-kontext-pro)
# ============================================================
class ImagineRequest(BaseModel):
    prompt: str
    conversation_id: str | None = None
    aspect_ratio: str = "1:1"  # "1:1", "16:9", "9:16", "4:3", "3:4"


class ImagineResponse(BaseModel):
    conversation_id: str
    image_url: str
    prompt: str


@router.post("/imagine", response_model=ImagineResponse)
async def imagine(
    payload: ImagineRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Text-to-image via Replicate (FLUX Kontext Pro by default).
    Saves user prompt + assistant image-message into the conversation history.
    """
    prompt = (payload.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    if len(prompt) > 1500:
        raise HTTPException(status_code=400, detail="prompt too long (max 1500 chars)")

    token = (os.environ.get("REPLICATE_API_TOKEN") or "").strip()
    if not token:
        raise HTTPException(status_code=500, detail="REPLICATE_API_TOKEN not configured")

    model_ref = (os.environ.get("REPLICATE_IMAGE_MODEL") or "black-forest-labs/flux-kontext-pro").strip()

    try:
        import replicate
    except ImportError:
        raise HTTPException(status_code=500, detail="replicate package not installed (pip install replicate)")

    try:
        # Run is sync — wrap in to_thread so we don't block the event loop.
        def _run():
            return replicate.Client(api_token=token).run(  # type: ignore[attr-defined]
                model_ref,
                input={
                    "prompt": prompt,
                    "aspect_ratio": payload.aspect_ratio,
                    "output_format": "jpg",
                    "safety_tolerance": 2,
                },
            )

        output = await asyncio.to_thread(_run)
    except Exception as e:
        logger.warning(f"Replicate run failed: {e}")
        raise HTTPException(status_code=502, detail=f"Image generation failed: {e}")

    # Replicate output may be a string URL, a list of URLs, or a FileOutput object.
    image_url: str = ""
    if isinstance(output, str):
        image_url = output
    elif isinstance(output, list) and output:
        first = output[0]
        image_url = str(first) if first else ""
    elif output is not None:
        # FileOutput-like has __str__ that returns URL.
        image_url = str(output)
    if not image_url or not image_url.startswith("http"):
        raise HTTPException(status_code=502, detail="Replicate returned no image URL")

    # Persist into conversation history (user prompt + assistant image bubble).
    user_uuid = UUID(current_user_id)
    conversation = await _get_or_create_conversation(
        db, user_uuid, f"/imagine {prompt[:80]}", payload.conversation_id
    )
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=f"/imagine {prompt}",
    )
    db.add(user_msg)
    await db.commit()

    bot_content = f"[Đã tạo ảnh từ prompt: {prompt}]\n{image_url}"
    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=bot_content,
        detected_intent="image_generation",
        detected_emotion="surprised",
        avatar_action="happy_face",
    )
    db.add(bot_msg)
    await db.commit()

    await _refresh_conversation_title(db, conversation, f"/imagine {prompt[:60]}")

    return ImagineResponse(
        conversation_id=str(conversation.id),
        image_url=image_url,
        prompt=prompt,
    )
