"""Agent engagement: likes (per user) and play opens — tracked in DB."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.core.database import get_db
from services.core.models import AgentStat, UserAgentLike
from services.core.security import get_current_user_id, get_optional_user_id

router = APIRouter(prefix="/agents", tags=["agents"])

ALLOWED_AGENT_IDS = frozenset({"tuq27"})


def _require_agent(agent_id: str) -> None:
    if agent_id not in ALLOWED_AGENT_IDS:
        raise HTTPException(status_code=404, detail="Unknown agent")


@router.get("/{agent_id}/stats")
async def get_agent_stats(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str | None = Depends(get_optional_user_id),
):
    _require_agent(agent_id)
    likes_stmt = select(func.count()).select_from(UserAgentLike).where(UserAgentLike.agent_id == agent_id)
    likes = (await db.execute(likes_stmt)).scalar_one()

    stat = (await db.execute(select(AgentStat).where(AgentStat.agent_id == agent_id))).scalar_one_or_none()
    plays = stat.plays if stat else 0

    liked_by_me = False
    if user_id:
        uid = UUID(user_id)
        liked_by_me = (
            await db.execute(
                select(UserAgentLike).where(UserAgentLike.user_id == uid, UserAgentLike.agent_id == agent_id)
            )
        ).scalar_one_or_none() is not None

    return {"likes": int(likes), "plays": plays, "liked_by_me": liked_by_me}


@router.post("/{agent_id}/like")
async def toggle_agent_like(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    _require_agent(agent_id)
    uid = UUID(user_id)

    removed = await db.execute(
        delete(UserAgentLike).where(UserAgentLike.user_id == uid, UserAgentLike.agent_id == agent_id)
    )
    await db.commit()
    if removed.rowcount == 0:
        db.add(UserAgentLike(user_id=uid, agent_id=agent_id))
        await db.commit()

    likes = (await db.execute(select(func.count()).select_from(UserAgentLike).where(UserAgentLike.agent_id == agent_id))).scalar_one()
    liked = (
        await db.execute(select(UserAgentLike).where(UserAgentLike.user_id == uid, UserAgentLike.agent_id == agent_id))
    ).scalar_one_or_none() is not None

    stat = (await db.execute(select(AgentStat).where(AgentStat.agent_id == agent_id))).scalar_one_or_none()
    plays = stat.plays if stat else 0

    return {"likes": int(likes), "plays": plays, "liked_by_me": liked}


@router.post("/{agent_id}/play")
async def record_agent_play(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    _require_agent(agent_id)

    stat = (await db.execute(select(AgentStat).where(AgentStat.agent_id == agent_id))).scalar_one_or_none()
    if stat is None:
        stat = AgentStat(agent_id=agent_id, plays=0)
        db.add(stat)
        await db.flush()
    stat.plays += 1
    await db.commit()
    await db.refresh(stat)

    likes = (await db.execute(select(func.count()).select_from(UserAgentLike).where(UserAgentLike.agent_id == agent_id))).scalar_one()
    uid = UUID(user_id)
    liked_by_me = (
        await db.execute(select(UserAgentLike).where(UserAgentLike.user_id == uid, UserAgentLike.agent_id == agent_id))
    ).scalar_one_or_none() is not None

    return {"likes": int(likes), "plays": stat.plays, "liked_by_me": liked_by_me}
