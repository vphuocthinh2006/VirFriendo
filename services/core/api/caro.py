"""
Caro / Gomoku-style: lưới n×n, cần k quân liên tiếp (mặc định k=min(5,n), n≤3 thì k=n).
Bot: thắng ngay → chặn user thắng → điểm nước (mối đe dọa + trung tâm).
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.agent_service.llm.client import generate
from services.core.security import get_current_user_id

router = APIRouter(prefix="/game/caro", tags=["Caro"])

CARO_GRID_MIN = 3
CARO_GRID_MAX = 15
CARO_GRID_ALLOWED = (3, 5, 7, 9, 11, 15)

_DIRS = ((0, 1), (1, 0), (1, 1), (1, -1))


def _default_win_length(n: int) -> int:
    if n <= 3:
        return n
    return min(5, n)


def _other(p: int) -> int:
    return 2 if p == 1 else 1


def _winner_at(board: list[list[int]], n: int, k: int) -> int | None:
    """Trả về 1, 2 nếu có người thắng; None nếu chưa kết thúc; 0 nếu hòa (đầy bàn)."""
    for r in range(n):
        for c in range(n):
            v = board[r][c]
            if v == 0:
                continue
            for dr, dc in _DIRS:
                rr, cc = r + (k - 1) * dr, c + (k - 1) * dc
                if not (0 <= rr < n and 0 <= cc < n):
                    continue
                ok = True
                for i in range(k):
                    if board[r + i * dr][c + i * dc] != v:
                        ok = False
                        break
                if ok:
                    return v
    if all(board[r][c] != 0 for r in range(n) for c in range(n)):
        return 0
    return None


def _max_run_from(board: list[list[int]], n: int, r: int, c: int, player: int) -> int:
    best = 0
    for dr, dc in _DIRS:
        length = 1
        tr, tc = r + dr, c + dc
        while 0 <= tr < n and 0 <= tc < n and board[tr][tc] == player:
            length += 1
            tr += dr
            tc += dc
        tr, tc = r - dr, c - dc
        while 0 <= tr < n and 0 <= tc < n and board[tr][tc] == player:
            length += 1
            tr -= dr
            tc -= dc
        best = max(best, length)
    return best


def _line_strength(board: list[list[int]], n: int, k: int, r: int, c: int, player: int) -> int:
    """Điểm nước giả định đặt (r,c) cho player: tổng mạnh theo 4 hướng (đếm chuỗi)."""
    if board[r][c] != 0:
        return -10**9
    board[r][c] = player
    score = 0
    for dr, dc in _DIRS:
        length = 1
        tr, tc = r + dr, c + dc
        while 0 <= tr < n and 0 <= tc < n and board[tr][tc] == player:
            length += 1
            tr += dr
            tc += dc
        tr, tc = r - dr, c - dc
        while 0 <= tr < n and 0 <= tc < n and board[tr][tc] == player:
            length += 1
            tr -= dr
            tc -= dc
        if length >= k:
            score += 10**6
        else:
            score += length**4
    board[r][c] = 0
    return score


def _pick_bot_move(board: list[list[int]], n: int, k: int, bot: int, user: int) -> tuple[int, int]:
    empties = [(r, c) for r in range(n) for c in range(n) if board[r][c] == 0]
    if not empties:
        raise HTTPException(status_code=409, detail="Bàn đầy")

    for r, c in empties:
        board[r][c] = bot
        w = _winner_at(board, n, k)
        board[r][c] = 0
        if w == bot:
            return (r, c)

    for r, c in empties:
        board[r][c] = user
        w = _winner_at(board, n, k)
        board[r][c] = 0
        if w == user:
            return (r, c)

    center = (n - 1) / 2.0
    scored: list[tuple[float, int, int]] = []
    for r, c in empties:
        off = abs(r - center) + abs(c - center)
        s = float(_line_strength(board, n, k, r, c, bot)) + 80.0 / (1.0 + off)
        s += 0.3 * float(_line_strength(board, n, k, r, c, user))
        scored.append((s, r, c))
    scored.sort(key=lambda x: -x[0])
    top = scored[0][0]
    pool = [x for x in scored if x[0] >= top - 1e-6]
    pick = random.choice(pool)
    return (pick[1], pick[2])


@dataclass
class CaroSession:
    session_id: str
    user_id: UUID
    n: int
    k: int
    user_piece: int
    board: list[list[int]] = field(default_factory=list)
    moves: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


_CARO_SESSIONS: dict[str, CaroSession] = {}


class CaroNewRequest(BaseModel):
    grid_size: int = Field(default=5, ge=CARO_GRID_MIN, le=CARO_GRID_MAX)
    win_length: int | None = Field(
        default=None,
        description="Số quân liên tiếp để thắng; None = mặc định theo grid",
    )
    user_stone: Literal["x", "o"] = "x"


class CaroMoveRequest(BaseModel):
    session_id: str
    row: int = Field(ge=0)
    col: int = Field(ge=0)


class CaroReviewRequest(BaseModel):
    session_id: str


class CaroReviewResponse(BaseModel):
    session_id: str
    status: str
    review_text: str
    stats: dict[str, Any]


def _user_wins(session: CaroSession, winner: int | None) -> str | None:
    if winner is None or winner == 0:
        return "draw" if winner == 0 else None
    up = session.user_piece
    if winner == up:
        return "user"
    return "bot"


def _serialize_caro(session: CaroSession) -> dict[str, Any]:
    n = session.n
    w = _winner_at(session.board, n, session.k)
    status = "finished" if w is not None else "active"
    bot = _other(session.user_piece)
    next_p = session.user_piece if (len(session.moves) % 2 == 0) else bot
    if status == "finished":
        next_p = session.user_piece

    def cell(v: int) -> str | None:
        if v == 0:
            return None
        return "x" if v == 1 else "o"

    return {
        "session_id": session.session_id,
        "status": status,
        "n": n,
        "k": session.k,
        "user_stone": "x" if session.user_piece == 1 else "o",
        "bot_stone": "o" if session.user_piece == 1 else "x",
        "next_stone": "x" if next_p == 1 else "o",
        "turn": "user" if (status == "active" and _is_user_turn(session)) else ("bot" if status == "active" else "none"),
        "board": [[cell(session.board[r][c]) for c in range(n)] for r in range(n)],
        "winner": _user_wins(session, w),
        "result": "draw" if w == 0 else ("x" if w == 1 else "o") if w else None,
        "moves_count": len(session.moves),
        "moves_log": list(session.moves),
    }


def _is_user_turn(session: CaroSession) -> bool:
    bot = _other(session.user_piece)
    x_first = True
    if x_first:
        first = 1
    else:
        first = 1
    ply = len(session.moves)
    if ply == 0:
        to_move = 1
    else:
        to_move = 1 if ply % 2 == 0 else 2
    return to_move == session.user_piece


def _review_stats_caro(session: CaroSession) -> dict[str, Any]:
    user = session.user_piece
    bot = _other(user)
    user_moves = [m for m in session.moves if m.get("side") == "user"]
    bot_moves = [m for m in session.moves if m.get("side") == "bot"]
    w = _winner_at(session.board, session.n, session.k)
    winner = _user_wins(session, w)

    best_run_user = 0
    for m in user_moves:
        r, c = int(m["row"]), int(m["col"])
        best_run_user = max(best_run_user, _max_run_from(session.board, session.n, r, c, user))

    opening_center = False
    if user_moves:
        r0, c0 = int(user_moves[0]["row"]), int(user_moves[0]["col"])
        mid = (session.n - 1) / 2
        opening_center = abs(r0 - mid) <= 1 and abs(c0 - mid) <= 1

    return {
        "grid_n": session.n,
        "win_k": session.k,
        "user_moves": len(user_moves),
        "bot_moves": len(bot_moves),
        "total_moves": len(session.moves),
        "winner": winner,
        "result": "draw" if w == 0 else winner,
        "user_best_run": best_run_user,
        "opening_near_center": opening_center,
        "move_sequence": [
            {"ply": i + 1, "side": m.get("side"), "row": m.get("row"), "col": m.get("col")}
            for i, m in enumerate(session.moves)
        ],
    }


async def _generate_caro_review_text(stats: dict[str, Any], grid_n: int, win_k: int) -> str:
    system = (
        "Bạn là coach game Caro/Gomoku (tiếng Việt), ngắn gọn, thực tế. "
        "Dựa đúng stats: grid_n, win_k, winner, số nước, user_best_run, opening_near_center, move_sequence — không bịa số."
    )
    prompt = (
        f"Lưới {grid_n}×{grid_n}, cần {win_k} quân liên tiếp để thắng.\n"
        f"Stats: {stats}\n"
        "Trả lời theo format:\n"
        "1) Nhận xét tổng quan (2–3 câu)\n"
        "2) Điểm làm tốt (1–2 ý, có thể nhắc mở quân / trung tâm nếu stats có)\n"
        "3) Cần cải thiện (2–3 ý: phòng thủ, tạo mối, chặn đối thủ)\n"
        "4) Tình huống then chốt: nếu có trong move_sequence — gợi ý 1–2 nhịp; nếu không rõ thì nói chung\n"
        "5) Bài tập trận sau (1 ý cụ thể theo kích thước lưới)\n"
    )
    text = await generate(system, prompt)
    if text:
        return text.strip()
    return (
        f"Tổng quan: Trận {grid_n}×{grid_n} (thắng khi có {win_k} liên tiếp).\n"
        "Điểm tốt: Bạn duy trì nhịp đặt quân ổn định.\n"
        "Cải thiện: Chú ý chặn đường dài của bot và tạo hai ngã ba (fork) khi lưới lớn.\n"
        "Bài tập: Chơi thử lưới nhỏ (3×3 hoặc 5×5) để luyện đọc đe dọa nhanh."
    )


def _get_caro_session(session_id: str, user_uuid: UUID) -> CaroSession:
    s = _CARO_SESSIONS.get(session_id)
    if not s or s.user_id != user_uuid:
        raise HTTPException(status_code=404, detail="Không tìm thấy caro session")
    return s


@router.post("/new")
async def caro_new(request: CaroNewRequest, current_user_id: str = Depends(get_current_user_id)):
    user_uuid = UUID(current_user_id)
    n = request.grid_size
    if n not in CARO_GRID_ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"grid_size phải là một trong {list(CARO_GRID_ALLOWED)}",
        )
    k = request.win_length if request.win_length is not None else _default_win_length(n)
    if k < 3 or k > n:
        raise HTTPException(status_code=400, detail=f"win_length phải từ 3 đến {n}")

    up = 1 if request.user_stone == "x" else 2
    sid = str(uuid4())
    session = CaroSession(
        session_id=sid,
        user_id=user_uuid,
        n=n,
        k=k,
        user_piece=up,
        board=[[0] * n for _ in range(n)],
    )
    _CARO_SESSIONS[sid] = session
    # X đi trước; nếu user chọn O thì bot (X) mở quân.
    if not _is_user_turn(session):
        bot = _other(session.user_piece)
        br, bc = _pick_bot_move(session.board, n, k, bot, session.user_piece)
        session.board[br][bc] = bot
        session.moves.append(
            {"side": "bot", "row": br, "col": bc, "stone": "x" if bot == 1 else "o"}
        )
    return _serialize_caro(session)


@router.get("/state/{session_id}")
async def caro_state(session_id: str, current_user_id: str = Depends(get_current_user_id)):
    user_uuid = UUID(current_user_id)
    session = _get_caro_session(session_id, user_uuid)
    return _serialize_caro(session)


@router.post("/move")
async def caro_move(request: CaroMoveRequest, current_user_id: str = Depends(get_current_user_id)):
    user_uuid = UUID(current_user_id)
    session = _get_caro_session(request.session_id, user_uuid)
    n, k = session.n, session.k
    w = _winner_at(session.board, n, k)
    if w is not None:
        return _serialize_caro(session)
    if not _is_user_turn(session):
        raise HTTPException(status_code=409, detail="Chưa tới lượt bạn")
    r, c = request.row, request.col
    if r >= n or c >= n:
        raise HTTPException(status_code=400, detail="Ô không hợp lệ")
    if session.board[r][c] != 0:
        raise HTTPException(status_code=400, detail="Ô đã có quân")

    session.board[r][c] = session.user_piece
    session.moves.append({"side": "user", "row": r, "col": c, "stone": "x" if session.user_piece == 1 else "o"})

    w = _winner_at(session.board, n, k)
    if w is not None:
        return _serialize_caro(session)

    br, bc = _pick_bot_move(session.board, n, k, _other(session.user_piece), session.user_piece)
    session.board[br][bc] = _other(session.user_piece)
    session.moves.append(
        {"side": "bot", "row": br, "col": bc, "stone": "x" if _other(session.user_piece) == 1 else "o"}
    )

    return _serialize_caro(session)


@router.post("/review", response_model=CaroReviewResponse)
async def caro_review(request: CaroReviewRequest, current_user_id: str = Depends(get_current_user_id)):
    user_uuid = UUID(current_user_id)
    session = _get_caro_session(request.session_id, user_uuid)
    stats = _review_stats_caro(session)
    stats["move_sequence_text"] = " ".join(
        f"{m.get('side')}({m.get('row')},{m.get('col')})" for m in session.moves
    )
    review_text = await _generate_caro_review_text(stats, session.n, session.k)
    w = _winner_at(session.board, session.n, session.k)
    status = "finished" if w is not None else "active"
    return CaroReviewResponse(session_id=session.session_id, status=status, review_text=review_text, stats=stats)
