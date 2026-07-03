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
import tempfile
import ipaddress
import urllib.parse
from typing import Any, Mapping
from pathlib import Path
import httpx
from services.core.database import get_db, AsyncSessionLocal
from services.core.models import Conversation, Message, UserMemory, UserAgentRelationship
from services.core.security import get_current_user_id
from services.core.config import settings
from pydantic import BaseModel
from pydantic import ConfigDict
from jose import jwt
from loguru import logger
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from services.core.context import get_conversation_context, MAX_CONTEXT_MESSAGES
from services.agent_service.llm.memory import extract_user_memories
from services.core.quickstart_personality import (
    append_user_line_and_maybe_summarize,
    get_quickstart_summary,
)
from services.core.s3_media import (
    expand_s3_uris_to_presigned,
    fetch_and_store_generated_image,
    upload_bytes_to_media_bucket,
)
from sqlalchemy import update as sa_update

from services.agent_service.api.intent_classifier import intent_classifier
from services.ml.confidence_gate import (
    emotion_to_avatar_action as _emotion_to_avatar_from_gate,
    gate_dialogue_act,
    merge_emotion_for_avatar,
    needs_emotion_llm_arbitrator,
)
from services.ml.llm_double_check import arbitrator_pick_emotion, arbitration_to_avatar_emotion
from services.ml.nlp_inference import get_nlp_service
from services.ml.gallery_search import gallery_matcher, gallery_hints_blob
from services.ml.vit_encoder import encode_image_pil_normalized

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


def _serialize_lc_message(msg: Any) -> dict[str, str]:
    if isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    if isinstance(msg, AIMessage):
        return {"role": "assistant", "content": msg.content}
    return {"role": "user", "content": getattr(msg, "content", "")}


async def _invoke_agent(lc_messages: list[Any], agent_id: str) -> dict[str, Any]:
    """
    Microservice-first agent invocation.
    If AGENT_SERVICE_URL is configured, call remote service; otherwise fallback local.
    """
    service_url = (settings.AGENT_SERVICE_URL or os.environ.get("AGENT_SERVICE_URL") or "").strip()
    if service_url:
        payload = {
            "agent_id": agent_id,
            "messages": [_serialize_lc_message(m) for m in lc_messages],
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=5.0)) as client:
                resp = await client.post(service_url.rstrip("/") + "/run", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "reply" in data:
                        return data
                logger.warning("agent-service non-200: {}", resp.status_code)
        except Exception as e:
            logger.warning("agent-service unavailable, fallback local: {}", e)

    from services.agent_service.llm_agent import run_agent

    return await run_agent(lc_messages, agent_id=agent_id)


_FALLBACK_EMPTY_REPLY = (
    "Mình chưa tạo được câu trả lời (lỗi model hoặc mạng). Bạn gửi lại giúp mình một lần nữa nhé~"
)


def _ensure_assistant_reply(text: str) -> str:
    t = (text or "").strip()
    return t if t else _FALLBACK_EMPTY_REPLY


def _extract_ws_token(ws: WebSocket) -> str | None:
    """
    Prefer token from WebSocket subprotocols (bearer,<token>) to avoid URL leaks.
    Keep query-param fallback for backward compatibility.
    """
    proto_hdr = (ws.headers.get("sec-websocket-protocol") or "").strip()
    if proto_hdr:
        offered = [p.strip() for p in proto_hdr.split(",") if p.strip()]
        if len(offered) >= 2 and offered[0].lower() == "bearer":
            return offered[1]
    token = (ws.query_params.get("token") or "").strip()
    return token or None


async def _validate_public_web_url(web_url: str) -> None:
    """
    SSRF guard:
    - only allow http/https
    - reject localhost/private/reserved ip literals
    - resolve domain and reject private/local/reserved destination IPs
    """
    parsed = urllib.parse.urlparse(web_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    hostname = (parsed.hostname or "").strip()
    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid URL")
    if hostname.lower() in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
        raise HTTPException(status_code=400, detail="URL not allowed")

    def _is_blocked_ip(raw: str) -> bool:
        ip = ipaddress.ip_address(raw)
        return any(
            [
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_reserved,
                ip.is_multicast,
                ip.is_unspecified,
            ]
        )

    try:
        if _is_blocked_ip(hostname):
            raise HTTPException(status_code=400, detail="URL not allowed")
        return
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        addr_info = await loop.getaddrinfo(hostname, parsed.port or 80, type=0)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL")

    for item in addr_info:
        sockaddr = item[4]
        if not sockaddr:
            continue
        resolved_ip = str(sockaddr[0])
        try:
            if _is_blocked_ip(resolved_ip):
                raise HTTPException(status_code=400, detail="URL not allowed")
        except ValueError:
            continue


def _extract_video_keyframes_as_data_urls(
    content: bytes, mime_type: str, max_frames: int = 6
) -> list[str]:
    """
    Extract evenly-distributed keyframes and convert to JPEG data URLs.
    Used as fallback for video analysis when provider doesn't accept raw video bytes.
    """
    try:
        import cv2  # type: ignore[import-not-found]
    except Exception as e:
        raise RuntimeError(
            "Video fallback requires opencv-python-headless (cv2) to extract keyframes"
        ) from e

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(f"x.{mime_type.split('/')[-1]}").suffix or ".mp4") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    frames: list[str] = []
    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise RuntimeError("Cannot open uploaded video")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            total = 180
        picks = sorted({max(0, min(total - 1, int(i * total / max_frames))) for i in range(max_frames)})

        for idx in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, float(idx))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            ok, enc = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            b64 = base64.b64encode(enc.tobytes()).decode("utf-8")
            frames.append(f"data:image/jpeg;base64,{b64}")
    finally:
        try:
            cap.release()  # type: ignore[name-defined]
        except Exception:
            pass
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not frames:
        raise RuntimeError("Failed to extract keyframes from video")
    return frames


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
    dialogue_act: str | None = None
    ml_debug: dict[str, Any] | None = None
    model_info: dict[str, Any] | None = None
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


async def _nlp_predict_for_user_text(text: str):
    svc = get_nlp_service()
    if not svc.enabled():
        return None
    return await asyncio.to_thread(svc.maybe_predict, text)


async def _intent_predict_for_user_text(text: str) -> str:
    label = await asyncio.to_thread(intent_classifier.predict, text)
    return label if isinstance(label, str) else str(label)


def _nlp_user_payload(nlp_out: Any) -> dict[str, Any] | None:
    if nlp_out is None:
        return None
    return {
        "emotion_label": nlp_out.emotion_label,
        "dialogue_act_label": nlp_out.dialogue_act_label,
        "emotion_probs": {
            "top1": round(nlp_out.emotion_prob_top1, 4),
            "margin": round(nlp_out.emotion_margin, 4),
        },
        "act_probs": {
            "top1": round(nlp_out.act_prob_top1, 4),
            "margin": round(nlp_out.act_margin, 4),
        },
        "emotion_idx": nlp_out.emotion_logits_idx,
        "act_idx": nlp_out.act_logits_idx,
    }


async def _finalize_avatar_with_merge_and_arbitrator(
    *,
    user_text_raw: str,
    nlp_out: Any,
    agent_emotion: str | None,
) -> tuple[str, str, dict[str, Any]]:
    emo_heur = agent_emotion
    merged_e, avatar_a, meta = merge_emotion_for_avatar(nlp_out, emo_heur)
    if needs_emotion_llm_arbitrator(nlp_out, meta) and nlp_out is not None:
        pick, raw_snip = await arbitrator_pick_emotion(
            user_snippet=user_text_raw[:400],
            heuristic_emotion=emo_heur or "neutral",
            nlp_emotion=nlp_out.emotion_label,
            nlp_p_top=nlp_out.emotion_prob_top1,
        )
        merged_e = arbitration_to_avatar_emotion(pick, merged_e)
        avatar_a = _emotion_to_avatar_from_gate(merged_e)
        meta["llm_double_check_snippet"] = raw_snip
    return merged_e, avatar_a, meta


async def _run_character_gallery_on_image_bytes(body: bytes) -> tuple[list[dict[str, Any]], str]:
    """Used from analyze-media (thread offload)."""

    def _inner() -> tuple[list[dict[str, Any]], str]:
        if not getattr(settings, "ENABLE_VIT_GALLERY", False):
            return [], ""
        try:
            from io import BytesIO

            import numpy as np
            import PIL.Image

            img = PIL.Image.open(BytesIO(body))
            emb = encode_image_pil_normalized(img)
            if emb is None:
                return [], ""
            vec = emb.numpy().reshape(-1).astype(np.float32, copy=False)
            hits = gallery_matcher().top_k(vec, k=8)
            hint = gallery_hints_blob(hits)
            slim = []
            for h in hits[:5]:
                slim.append(
                    {
                        "character": h.get("character"),
                        "similarity": round(float(h["similarity"]), 4),
                        "tier": h.get("tier"),
                    }
                )
            return slim, hint
        except Exception:
            logger.exception("Gallery ViT inference failed")
            return [], ""

    return await asyncio.to_thread(_inner)


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
    agent_task = asyncio.create_task(_invoke_agent(lc_messages, aid))
    nlp_task = asyncio.create_task(_nlp_predict_for_user_text(request.message))
    intent_task = asyncio.create_task(_intent_predict_for_user_text(request.message))
    result, nlp_out, routed_intent = await asyncio.gather(agent_task, nlp_task, intent_task)

    bot_reply = _sanitize_agent_handle_typo(result["reply"], aid)
    bot_reply = _ensure_assistant_reply(bot_reply)

    intent = routed_intent

    # --- EMOTION FUSION: BERT (user) + Groq (bot reply) + heuristic ---
    from services.ml.emotion_fusion import detect_bot_reply_emotion, fuse_emotions

    # Run Groq bot emotion detection in parallel with old pipeline
    groq_emotion_task = asyncio.create_task(detect_bot_reply_emotion(bot_reply, request.message))

    # Old pipeline: BERT + heuristic + arbitrator
    emotion_ml, avatar_action, emotion_meta = await _finalize_avatar_with_merge_and_arbitrator(
        user_text_raw=request.message,
        nlp_out=nlp_out,
        agent_emotion=result.get("emotion"),
    )

    # Get Groq bot emotion result
    groq_bot_emotion = await groq_emotion_task

    # Fuse all signals
    bert_emotion = nlp_out.emotion_label if nlp_out else None
    fused_emotion, fusion_meta = fuse_emotions(
        bert_emotion=bert_emotion,
        groq_bot_emotion=groq_bot_emotion,
        heuristic_emotion=emotion_ml,
    )
    emotion = fused_emotion
    emotion_meta["fusion"] = fusion_meta

    # Update avatar_action based on fused emotion
    avatar_action = _emotion_to_avatar_from_gate(fused_emotion)

    bibliotherapy = result.get("bibliotherapy_suggestion")

    # Log ML predictions to S3 for SageMaker Model Monitor + per-conversation analytics
    try:
        from services.ml.prediction_logger import log_nlp_prediction

        _conv_id_str = str(conversation.id)
        _msg_id_str = str(user_msg.id)

        if nlp_out is not None:
            # Intent = dialogue act from BERT (Inform/Question/Directive/Commissive)
            log_nlp_prediction(
                user_text=request.message,
                emotion_label=nlp_out.emotion_label,
                dialogue_act_label=nlp_out.dialogue_act_label,
                emotion_prob_top1=nlp_out.emotion_prob_top1,
                emotion_margin=nlp_out.emotion_margin,
                act_prob_top1=nlp_out.act_prob_top1,
                act_margin=nlp_out.act_margin,
                final_avatar_emotion=fused_emotion,
                arbitrator_used=bool(emotion_meta.get("llm_double_check_snippet")),
                arbitrator_pick=emotion_meta.get("llm_double_check_snippet"),
                conversation_id=_conv_id_str,
                message_id=_msg_id_str,
                intent_label=nlp_out.dialogue_act_label,
                intent_source="bert_multitask",
                intent_model_confidence=nlp_out.act_prob_top1,
                fusion_meta=fusion_meta,
            )
        else:
            log_nlp_prediction(
                user_text=request.message,
                emotion_label="nlp_unavailable",
                dialogue_act_label="unknown",
                emotion_prob_top1=0.0,
                emotion_margin=0.0,
                act_prob_top1=0.0,
                act_margin=0.0,
                final_avatar_emotion=fused_emotion,
                arbitrator_used=False,
                arbitrator_pick=None,
                conversation_id=_conv_id_str,
                message_id=_msg_id_str,
                intent_label="unknown",
                intent_source="nlp_unavailable",
                fusion_meta=fusion_meta,
            )
    except Exception:
        pass

    dlg_act_val = gate_dialogue_act(nlp_out) if nlp_out else None
    user_ml_blob: dict[str, Any] = {
        "intent_classifier": routed_intent,
        "nlp": _nlp_user_payload(nlp_out),
        "emotion_merge": emotion_meta,
    }
    ml_json_u = json.dumps(user_ml_blob, ensure_ascii=False)[:12000]

    await db.execute(
        sa_update(Message)
        .where(Message.id == user_msg.id)
        .values(dialogue_act=dlg_act_val, ml_metadata=ml_json_u),
    )

    bot_ml_json = json.dumps(
        {"nlp_emotion": _nlp_user_payload(nlp_out), "emotion_merge_bot": emotion_meta},
        ensure_ascii=False,
    )[:8000]

    # BƯỚC 4: Lưu phản hồi bot vào DB
    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=bot_reply,
        detected_intent=intent,
        detected_emotion=emotion,
        dialogue_act=None,
        ml_metadata=bot_ml_json,
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
        dialogue_act=dlg_act_val,
        ml_debug=user_ml_blob if nlp_out else None,
        model_info=result.get("model_info"),
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
    dialogue_act: str | None = None
    ml_metadata: str | None = None
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

    out: list[MessageResponse] = []
    for msg in messages:
        m = MessageResponse.model_validate(msg)
        expanded = expand_s3_uris_to_presigned(m.content)
        if expanded != m.content:
            m = m.model_copy(update={"content": expanded})
        out.append(m)
    return out


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


# --- User Feedback (RLHF) ---

class FeedbackRequest(BaseModel):
    message_id: str
    conversation_id: str
    rating: str  # "up" or "down"
    feedback_text: str | None = None


@router.post("/feedback", status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """User rates a bot message (👍/👎) + optional text feedback. Used for RLHF training data."""
    if request.rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up' or 'down'")

    user_uuid = UUID(current_user_id)

    # Get the bot message
    try:
        msg_id = UUID(request.message_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid message_id")

    msg_query = await db.execute(
        select(Message).where(Message.id == msg_id, Message.role == "assistant")
    )
    bot_msg = msg_query.scalar_one_or_none()
    if not bot_msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Get the user message before it (for context)
    prev_query = await db.execute(
        select(Message)
        .where(Message.conversation_id == bot_msg.conversation_id, Message.role == "user")
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    user_msg = prev_query.scalar_one_or_none()

    # Log to S3 for RLHF
    try:
        from services.ml.feedback_store import log_feedback
        log_feedback(
            user_id=current_user_id,
            message_id=request.message_id,
            conversation_id=request.conversation_id,
            bot_reply=bot_msg.content or "",
            user_message=(user_msg.content if user_msg else ""),
            rating=request.rating,
            feedback_text=request.feedback_text,
            detected_emotion=bot_msg.detected_emotion,
            detected_intent=bot_msg.detected_intent,
        )
    except Exception as e:
        logger.warning("Feedback logging failed: {}", e)

    return {"status": "ok", "rating": request.rating}


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
    token = _extract_ws_token(ws)
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return
    user_id = _verify_ws_token(token)
    if not user_id:
        await ws.close(code=4001, reason="Invalid token")
        return

    proto_hdr = (ws.headers.get("sec-websocket-protocol") or "").strip()
    if proto_hdr:
        await ws.accept(subprotocol="bearer")
    else:
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

    # 4) Invoke Claude agent (+ parallel NLP + intent)
    aid = _session_agent_id(session)
    agent_task = asyncio.create_task(_invoke_agent(lc_messages, aid))
    nlp_task = asyncio.create_task(_nlp_predict_for_user_text(content))
    intent_task = asyncio.create_task(_intent_predict_for_user_text(content))
    result, nlp_out, routed_intent = await asyncio.gather(agent_task, nlp_task, intent_task)

    bot_reply = _sanitize_agent_handle_typo(result["reply"], aid)
    bot_reply = _ensure_assistant_reply(bot_reply)
    intent = routed_intent

    # --- EMOTION FUSION (WS): BERT + Groq bot + heuristic ---
    from services.ml.emotion_fusion import detect_bot_reply_emotion, fuse_emotions

    groq_emotion_task = asyncio.create_task(detect_bot_reply_emotion(bot_reply, content))
    emotion_ml, avatar_action, emotion_meta = await _finalize_avatar_with_merge_and_arbitrator(
        user_text_raw=content,
        nlp_out=nlp_out,
        agent_emotion=result.get("emotion"),
    )
    groq_bot_emotion = await groq_emotion_task
    bert_emotion = nlp_out.emotion_label if nlp_out else None
    emotion, fusion_meta = fuse_emotions(
        bert_emotion=bert_emotion,
        groq_bot_emotion=groq_bot_emotion,
        heuristic_emotion=emotion_ml,
    )
    emotion_meta["fusion"] = fusion_meta
    avatar_action = _emotion_to_avatar_from_gate(emotion)

    dlg_act_val = gate_dialogue_act(nlp_out) if nlp_out else None
    user_ml_blob: dict[str, Any] = {
        "intent_classifier": routed_intent,
        "nlp": _nlp_user_payload(nlp_out),
        "emotion_merge": emotion_meta,
    }
    ml_json_u = json.dumps(user_ml_blob, ensure_ascii=False)[:12000]
    await db.execute(
        sa_update(Message)
        .where(Message.id == user_msg.id)
        .values(dialogue_act=dlg_act_val, ml_metadata=ml_json_u),
    )

    bot_ml_json = json.dumps(
        {"nlp_emotion": _nlp_user_payload(nlp_out), "emotion_merge_bot": emotion_meta},
        ensure_ascii=False,
    )[:8000]

    # 5) Save bot message
    bot_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=bot_reply,
        detected_intent=intent,
        detected_emotion=emotion,
        dialogue_act=None,
        ml_metadata=bot_ml_json,
        avatar_action=avatar_action,
    )
    db.add(bot_msg)
    await db.commit()
    await db.refresh(bot_msg)

    # Log ML predictions to S3 (WS path)
    try:
        from services.ml.prediction_logger import log_nlp_prediction

        _conv_id_str = str(conversation.id)
        _msg_id_str = str(user_msg.id)

        if nlp_out is not None:
            # Intent = dialogue act from BERT (Inform/Question/Directive/Commissive)
            log_nlp_prediction(
                user_text=content,
                emotion_label=nlp_out.emotion_label,
                dialogue_act_label=nlp_out.dialogue_act_label,
                emotion_prob_top1=nlp_out.emotion_prob_top1,
                emotion_margin=nlp_out.emotion_margin,
                act_prob_top1=nlp_out.act_prob_top1,
                act_margin=nlp_out.act_margin,
                final_avatar_emotion=emotion,
                arbitrator_used=bool(emotion_meta.get("llm_double_check_snippet")),
                arbitrator_pick=emotion_meta.get("llm_double_check_snippet"),
                conversation_id=_conv_id_str,
                message_id=_msg_id_str,
                intent_label=nlp_out.dialogue_act_label,
                intent_source="bert_multitask",
                intent_model_confidence=nlp_out.act_prob_top1,
                fusion_meta=fusion_meta,
            )
        else:
            log_nlp_prediction(
                user_text=content,
                emotion_label="nlp_unavailable",
                dialogue_act_label="unknown",
                emotion_prob_top1=0.0,
                emotion_margin=0.0,
                act_prob_top1=0.0,
                act_margin=0.0,
                final_avatar_emotion=emotion,
                arbitrator_used=False,
                arbitrator_pick=None,
                conversation_id=_conv_id_str,
                message_id=_msg_id_str,
                intent_label="unknown",
                intent_source="nlp_unavailable",
                fusion_meta=fusion_meta,
            )
    except Exception:
        pass

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
        "dialogue_act": dlg_act_val,
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
    request: Request,
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

    # Microservice mode: forward to media-service.
    media_url = (settings.MEDIA_SERVICE_URL or os.environ.get("MEDIA_SERVICE_URL") or "").strip()
    if media_url:
        auth = (request.headers.get("Authorization") or "").strip()
        content = await file.read()
        mime = file.content_type or "application/octet-stream"
        files = {"file": (file.filename or "audio.webm", content, mime)}
        headers = {"Authorization": auth} if auth else {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            res = await client.post(
                media_url.rstrip("/") + "/chat/transcribe",
                headers=headers,
                files=files,
            )
        if not res.ok:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

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
    stored_media_url: str | None = None  # presigned HTTPS if S3 upload succeeded
    character_gallery_hints: list[dict[str, Any]] | None = None  # ViT + gallery top-k metadata


@router.post("/analyze-media", response_model=MediaAnalysisResponse)
async def analyze_media(
    request: Request,
    file: UploadFile | None = File(None),
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
    logger.info(
        f"analyze_media called: file={getattr(file, 'filename', None)}, message={message[:100] if message else 'empty'}"
    )

    # Microservice mode: forward to media-service.
    media_url = (settings.MEDIA_SERVICE_URL or os.environ.get("MEDIA_SERVICE_URL") or "").strip()
    if media_url:
        auth = (request.headers.get("Authorization") or "").strip()
        form_data: dict[str, str] = {
            "message": message or "",
        }
        if conversation_id:
            form_data["conversation_id"] = conversation_id
        if agent_id:
            form_data["agent_id"] = agent_id
        if entry_mode:
            form_data["entry_mode"] = entry_mode
        if persona:
            form_data["persona"] = persona
        if character_name:
            form_data["character_name"] = character_name
        if gender:
            form_data["gender"] = gender

        files = None
        if file is not None:
            content = await file.read()
            mime = file.content_type or "application/octet-stream"
            files = {"file": (file.filename or "upload", content, mime)}

        headers = {"Authorization": auth} if auth else {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            res = await client.post(
                media_url.rstrip("/") + "/chat/analyze-media",
                headers=headers,
                data=form_data,
                files=files,
            )
        if not res.ok:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()
    
    # Check if message contains YouTube URL
    youtube_pattern = r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
    youtube_match = re.search(youtube_pattern, message) if message else None
    
    # Check if message contains web URL
    url_pattern = r'https?://[^\s]+'
    url_match = re.search(url_pattern, message) if message else None

    # Optional microservice split: delegate URL-based analysis to knowledge-service.
    knowledge_url = (settings.KNOWLEDGE_SERVICE_URL or os.environ.get("KNOWLEDGE_SERVICE_URL") or "").strip()
    if knowledge_url and (youtube_match or (url_match and not youtube_match)):
        auth = (request.headers.get("Authorization") or "").strip()
        data = {
            "message": message or "",
            "conversation_id": conversation_id or "",
            "agent_id": agent_id or "",
            "entry_mode": entry_mode or "",
            "persona": persona or "",
            "character_name": character_name or "",
            "gender": gender or "",
        }
        endpoint = "/chat/analyze-youtube" if youtube_match else "/chat/analyze-web"
        data["url"] = youtube_match.group(0) if youtube_match else (url_match.group(0) if url_match else "")
        headers = {"Authorization": auth} if auth else {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            res = await client.post(knowledge_url.rstrip("/") + endpoint, headers=headers, data=data)
        if not res.ok:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()
    
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

    if file is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either a media file upload or a YouTube/Web URL in message",
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
    
    # Read media bytes
    content = await file.read()
    logger.info(f"File size: {len(content)} bytes")
    
    # Check file size
    is_video = file_ext in [".mp4", ".mov", ".avi", ".webm"]
    max_size = 50 * 1024 * 1024 if is_video else 20 * 1024 * 1024
    
    if len(content) > max_size:
        max_mb = 50 if is_video else 20
        logger.error(f"File too large: {len(content)} bytes > {max_size} bytes")
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {max_mb}MB")

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

    stored_media_url: str | None = None
    s3_uri_line = ""
    s3_upload = await upload_bytes_to_media_bucket(
        user_id=current_user_id,
        kind="upload",
        body=content,
        content_type=mime_type,
        filename_suffix=file_ext,
    )
    if s3_upload:
        uri, presigned = s3_upload
        s3_uri_line = f"\n{uri}"
        stored_media_url = presigned
        logger.info(f"[S3] Uploaded user media → {uri}")

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

    gallery_hints_list: list[dict[str, Any]] = []
    gallery_ctx = ""
    if not is_video and getattr(settings, "ENABLE_VIT_GALLERY", False):
        gallery_hints_list, _ = await _run_character_gallery_on_image_bytes(content)
        logger.info(f"[ViT Gallery] matches={len(gallery_hints_list)}, top={gallery_hints_list[0] if gallery_hints_list else 'none'}")
        if gallery_hints_list:
            top = gallery_hints_list[0]
            nm = top.get("character") or ""
            sim = top.get("similarity", 0)
            tier = top.get("tier") or ""
            # Cross-validation: if top2 is close to top1, flag ambiguity
            margin_note = ""
            if len(gallery_hints_list) >= 2:
                second = gallery_hints_list[1]
                margin = sim - (second.get("similarity", 0))
                if margin < 0.05:
                    margin_note = (
                        f" ⚠️ Lưu ý: nhân vật thứ 2 gần bằng ({second.get('character')}, "
                        f"sim={second.get('similarity', 0):.2f}) — có thể nhầm lẫn. "
                        "Hãy dùng Gemini/GPT-4o vision để double-check."
                    )
            if tier in ("high", "confident"):
                gallery_ctx = (
                    f"Gallery ViT nhận diện CHẮC CHẮN: 「{nm}」 (similarity={sim:.2f}, tier={tier}).{margin_note}\n"
                    "Tin cậy RẤT CAO — ViT được train riêng trên nhân vật này. LUÔN dùng tên này.\n"
                    "KHÔNG được đổi sang tên khác dù vision API nói gì. ViT chính xác hơn vision API về identity.\n\n"
                )
            elif tier == "medium":
                gallery_ctx = (
                    f"Gallery ViT nhận diện: 「{nm}」 (similarity={sim:.2f}, tier={tier}).{margin_note}\n"
                    "Tin cậy trung bình-cao — ViT được train riêng trên gallery nhân vật nên CHÍNH XÁC hơn vision API về tên nhân vật.\n"
                    "NẾU vision API nói nhân vật KHÁC nhưng CÙNG BỘ ANIME/GAME → TIN ViT (ví dụ: ViT nói Fern, vision nói Frieren — cả 2 cùng anime nhưng ViT đúng hơn).\n"
                    "CHỈ bỏ qua ViT nếu vision API nói nhân vật từ BỘ ANIME/GAME HOÀN TOÀN KHÁC.\n\n"
                )
            else:
                gallery_ctx = (
                    f"Gallery ViT gợi ý yếu: 「{nm}」 (similarity={sim:.2f}, tier={tier}).{margin_note}\n"
                    "Tin cậy thấp — KHÔNG dùng tên này trừ khi vision API cũng đồng ý. Ưu tiên vision.\n\n"
                )

    # Get vision analysis - GPT-4o (primary) → GPT-4o-mini (fallback)
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if not gemini_key and not openai_key:
        raise HTTPException(status_code=500, detail="Vision analysis requires GEMINI_API_KEY or OPENAI_API_KEY")

    vision_system = gallery_ctx + f"""Bạn là {aid}, một cô gái anime thân thiện. Xưng "mình", gọi đối phương "bạn".

NHIỆM VỤ: Phân tích {'video' if is_video else 'ảnh'} và NHẬN DIỆN chính xác nhất có thể.

BẮT BUỘC — NHẬN DIỆN NHÂN VẬT:
- LUÔN LUÔN đoán tên nhân vật/người. KHÔNG BAO GIỜ nói "không thể xác định" hay "người đàn ông bí ẩn".
- Nếu là nhân vật anime/manga/game/phim: nói TÊN + TÁC PHẨM. Ví dụ: "Đây là Levi Ackerman từ Attack on Titan".
- Nếu là người thật: nói TÊN + NGHỀ. Ví dụ: "Đây là Keanu Reeves, diễn viên".
- Nếu không chắc 100%: vẫn PHẢI đoán top 2-3 khả năng. Ví dụ: "Mình nghĩ đây là Aiden Pearce (Watch Dogs) hoặc có thể là một cosplay của nhân vật cyberpunk".
- Dựa vào MỌI chi tiết: kiểu tóc, màu tóc, trang phục, phụ kiện, sẹo, hình xăm, vũ khí, bối cảnh, phong cách vẽ.
- KHÔNG BAO GIỜ trả lời chung chung kiểu "người đàn ông mặc áo khoác da" mà không đoán danh tính.

SEARCH QUERY — CỰC KỲ QUAN TRỌNG:
- Query PHẢI cụ thể để Google tìm được đúng nhân vật.
- ĐÚNG: "Aiden Pearce Watch Dogs character", "Levi Ackerman Attack on Titan"
- SAI: "mysterious man leather jacket", "anime character dark background"
- Nếu thấy đặc điểm độc đáo (mặt nạ, vũ khí, biểu tượng): dùng nó trong query.
- Ví dụ: thấy mặt nạ fox → "fox mask anime character", thấy bịt mắt + tóc trắng → "Gojo Satoru Jujutsu Kaisen"

Trả lời bằng tiếng Việt, tự nhiên, 3-6 câu. KHÔNG bullet points. KHÔNG BAO GIỜ dùng ký tự Trung Quốc/Nhật/Hàn — chỉ tiếng Việt thuần.

CUỐI câu trả lời, BẮT BUỘC thêm 3 dòng:
CONFIDENCE: <số từ 1-10, 10 = chắc chắn 100%, 1 = đoán mò>
SEARCH_QUERY: <query tiếng Anh CỤ THỂ để tìm đúng nhân vật — PHẢI có tên nhân vật nếu đoán được>
SUBJECT_TAG: <tên nhân vật + nguồn, ví dụ "Aiden Pearce (Watch Dogs)">"""

    raw_vision = ""

    # --- MULTI-MODEL CONSENSUS: call both GPT-4o AND Gemini, pick best ---
    gpt4o_result = ""
    gemini_result = ""

    async def _call_gpt4o() -> str:
        if not openai_key:
            return ""
        try:
            logger.info("[VISION] Calling GPT-4o...")
            from openai import OpenAI
            oai = OpenAI(api_key=openai_key)
            user_content: list[dict[str, Any]] = [{"type": "text", "text": vision_prompt}]
            if is_video:
                frame_urls = _extract_video_keyframes_as_data_urls(content, mime_type, max_frames=6)
                for frame_url in frame_urls:
                    user_content.append({"type": "image_url", "image_url": {"url": frame_url, "detail": "low"}})
                user_content.append({"type": "text", "text": "Các ảnh trên là khung hình theo timeline video. Hãy suy luận diễn biến chính."})
            else:
                base64_content = base64.b64encode(content).decode('utf-8')
                user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_content}", "detail": "high"}})
            response = oai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": vision_system}, {"role": "user", "content": user_content}],
                max_tokens=900,
                temperature=0.5,
            )
            result = response.choices[0].message.content or ""
            logger.info("[VISION] ✅ GPT-4o done")
            return result
        except Exception as e:
            logger.error("[VISION] GPT-4o failed: {}", e)
            return ""

    async def _call_gemini() -> str:
        """Fallback: GPT-4o-mini (cheaper, still has vision)."""
        if not openai_key:
            return ""
        try:
            logger.info("[VISION] Calling GPT-4o-mini (fallback)...")
            from openai import OpenAI
            oai = OpenAI(api_key=openai_key)
            user_content: list[dict[str, Any]] = [{"type": "text", "text": vision_prompt}]
            if is_video:
                frame_urls = _extract_video_keyframes_as_data_urls(content, mime_type, max_frames=4)
                for frame_url in frame_urls:
                    user_content.append({"type": "image_url", "image_url": {"url": frame_url, "detail": "low"}})
            else:
                base64_content = base64.b64encode(content).decode('utf-8')
                user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_content}", "detail": "high"}})
            response = oai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": vision_system}, {"role": "user", "content": user_content}],
                max_tokens=900,
                temperature=0.5,
            )
            result = response.choices[0].message.content or ""
            logger.info("[VISION] ✅ GPT-4o-mini done")
            return result
        except Exception as e:
            logger.error("[VISION] GPT-4o-mini failed: {}", e)
            return ""

    # Run both in parallel
    gpt4o_task = asyncio.create_task(_call_gpt4o())
    gemini_task = asyncio.create_task(_call_gemini())
    gpt4o_result, gemini_result = await asyncio.gather(gpt4o_task, gemini_task)

    # --- FUSION SCORE CONSENSUS LOGIC ---
    def _parse_vision_confidence(text: str) -> float:
        """Extract CONFIDENCE: N from vision response. Returns 0-1 scale."""
        for line in text.splitlines():
            stripped = line.strip().upper()
            if stripped.startswith("CONFIDENCE:"):
                try:
                    val = float(stripped.split(":", 1)[1].strip().split()[0])
                    return min(max(val / 10.0, 0.0), 1.0)
                except (ValueError, IndexError):
                    pass
        return 0.5  # default if not found

    def _parse_subject_tag(text: str) -> str:
        """Extract SUBJECT_TAG value from vision response."""
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("SUBJECT_TAG:"):
                return stripped.split(":", 1)[1].strip().strip('"').strip("'")
        return ""

    def _compute_fusion_decision(
        vit_sim: float, vit_name: str, vit_tier: str,
        gpt4o_conf: float, gpt4o_tag: str,
        mini_conf: float, mini_tag: str,
    ) -> dict[str, Any]:
        """Compute fusion score to decide ViT vs Vision API winner.

        Logic:
        - If ViT and GPT-4o AGREE → high confidence, use that name
        - If they DISAGREE → ALWAYS trust GPT-4o (it sees the actual image)
        - ViT is only used as confirmation signal, never overrides vision API

        Returns dict with 'winner' ('vit' or 'vision'), 'fusion_score', 'reason'.
        """
        vit_conf = min(max(vit_sim, 0.0), 1.0)
        vision_conf = gpt4o_conf * 0.7 + mini_conf * 0.3

        # Check if ViT and vision agree (same character name)
        vit_lower = vit_name.lower().replace("_", " ")
        gpt4o_lower = gpt4o_tag.lower()
        mini_lower = mini_tag.lower()
        vit_in_gpt4o = vit_lower in gpt4o_lower or any(w in gpt4o_lower for w in vit_lower.split() if len(w) > 3)
        vit_in_mini = vit_lower in mini_lower or any(w in mini_lower for w in vit_lower.split() if len(w) > 3)

        # AGREEMENT: ViT confirms what GPT-4o says → extra confidence
        if vit_in_gpt4o or vit_in_mini:
            return {"winner": "agreement", "fusion_score": vision_conf + 0.2, "reason": "vit_confirms_vision"}

        # DISAGREEMENT: GPT-4o and ViT say different things
        # → ALWAYS trust GPT-4o. It sees the actual pixels.
        # ViT gallery only has 45 classes and often confuses characters from same anime.
        # GPT-4o is a general vision model that can identify ANY character.
        if gpt4o_conf >= 0.5:
            return {"winner": "vision", "fusion_score": vision_conf, "reason": "vision_overrides_vit_disagreement"}

        # GPT-4o low confidence + ViT high tier → use ViT as hint but still prefer vision
        if vit_tier in ("high", "confident") and vit_conf >= 0.85:
            return {"winner": "vit", "fusion_score": vit_conf, "reason": "vit_high_confidence_vision_unsure"}

        # Default: trust vision
        return {"winner": "vision", "fusion_score": vision_conf, "reason": "default_trust_vision"}

    if gpt4o_result and gemini_result:
        # Parse confidence from both vision responses
        gpt4o_conf = _parse_vision_confidence(gpt4o_result)
        mini_conf = _parse_vision_confidence(gemini_result)
        gpt4o_tag = _parse_subject_tag(gpt4o_result)
        mini_tag = _parse_subject_tag(gemini_result)

        # Compute fusion decision if ViT has a match
        fusion_info = ""
        if gallery_hints_list:
            top = gallery_hints_list[0]
            vit_name = top.get("character", "")
            vit_sim = top.get("similarity", 0)
            vit_tier = top.get("tier", "")
            fusion = _compute_fusion_decision(
                vit_sim, vit_name, vit_tier,
                gpt4o_conf, gpt4o_tag,
                mini_conf, mini_tag,
            )
            logger.info(
                f"[FUSION] ViT={vit_name}(sim={vit_sim:.3f},tier={vit_tier}) vs "
                f"GPT4o={gpt4o_tag}(conf={gpt4o_conf:.1f}) vs Mini={mini_tag}(conf={mini_conf:.1f}) "
                f"→ winner={fusion['winner']}, score={fusion['fusion_score']:.3f}, reason={fusion['reason']}"
            )
            if fusion["winner"] == "vit":
                fusion_info = (
                    f"\n\nGỢI Ý TỪ ViT: 「{vit_name.replace('_', ' ').title()}」 "
                    f"(score={fusion['fusion_score']:.2f}). "
                    f"Chỉ dùng tên này nếu GPT-4o cũng không chắc chắn."
                )
            elif fusion["winner"] == "agreement":
                fusion_info = (
                    f"\n\n✅ CẢ HAI ĐỒNG Ý: ViT Gallery xác nhận nhân vật từ nguồn A/B. Tin tưởng cao."
                )

        # Both succeeded — use LLM to merge with fusion guidance
        from services.agent_service.llm.client import generate
        consensus_prompt = (
            f"Bạn là trợ lý chat vui vẻ. Hai nguồn AI đã phân tích cùng 1 ảnh (user KHÔNG biết có 2 nguồn).\n\n"
            f"=== Nguồn A ===\n{gpt4o_result[:800]}\n\n"
            f"=== Nguồn B ===\n{gemini_result[:800]}\n\n"
            f"=== ViT Gallery ===\n{gallery_ctx or 'Không có kết quả'}\n\n"
            f"{fusion_info}\n\n"
            "NHIỆM VỤ: Viết 1 câu trả lời DUY NHẤT bằng tiếng Việt cho user.\n"
            "QUY TẮC BẮT BUỘC:\n"
            "- KHÔNG BAO GIỜ nhắc đến 'GPT-4o', 'Gemini', 'nguồn A', 'nguồn B', 'AI', 'hệ thống', 'ViT', 'fusion'\n"
            "- KHÔNG nói 'theo phân tích', 'dựa trên thông tin', 'một bên nói... bên kia nói...'\n"
            "- Viết như BẠN tự nhận ra nhân vật — tự tin, trực tiếp\n"
            "- ƯU TIÊN thông tin từ nguồn A (GPT-4o) vì nó nhìn ảnh trực tiếp\n"
            "- NẾU có '✅ CẢ HAI ĐỒNG Ý' → nói chắc chắn\n"
            "- NẾU có 'GỢI Ý TỪ ViT' nhưng nguồn A nói khác → TIN NGUỒN A\n"
            "- Giọng chat tự nhiên, xưng 'mình' gọi 'bạn', ngắn gọn 2-3 câu\n"
            "- CUỐI câu trả lời thêm 2 dòng riêng:\n"
            "SEARCH_QUERY: <query tiếng Anh để tìm nhân vật>\n"
            "SUBJECT_TAG: <tên nhân vật (nguồn)>"
        )
        merged = await generate(consensus_prompt, "Viết câu trả lời:")
        if merged and len(merged.strip()) > 40:
            raw_vision = merged.strip()
            logger.info("[VISION] ✅ Consensus merged with fusion scoring")
        else:
            raw_vision = gpt4o_result  # fallback to GPT-4o
    elif gpt4o_result:
        raw_vision = gpt4o_result
    elif gemini_result:
        raw_vision = gemini_result

    if not raw_vision:
        raise HTTPException(status_code=500, detail="Vision analysis failed: no response from any provider")

    # Extract SEARCH_QUERY + SUBJECT_TAG + CONFIDENCE, strip them from user-facing reply
    search_query: str = ""
    subject_tag: str = ""
    cleaned_lines: list[str] = []
    for line in raw_vision.splitlines():
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("CONFIDENCE:") or up.startswith("CONFIDENCE :"):
            continue  # strip confidence line from user-facing reply
        if up.startswith("SEARCH_QUERY:") or up.startswith("SEARCH_QUERY :"):
            q = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if q and q.upper() != "NONE":
                search_query = q
            continue
        if up.startswith("SUBJECT_TAG:") or up.startswith("SUBJECT_TAG :"):
            t = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if t and t.lower() not in ("none", "ảnh chung"):
                subject_tag = t
            continue
        # Also strip inline occurrences (LLM sometimes embeds them mid-text)
        cleaned = re.sub(r'SEARCH_QUERY\s*:\s*"?[^"\n]+"?', '', stripped, flags=re.IGNORECASE)
        cleaned = re.sub(r'SUBJECT_TAG\s*:\s*"?[^"\n]+"?', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'CONFIDENCE\s*:\s*\d+', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()
        if cleaned:
            cleaned_lines.append(cleaned)
    vision_reply = "\n".join(cleaned_lines).strip()

    logger.info(f"Vision pass done. search_query={search_query!r} subject_tag={subject_tag!r}")

    # PASS 2: reverse-image-search via Tavily on the extracted subject
    if search_query and not is_video:
        try:
            from services.agent_service.llm.web_search import tavily_search
            # Search with multiple queries for better coverage
            hits = await tavily_search(search_query, max_results=5)
            
            # If first search is too generic, try a more specific one
            if subject_tag and subject_tag.lower() != "ảnh chung":
                extra_hits = await tavily_search(f"{subject_tag} character wiki", max_results=3)
                hits.extend(extra_hits)
            
            logger.info(f"Tavily hits for {search_query!r}: {len(hits)}")
            if hits:
                sources_text = "\n".join(
                    f"- {h.get('title','')}: {h.get('snippet','')[:300]} ({h.get('url','')})"
                    for h in hits if h.get('snippet') or h.get('title')
                )
                if sources_text.strip():
                    from services.agent_service.llm.client import generate
                    enrich_system = (
                        f"Bạn là {aid}. Xưng 'mình', gọi đối phương 'bạn'. "
                        "NHIỆM VỤ: Dựa vào thông tin web, XÁC NHẬN hoặc SỬA danh tính nhân vật trong ảnh. "
                        "Nếu web confirm đúng nhân vật → nói chắc chắn + thêm facts thú vị. "
                        "Nếu web suggest nhân vật khác → sửa lại danh tính cho đúng. "
                        "Viết tự nhiên tiếng Việt, 4-8 câu. KHÔNG bullet. KHÔNG link. "
                        "Phải NÓI RÕ TÊN nhân vật + tác phẩm nguồn."
                    )
                    enrich_user = (
                        f"PHÂN TÍCH ẢNH BAN ĐẦU:\n{vision_reply}\n\n"
                        f"NHÂN VẬT ĐÃ ĐOÁN: {subject_tag or 'chưa xác định'}\n\n"
                        f"KẾT QUẢ TÌM KIẾM WEB ('{search_query}'):\n{sources_text}\n\n"
                        "Viết câu trả lời cuối cùng — XÁC NHẬN danh tính dựa trên web. "
                        "Nếu web nói khác → sửa. Nếu web confirm → nói chắc chắn hơn + thêm info."
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
    user_msg_content = (
        f"{media_label}{s3_uri_line}\n{message}"
        if message
        else f"{media_label}{s3_uri_line}"
    )
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
        stored_media_url=stored_media_url,
        character_gallery_hints=gallery_hints_list if gallery_hints_list else None,
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
        
        messages = [
            {
                "role": "system",
                "content": f"""Bạn là {aid}, một cô gái anime thân thiện. Xưng "mình", gọi đối phương "bạn".
Phân tích video YouTube và trả lời bằng tiếng Việt, giọng tự nhiên như chat với bạn.
Không dùng bullet points, không giọng trợ lý AI."""
            },
            {"role": "user", "content": analysis_prompt}
        ]
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=600,
            temperature=0.7,
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
            character_gallery_hints=None,
        )
        
    except ImportError as e:
        logger.error(f"Missing package: {e}")
        raise HTTPException(status_code=500, detail="youtube-transcript-api package required")
    except HTTPException:
        raise
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
        
        await _validate_public_web_url(web_url)

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
        
        messages = [
            {
                "role": "system",
                "content": f"""Bạn là {aid}, một cô gái anime thân thiện. Xưng "mình", gọi đối phương "bạn".
Phân tích nội dung web và trả lời bằng tiếng Việt, giọng tự nhiên như chat với bạn.
Không dùng bullet points, không giọng trợ lý AI."""
            },
            {"role": "user", "content": analysis_prompt}
        ]
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=600,
            temperature=0.7,
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
            character_gallery_hints=None,
        )
        
    except ImportError as e:
        logger.error(f"Missing package: {e}")
        raise HTTPException(status_code=500, detail="beautifulsoup4 and httpx packages required")
    except HTTPException:
        raise
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
    request: Request,
    payload: ImagineRequest,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Text-to-image via Replicate (FLUX Kontext Pro by default).
    Saves user prompt + assistant image-message into the conversation history.
    """
    media_url = (settings.MEDIA_SERVICE_URL or os.environ.get("MEDIA_SERVICE_URL") or "").strip()
    if media_url:
        auth = (request.headers.get("Authorization") or "").strip()
        headers = {"Authorization": auth} if auth else {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            res = await client.post(
                media_url.rstrip("/") + "/chat/imagine",
                headers=headers,
                json=payload.model_dump(),
            )
        if not res.ok:
            raise HTTPException(status_code=res.status_code, detail=res.text)
        return res.json()

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

    outbound_image_url = image_url
    stored_s3_uri = ""
    s3_gen = await fetch_and_store_generated_image(user_id=current_user_id, source_url=image_url)
    if s3_gen:
        stored_s3_uri, outbound_image_url = s3_gen
        logger.info(f"[S3] Stored generated image → {stored_s3_uri}")

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

    bot_content = f"[Đã tạo ảnh từ prompt: {prompt}]\n{stored_s3_uri or image_url}"
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
        image_url=outbound_image_url,
        prompt=prompt,
    )


# ---------------------------------------------------------------------------
# ML Analytics endpoint — aggregate per-conversation analytics and push to S3
# ---------------------------------------------------------------------------

class ConversationAnalyticsResponse(BaseModel):
    conversation_id: str
    total_messages: int
    emotion_distribution: dict[str, Any]
    dialogue_act_distribution: dict[str, Any]
    intent_distribution: dict[str, Any]
    avg_emotion_confidence: float
    avg_act_confidence: float
    intent_model_properties: dict[str, Any]
    s3_key: str | None = None


@router.get("/analytics/{conversation_id}", response_model=ConversationAnalyticsResponse)
async def get_conversation_analytics(
    conversation_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate ML analytics for a conversation and push to S3.

    Returns emotion/dialogue_act/intent distributions with percentages,
    model properties, and reasoning for choosing intent_model over Groq.
    """
    user_uuid = UUID(current_user_id)
    try:
        conv_uuid = UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation_id")

    # Verify ownership
    conv_q = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_uuid,
            Conversation.user_id == user_uuid,
        )
    )
    if not conv_q.scalar():
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Fetch all user messages with ml_metadata
    msg_q = await db.execute(
        select(Message).where(
            Message.conversation_id == conv_uuid,
            Message.role == "user",
        ).order_by(Message.created_at.asc())
    )
    messages = msg_q.scalars().all()

    emotion_dist: dict[str, int] = {}
    act_dist: dict[str, int] = {}
    intent_dist: dict[str, int] = {}
    total_emotion_conf: float = 0.0
    total_act_conf: float = 0.0
    count_with_nlp: int = 0

    for msg in messages:
        meta_raw = msg.ml_metadata
        if not meta_raw:
            continue
        try:
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
        except (json.JSONDecodeError, TypeError):
            continue

        # Intent
        intent_label = meta.get("intent_classifier") or "unknown"
        intent_dist[intent_label] = intent_dist.get(intent_label, 0) + 1

        # NLP predictions
        nlp_data = meta.get("nlp")
        if nlp_data:
            count_with_nlp += 1
            em_label = nlp_data.get("emotion_label", "unknown")
            act_label = nlp_data.get("dialogue_act_label", "unknown")
            emotion_dist[em_label] = emotion_dist.get(em_label, 0) + 1
            act_dist[act_label] = act_dist.get(act_label, 0) + 1

            em_probs = nlp_data.get("emotion_probs", {})
            act_probs = nlp_data.get("act_probs", {})
            total_emotion_conf += em_probs.get("top1", 0.0)
            total_act_conf += act_probs.get("top1", 0.0)

    total = len(messages)
    avg_em_conf = total_emotion_conf / count_with_nlp if count_with_nlp > 0 else 0.0
    avg_act_conf = total_act_conf / count_with_nlp if count_with_nlp > 0 else 0.0

    intent_model_props = {
        "model_name": "bert-base-uncased (multitask fine-tuned)",
        "model_file": "intent_emotion_model.pth (438MB)",
        "architecture": "BERT + dual classification heads (emotion 7-class + dialogue_act 4-class)",
        "training_data": "VirFriendo conversation logs — emotion + dialogue act annotated",
        "inference_device": "CPU (ECS Fargate 1 vCPU)",
        "avg_latency_ms": "15-50ms (local, no network)",
        "advantages_over_groq": [
            "Zero API cost — inference runs locally on ECS CPU, no per-token billing",
            "Deterministic — same input always produces same classification label",
            "No rate-limit / quota exhaustion risk under high traffic",
            "Low latency ~15-50ms vs Groq API ~200-800ms (network round-trip)",
            "No external network dependency — works even if Groq/OpenAI APIs are down",
            "Privacy — user text never leaves the container for intent/emotion classification",
            "Consistent accuracy on trained domain (emotion + dialogue act)",
            "No temperature/sampling variance — reproducible results for debugging",
        ],
        "limitations": [
            "Fixed label set — cannot classify new intents without retraining",
            "Requires ~438MB model file downloaded at container startup",
            "CPU-only inference on Fargate (no GPU, slower than GPU but acceptable)",
            "Domain-specific — trained only on VirFriendo conversation patterns",
        ],
        "groq_comparison_table": {
            "cost_per_1k_calls": {"bert": "$0.00", "groq": "~$0.05-0.10"},
            "latency_p50": {"bert": "~25ms", "groq": "~350ms"},
            "determinism": {"bert": "100% deterministic", "groq": "non-deterministic (temperature)"},
            "availability": {"bert": "100% (local)", "groq": "99.5% (API dependency)"},
            "flexibility": {"bert": "fixed labels only", "groq": "arbitrary prompts"},
            "privacy": {"bert": "data stays in container", "groq": "text sent to external API"},
        },
        "decision_summary": (
            "BERT intent_model chosen for production: "
            "cost=0, latency<50ms, deterministic, no external dependency. "
            "Groq LLM hybrid was tested but removed — too unreliable for production intent classification "
            "(non-deterministic outputs, rate-limits under load, added ~300ms latency per call)."
        ),
    }

    # Push aggregated analytics to S3
    s3_key = None
    try:
        from services.ml.prediction_logger import log_conversation_analytics
        log_conversation_analytics(
            conversation_id=conversation_id,
            user_id=current_user_id,
            total_messages=total,
            emotion_distribution=emotion_dist,
            dialogue_act_distribution=act_dist,
            intent_distribution=intent_dist,
            avg_emotion_confidence=avg_em_conf,
            avg_act_confidence=avg_act_conf,
            intent_model_properties=intent_model_props,
        )
        s3_key = f"ml-analytics/{conversation_id}/"
    except Exception:
        pass

    return ConversationAnalyticsResponse(
        conversation_id=conversation_id,
        total_messages=total,
        emotion_distribution={
            "counts": emotion_dist,
            "percentages": {k: round(v / max(count_with_nlp, 1) * 100, 1) for k, v in emotion_dist.items()},
            "dominant": max(emotion_dist, key=emotion_dist.get) if emotion_dist else "unknown",
        },
        dialogue_act_distribution={
            "counts": act_dist,
            "percentages": {k: round(v / max(count_with_nlp, 1) * 100, 1) for k, v in act_dist.items()},
            "dominant": max(act_dist, key=act_dist.get) if act_dist else "unknown",
        },
        intent_distribution={
            "counts": intent_dist,
            "percentages": {k: round(v / max(total, 1) * 100, 1) for k, v in intent_dist.items()},
            "dominant": max(intent_dist, key=intent_dist.get) if intent_dist else "unknown",
        },
        avg_emotion_confidence=round(avg_em_conf, 4),
        avg_act_confidence=round(avg_act_conf, 4),
        intent_model_properties=intent_model_props,
        s3_key=s3_key,
    )
