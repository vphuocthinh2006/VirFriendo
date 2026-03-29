import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID, uuid4

import chess
import chess.engine
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.agent_service.llm.client import generate
from services.core.security import get_current_user_id

router = APIRouter(prefix="/game", tags=["Game"])

_PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


@dataclass
class ChessSession:
    session_id: str
    user_id: UUID
    user_color: Literal["white", "black"]
    bot_level: int
    board: chess.Board = field(default_factory=chess.Board)
    moves: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


_CHESS_SESSIONS: dict[str, ChessSession] = {}


class ChessNewRequest(BaseModel):
    user_color: Literal["white", "black"] = "white"
    bot_level: int = Field(default=3, ge=1, le=10)


class ChessMoveRequest(BaseModel):
    session_id: str
    move_uci: str


class ChessReviewRequest(BaseModel):
    session_id: str


class ChessReviewResponse(BaseModel):
    session_id: str
    status: str
    review_text: str
    stats: dict[str, Any]


def _user_turn(board: chess.Board, user_color: Literal["white", "black"]) -> bool:
    return board.turn == (chess.WHITE if user_color == "white" else chess.BLACK)


def _material_score(board: chess.Board, user_color: Literal["white", "black"]) -> int:
    white_score = 0
    black_score = 0
    for piece_type, val in _PIECE_VALUES.items():
        white_score += len(board.pieces(piece_type, chess.WHITE)) * val
        black_score += len(board.pieces(piece_type, chess.BLACK)) * val
    return (white_score - black_score) if user_color == "white" else (black_score - white_score)


def _engine_path() -> str:
    return (os.environ.get("STOCKFISH_PATH") or "").strip()


def _score_to_cp(score: chess.engine.PovScore) -> int:
    if score.is_mate():
        mate = score.mate()
        if mate is None:
            return 0
        sign = 1 if mate > 0 else -1
        # Keep mate value finite but dominant over cp.
        return sign * (10000 - min(abs(mate), 100))
    cp = score.score()
    return int(cp or 0)


def _evaluate_cp(board: chess.Board, user_color: Literal["white", "black"], think_s: float = 0.12) -> int:
    sf = _engine_path()
    pov = chess.WHITE if user_color == "white" else chess.BLACK
    if sf:
        try:
            with chess.engine.SimpleEngine.popen_uci(sf) as engine:
                info = engine.analyse(board, chess.engine.Limit(time=max(0.05, think_s)))
                score = info.get("score")
                if score is not None:
                    return _score_to_cp(score.pov(pov))
        except Exception:
            pass
    # Fallback: rough material estimate converted to cp.
    return _material_score(board, user_color) * 100


def _pick_fallback_bot_move(board: chess.Board) -> chess.Move:
    legal = list(board.legal_moves)
    if not legal:
        raise HTTPException(status_code=409, detail="No legal moves for bot")
    captures_or_checks: list[chess.Move] = []
    for mv in legal:
        if board.is_capture(mv):
            captures_or_checks.append(mv)
            continue
        board.push(mv)
        gives_check = board.is_check()
        board.pop()
        if gives_check:
            captures_or_checks.append(mv)
    pool = captures_or_checks or legal
    return random.choice(pool)


def _pick_bot_move(board: chess.Board, level: int) -> chess.Move:
    sf = _engine_path()
    if sf:
        try:
            with chess.engine.SimpleEngine.popen_uci(sf) as engine:
                think_s = min(0.08 + (level * 0.04), 0.6)
                result = engine.play(board, chess.engine.Limit(time=think_s))
                if result.move:
                    return result.move
        except Exception:
            pass
    return _pick_fallback_bot_move(board)


def _push_tracked_move(session: ChessSession, move: chess.Move, side: Literal["user", "bot"]) -> None:
    board = session.board
    score_before = _material_score(board, session.user_color)
    san = board.san(move)
    eval_before_cp = _evaluate_cp(board, session.user_color)
    board.push(move)
    score_after = _material_score(board, session.user_color)
    eval_after_cp = _evaluate_cp(board, session.user_color)
    session.moves.append(
        {
            "side": side,
            "uci": move.uci(),
            "san": san,
            "material_delta": score_after - score_before,
            "eval_before_cp": eval_before_cp,
            "eval_after_cp": eval_after_cp,
            "eval_delta_cp": eval_after_cp - eval_before_cp,
            "fen_after": board.fen(),
        }
    )


def _winner_from_result(result: str, user_color: Literal["white", "black"]) -> str | None:
    if result == "1/2-1/2":
        return "draw"
    if result == "1-0":
        return "user" if user_color == "white" else "bot"
    if result == "0-1":
        return "user" if user_color == "black" else "bot"
    return None


def _serialize_session(session: ChessSession) -> dict[str, Any]:
    board = session.board
    status = "finished" if board.is_game_over(claim_draw=True) else "active"
    result = board.result(claim_draw=True) if status == "finished" else None
    return {
        "session_id": session.session_id,
        "status": status,
        "user_color": session.user_color,
        "bot_level": session.bot_level,
        "turn": "white" if board.turn == chess.WHITE else "black",
        "fen": board.fen(),
        "legal_moves": [mv.uci() for mv in board.legal_moves],
        "last_move": session.moves[-1] if session.moves else None,
        "moves_count": len(session.moves),
        "result": result,
        "winner": _winner_from_result(result, session.user_color) if result else None,
    }


def _review_stats(session: ChessSession) -> dict[str, Any]:
    user_moves = [m for m in session.moves if m.get("side") == "user"]
    captures = sum(1 for m in user_moves if "x" in str(m.get("san") or ""))
    checks = sum(1 for m in user_moves if "+" in str(m.get("san") or "") or "#" in str(m.get("san") or ""))
    castles = sum(1 for m in user_moves if "O-O" in str(m.get("san") or ""))
    inaccuracy = sum(1 for m in user_moves if float(m.get("eval_delta_cp") or 0) <= -60)
    mistakes = sum(1 for m in user_moves if float(m.get("eval_delta_cp") or 0) <= -120)
    blunders = sum(1 for m in user_moves if float(m.get("eval_delta_cp") or 0) <= -250)
    best = None
    if user_moves:
        best = max(user_moves, key=lambda m: float(m.get("material_delta") or -999))
    top_mistakes = sorted(
        [m for m in user_moves if float(m.get("eval_delta_cp") or 0) <= -60],
        key=lambda m: float(m.get("eval_delta_cp") or 0),
    )[:3]
    key_mistakes = [
        {
            "san": m.get("san"),
            "uci": m.get("uci"),
            "eval_delta_cp": m.get("eval_delta_cp"),
            "material_delta": m.get("material_delta"),
        }
        for m in top_mistakes
    ]
    board = session.board
    result = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else "*"
    avg_eval_delta = 0.0
    if user_moves:
        avg_eval_delta = round(
            sum(float(m.get("eval_delta_cp") or 0) for m in user_moves) / max(1, len(user_moves)),
            2,
        )

    training_focus: list[str] = []
    if blunders >= 2:
        training_focus.append("Giảm blunder: kiểm tra quân treo và nước phản công trước khi đi.")
    if castles == 0 and len(user_moves) >= 8:
        training_focus.append("Nhập thành sớm hơn để an toàn vua.")
    if checks == 0 and captures <= 1:
        training_focus.append("Tăng chủ động chiến thuật: tìm đòn đôi, ghim, chiếu đôi.")
    if not training_focus:
        training_focus.append("Ổn định nhịp: mỗi nước tự hỏi đối thủ đang dọa gì.")
    return {
        "result": result,
        "user_moves": len(user_moves),
        "captures": captures,
        "checks": checks,
        "castles": castles,
        "inaccuracy_like_moves": inaccuracy,
        "mistake_like_moves": mistakes,
        "blunder_like_moves": blunders,
        "avg_eval_delta_cp": avg_eval_delta,
        "best_move_san": best.get("san") if best else None,
        "best_move_gain": best.get("material_delta") if best else None,
        "key_mistakes": key_mistakes,
        "training_focus": training_focus,
    }


async def _generate_review_text(stats: dict[str, Any], user_color: str) -> str:
    system = (
        "Bạn là AI coach cờ vua thân thiện, nói tiếng Việt tự nhiên, ngắn gọn, thực tế. "
        "Hãy nhận xét phong cách chơi và đưa 3 gợi ý cải thiện."
    )
    prompt = (
        f"Màu quân của người chơi: {user_color}\n"
        f"Stats: {stats}\n"
        "Trả lời theo format:\n"
        "1) Nhận xét tổng quan (2-3 câu)\n"
        "2) Điểm làm tốt (1-2 ý)\n"
        "3) Cần cải thiện (2-3 ý)\n"
        "4) Key mistakes (nêu SAN của 1-3 nước lỗi nặng nhất nếu có)\n"
        "5) Bài tập trận sau (1 ý cụ thể)\n"
    )
    text = await generate(system, prompt)
    if text:
        return text.strip()
    return (
        "Nhận xét tổng quan: Nhịp chơi khá ổn, nhưng có vài nước làm tụt lợi thế nhanh nên thế trận bị đảo chiều.\n"
        "Điểm làm tốt: Bạn vẫn chủ động tìm cơ hội bắt quân và duy trì áp lực ở trung cuộc.\n"
        "Cần cải thiện: Giảm các nước tụt eval lớn, ưu tiên an toàn vua sớm, và luôn kiểm tra phản đòn ngay sau nước mình định đi.\n"
        "Key mistakes: Ưu tiên xem lại các nước có eval_delta_cp <= -120 trong mục thống kê.\n"
        "Bài tập trận sau: Trước mỗi nước, dừng 3 giây để tự hỏi 'đối thủ đang dọa gì?'."
    )


def _get_session_or_404(session_id: str, user_uuid: UUID) -> ChessSession:
    sess = _CHESS_SESSIONS.get(session_id)
    if not sess or sess.user_id != user_uuid:
        raise HTTPException(status_code=404, detail="Không tìm thấy chess session")
    return sess


@router.post("/chess/new")
async def new_chess_game(
    request: ChessNewRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    user_uuid = UUID(current_user_id)
    sess_id = str(uuid4())
    session = ChessSession(
        session_id=sess_id,
        user_id=user_uuid,
        user_color=request.user_color,
        bot_level=request.bot_level,
        board=chess.Board(),
    )
    # If user chooses black, bot plays the first move.
    if request.user_color == "black" and not session.board.is_game_over(claim_draw=True):
        bot_move = _pick_bot_move(session.board, request.bot_level)
        _push_tracked_move(session, bot_move, "bot")
    _CHESS_SESSIONS[sess_id] = session
    return _serialize_session(session)


@router.get("/chess/state/{session_id}")
async def chess_state(
    session_id: str,
    current_user_id: str = Depends(get_current_user_id),
):
    user_uuid = UUID(current_user_id)
    session = _get_session_or_404(session_id, user_uuid)
    return _serialize_session(session)


@router.post("/chess/move")
async def chess_move(
    request: ChessMoveRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    user_uuid = UUID(current_user_id)
    session = _get_session_or_404(request.session_id, user_uuid)
    board = session.board
    if board.is_game_over(claim_draw=True):
        return _serialize_session(session)
    if not _user_turn(board, session.user_color):
        raise HTTPException(status_code=409, detail="Chưa tới lượt bạn")
    try:
        move = chess.Move.from_uci(request.move_uci.strip().lower())
    except Exception:
        raise HTTPException(status_code=400, detail="Nước đi không hợp lệ")
    if move not in board.legal_moves:
        raise HTTPException(status_code=400, detail="Nước đi không hợp lệ")
    _push_tracked_move(session, move, "user")

    if not board.is_game_over(claim_draw=True):
        bot_move = _pick_bot_move(board, session.bot_level)
        _push_tracked_move(session, bot_move, "bot")
    return _serialize_session(session)


@router.post("/chess/review", response_model=ChessReviewResponse)
async def chess_review(
    request: ChessReviewRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    user_uuid = UUID(current_user_id)
    session = _get_session_or_404(request.session_id, user_uuid)
    stats = _review_stats(session)
    status = "finished" if session.board.is_game_over(claim_draw=True) else "active"
    review_text = await _generate_review_text(stats, session.user_color)
    return ChessReviewResponse(
        session_id=session.session_id,
        status=status,
        review_text=review_text,
        stats=stats,
    )

