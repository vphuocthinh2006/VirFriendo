from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.core.database import get_db
from services.core.models import DiaryEntry
from services.core.security import get_current_user_id

router = APIRouter(prefix="/diary", tags=["Diary"])


class DiaryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=20000)
    agent_id: str | None = Field(None, max_length=64)


class DiaryRow(BaseModel):
    id: UUID
    content: str
    agent_id: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[DiaryRow])
async def list_diary(
    agent_id: str | None = None,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = UUID(current_user_id)
    q = select(DiaryEntry).where(DiaryEntry.user_id == user_uuid)
    if agent_id:
        q = q.where(DiaryEntry.agent_id == agent_id)
    q = q.order_by(DiaryEntry.created_at.desc()).limit(200)
    result = await db.execute(q)
    rows = result.scalars().all()
    return [DiaryRow.model_validate(r) for r in rows]


@router.post("", response_model=DiaryRow, status_code=201)
async def create_diary(
    body: DiaryCreate,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    user_uuid = UUID(current_user_id)
    aid = (body.agent_id or "").strip() or None
    entry = DiaryEntry(user_id=user_uuid, agent_id=aid, content=body.content.strip())
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return DiaryRow.model_validate(entry)


@router.delete("/{entry_id}", status_code=204)
async def delete_diary(
    entry_id: str,
    current_user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        eid = UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")
    user_uuid = UUID(current_user_id)
    res = await db.execute(
        delete(DiaryEntry).where(DiaryEntry.id == eid, DiaryEntry.user_id == user_uuid)
    )
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Not found")
    await db.commit()
