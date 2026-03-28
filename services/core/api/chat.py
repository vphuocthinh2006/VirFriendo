from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from uuid import UUID
from datetime import datetime
import asyncio
import json
import re
from typing import Any, Mapping

from services.core.database import get_db, AsyncSessionLocal
from services.core.models import Conversation, Message, UserMemory, UserAgentRelationship
from services.core.security import get_current_user_id
from services.core.config import settings
from pydantic import BaseModel
from pydantic import ConfigDict
from jose import jwt
from loguru import logger

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from services.agent_service.graph.workflow import graph_app
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
    final_state = await graph_app.ainvoke({"messages": lc_messages, "agent_id": aid})
    
    # Lấy tin nhắn cuối cùng do AI sinh ra (nằm ở cuối list messages)
    bot_reply_message = final_state["messages"][-1]
    bot_reply = _sanitize_agent_handle_typo(_extract_assistant_content(bot_reply_message), aid)
    bot_reply = _ensure_assistant_reply(bot_reply)
    
    intent = final_state.get("intent")
    emotion = final_state.get("emotion")
    avatar_action = final_state.get("avatar_action")
    bibliotherapy = final_state.get("bibliotherapy_suggestion")

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
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách tất cả conversations của user hiện tại"""
    logger.info("chat.refresh ip={} user_id={}", _client_ip(request), current_user_id)
    user_uuid = UUID(current_user_id)
    query = select(Conversation).where(Conversation.user_id == user_uuid)
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
# WebSocket streaming: /chat/ws
# ---------------------------------------------------------------------------

def _verify_ws_token(token: str) -> str | None:
    """Decode JWT and return user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None


STREAM_CHUNK_WORDS = 3
STREAM_DELAY_S = 0.04


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

    # 4) Invoke LangGraph
    aid = _session_agent_id(session)
    final_state = await graph_app.ainvoke({"messages": lc_messages, "agent_id": aid})

    bot_reply = _sanitize_agent_handle_typo(_extract_assistant_content(final_state["messages"][-1]), aid)
    bot_reply = _ensure_assistant_reply(bot_reply)
    intent = final_state.get("intent")
    emotion = final_state.get("emotion")
    avatar_action = final_state.get("avatar_action")

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

