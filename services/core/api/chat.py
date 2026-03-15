from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from uuid import UUID

from services.core.database import get_db
from services.core.models import Conversation, Message
from services.core.security import get_current_user_id
from pydantic import BaseModel
from pydantic import ConfigDict

from langchain_core.messages import HumanMessage, AIMessage
from services.agent_service.graph.workflow import graph_app
from services.core.context import get_conversation_context, MAX_CONTEXT_MESSAGES

router = APIRouter(prefix="/chat", tags=["Chat"])

# Schema nhận tin nhắn
class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None  # None = tạo conversation mới

# Schema trả về
class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    detected_intent: str | None = None
    detected_emotion: str | None = None
    avatar_action: str | None = None
    bibliotherapy_suggestion: str | None = None

@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user_id),  # Xác thực JWT
    db: AsyncSession = Depends(get_db)
):
    # BƯỚC 1: Lấy hoặc tạo mới Conversation
    user_uuid = UUID(current_user_id)
    if request.conversation_id:
        try:
            conv_id = UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
        query = select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_uuid)
        result = await db.execute(query)
        conversation = result.scalars().first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc hội thoại")
    else:
        # Hội thoại mới: đặt tiêu đề = nội dung tin đầu (cắt 80 ký tự)
        title = (request.message[:80] + "…") if len(request.message) > 80 else request.message.strip() or "Hội thoại mới"
        conversation = Conversation(user_id=user_uuid, title=title)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)

    # BƯỚC 2: Lưu tin nhắn user vào DB
    # user_msg = Message(conversation_id=..., role="user", content=request.message)
    user_msg = Message(conversation_id=conversation.id, role="user", content=request.message)
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # BƯỚC 3: Tạo phản hồi AI (dùng LangGraph) — đưa lịch sử gần nhất từ DB vào context
    history = await get_conversation_context(conversation.id, db, max_messages=MAX_CONTEXT_MESSAGES)
    lc_messages = []
    for h in history:
        if h.get("role") == "assistant":
            lc_messages.append(AIMessage(content=h.get("content") or ""))
        else:
            lc_messages.append(HumanMessage(content=h.get("content") or ""))
    # Nếu không có history (conv mới), history đã gồm tin vừa gửi vì ta đã commit user_msg ở trên
    if not lc_messages:
        lc_messages = [HumanMessage(content=request.message)]

    initial_state = {
        "messages": lc_messages,
    }

    final_state = await graph_app.ainvoke(initial_state)
    
    # Lấy tin nhắn cuối cùng do AI sinh ra (nằm ở cuối list messages)
    bot_reply_message = final_state["messages"][-1]
    bot_reply = bot_reply_message.content
    
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

    # Cập nhật tiêu đề mỗi 21 tin (theo tin user vừa gửi)
    count_result = await db.execute(select(func.count(Message.id)).where(Message.conversation_id == conversation.id))
    total = count_result.scalar() or 0
    if total > 0 and total % 21 == 0:
        conversation.title = (request.message[:80] + "…") if len(request.message) > 80 else request.message.strip()
        await db.commit()

    # BƯỚC 5: Trả về response
    return ChatResponse(
        conversation_id=str(conversation.id), 
        reply=bot_reply,
        detected_intent=intent,
        detected_emotion=emotion,
        avatar_action=avatar_action,
        bibliotherapy_suggestion=bibliotherapy
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
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Lấy danh sách tất cả conversations của user hiện tại"""
    user_uuid = UUID(current_user_id)
    query = select(Conversation).where(Conversation.user_id == user_uuid)
    result = await db.execute(query)
    conversations = result.scalars().all()
    return [ConversationSummary.model_validate(conv) for conv in conversations]


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

