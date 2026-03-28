import asyncio
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
from services.core.chess_platforms import fetch_lichess_daily_puzzle
from services.core.security import get_current_user_id

router = APIRouter(prefix="/game", tags=["Game"])

# Thang ELO giao diện (bot yếu → mạnh). UI cố định 350–1250.
BOT_ELO_MIN = 350
BOT_ELO_MAX = 1250
# Stockfish UCI_Elo (khi bật UCI_LimitStrength) — biên do engine quy định.
SF_UCI_ELO_MIN = 1320
SF_UCI_ELO_MAX = 3190

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
    bot_elo: int
    board: chess.Board = field(default_factory=chess.Board)
    moves: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


_CHESS_SESSIONS: dict[str, ChessSession] = {}


class ChessNewRequest(BaseModel):
    user_color: Literal["white", "black"] = "white"
    bot_elo: int = Field(default=800, ge=BOT_ELO_MIN, le=BOT_ELO_MAX)


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


def _map_elo_to_stockfish_uci(elo: int) -> int:
    e = max(BOT_ELO_MIN, min(BOT_ELO_MAX, elo))
    return int(
        SF_UCI_ELO_MIN
        + (e - BOT_ELO_MIN) * (SF_UCI_ELO_MAX - SF_UCI_ELO_MIN) / (BOT_ELO_MAX - BOT_ELO_MIN)
    )


def _elo_to_movetime_fallback(elo: int) -> float:
    """Khi Stockfish không hỗ trợ UCI_Elo — thời suy nghĩ tăng dần theo ELO."""
    e = max(BOT_ELO_MIN, min(BOT_ELO_MAX, elo))
    t = 0.06 + (e - BOT_ELO_MIN) / (BOT_ELO_MAX - BOT_ELO_MIN) * 0.48
    return min(0.65, max(0.05, t))


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


def _evaluate_cp_engine(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    user_color: Literal["white", "black"],
    think_s: float = 0.12,
) -> int:
    """Đánh giá thế cờ theo góc nhìn người chơi (cp), dùng engine đã mở sẵn."""
    pov = chess.WHITE if user_color == "white" else chess.BLACK
    try:
        info = engine.analyse(board, chess.engine.Limit(time=max(0.05, think_s)))
        score = info.get("score")
        if score is not None:
            return _score_to_cp(score.pov(pov))
    except Exception:
        pass
    return _material_score(board, user_color) * 100


def _evaluate_cp(board: chess.Board, user_color: Literal["white", "black"], think_s: float = 0.12) -> int:
    sf = _engine_path()
    if sf:
        try:
            with chess.engine.SimpleEngine.popen_uci(sf) as engine:
                return _evaluate_cp_engine(engine, board, user_color, think_s)
        except Exception:
            pass
    # Fallback: rough material estimate converted to cp.
    return _material_score(board, user_color) * 100


def _classify_cp_loss(loss: float) -> str:
    """Lichess-style buckets (centipawns)."""
    if loss < 50:
        return "good"
    if loss < 100:
        return "inaccuracy"
    if loss < 200:
        return "mistake"
    return "blunder"


def _stockfish_enrich_review(session: ChessSession) -> dict[str, Any] | None:
    """
    Phân tích từng nước user: so sánh eval sau nước tốt nhất (engine) vs sau nước bạn đi.
    cp_loss = max(0, eval_after_best - eval_after_played) theo góc nhìn user.
    """
    sf = _engine_path()
    if not sf:
        return None
    user_color = session.user_color
    user_rows: list[dict[str, Any]] = []
    insights: list[dict[str, Any]] = []

    with chess.engine.SimpleEngine.popen_uci(sf) as engine:
        try:
            engine.configure({"UCI_LimitStrength": False})
        except Exception:
            pass

        for i, m in enumerate(session.moves):
            if m.get("side") != "user":
                continue
            fb = m.get("fen_before")
            uci = m.get("uci")
            if not isinstance(fb, str) or not isinstance(uci, str):
                continue
            try:
                board = chess.Board(fb)
                played = chess.Move.from_uci(uci.strip().lower())
            except Exception:
                continue
            if played not in board.legal_moves:
                continue

            try:
                raw = engine.analyse(board, chess.engine.Limit(depth=12, time=0.32), multipv=5)
            except Exception:
                continue
            infos = raw if isinstance(raw, list) else [raw]
            if not infos:
                continue
            first = infos[0]
            pv0 = first.get("pv") or []
            if not pv0:
                continue
            best_move = pv0[0]

            best_lines: list[dict[str, Any]] = []
            for j, inf in enumerate(infos):
                pv = inf.get("pv") or []
                if not pv:
                    continue
                bm = pv[0]
                try:
                    san_bm = board.san(bm)
                except Exception:
                    continue
                sc_obj = inf.get("score")
                cp_s: str | None = None
                if sc_obj is not None:
                    pov_t = sc_obj.pov(board.turn)
                    if pov_t.is_mate():
                        mate = pov_t.mate()
                        cp_s = f"Mate in {mate}" if mate is not None else "Mate"
                    else:
                        cp_val = pov_t.score()
                        cp_s = f"{cp_val} cp" if cp_val is not None else None
                best_lines.append({"rank": j + 1, "san": san_bm, "eval_hint": cp_s})

            b_played = board.copy()
            b_played.push(played)
            s_played = _evaluate_cp_engine(engine, b_played, user_color, 0.1)

            b_best = board.copy()
            b_best.push(best_move)
            s_best = _evaluate_cp_engine(engine, b_best, user_color, 0.1)

            cp_loss = max(0.0, float(s_best - s_played))
            cls = _classify_cp_loss(cp_loss)
            try:
                best_san = board.san(best_move)
                played_san = board.san(played)
            except Exception:
                continue

            ply = i + 1
            row: dict[str, Any] = {
                "ply": ply,
                "san": played_san,
                "uci": played.uci(),
                "cp_loss": round(cp_loss, 1),
                "classification": cls,
                "best_move_san": best_san,
                "best_move_uci": best_move.uci(),
                "eval_after_played_cp": s_played,
                "eval_after_best_cp": s_best,
            }
            user_rows.append(row)

            if cp_loss >= 50.0:
                insights.append(
                    {
                        "ply": ply,
                        "your_move_san": played_san,
                        "your_move_uci": played.uci(),
                        "best_move_san": best_san,
                        "best_move_uci": best_move.uci(),
                        "cp_loss": round(cp_loss, 1),
                        "classification": cls,
                        "engine_top_moves": best_lines[:3],
                    }
                )

    if not user_rows:
        return None

    inc = sum(1 for r in user_rows if r["classification"] == "inaccuracy")
    mis = sum(1 for r in user_rows if r["classification"] == "mistake")
    blu = sum(1 for r in user_rows if r["classification"] == "blunder")
    avg_loss = sum(float(r["cp_loss"]) for r in user_rows) / max(1, len(user_rows))

    worst = sorted([r for r in user_rows if r["cp_loss"] >= 50.0], key=lambda x: float(x["cp_loss"]), reverse=True)[:8]
    key_mistakes = [
        {
            "san": r["san"],
            "uci": r["uci"],
            "cp_loss": r["cp_loss"],
            "eval_delta_cp": round(-float(r["cp_loss"]), 1),
            "best_move_san": r["best_move_san"],
            "best_move_uci": r["best_move_uci"],
            "classification": r["classification"],
            "material_delta": 0,
        }
        for r in worst
    ]

    return {
        "user_move_analysis": user_rows,
        "engine_insights": insights[:14],
        "avg_cp_loss": round(avg_loss, 2),
        "inaccuracy_count": inc,
        "mistake_count": mis,
        "blunder_count": blu,
        "key_mistakes": key_mistakes,
    }


def _pick_fallback_bot_move(board: chess.Board, bot_elo: int) -> chess.Move:
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
    strength = (bot_elo - BOT_ELO_MIN) / max(1, (BOT_ELO_MAX - BOT_ELO_MIN))
    strength = max(0.0, min(1.0, strength))
    if random.random() < 0.12 + 0.78 * strength:
        pool = captures_or_checks or legal
    else:
        pool = legal
    return random.choice(pool)


def _pick_bot_move(board: chess.Board, bot_elo: int) -> chess.Move:
    sf = _engine_path()
    if sf:
        try:
            with chess.engine.SimpleEngine.popen_uci(sf) as engine:
                uci_elo = _map_elo_to_stockfish_uci(bot_elo)
                try:
                    engine.configure(
                        {
                            "UCI_LimitStrength": True,
                            "UCI_Elo": uci_elo,
                        }
                    )
                except Exception:
                    engine.configure({})
                    think_s = _elo_to_movetime_fallback(bot_elo)
                    result = engine.play(board, chess.engine.Limit(time=think_s))
                    if result.move:
                        return result.move
                else:
                    result = engine.play(board, chess.engine.Limit(time=0.22, depth=14))
                    if result.move:
                        return result.move
        except Exception:
            pass
    return _pick_fallback_bot_move(board, bot_elo)


def _push_tracked_move(session: ChessSession, move: chess.Move, side: Literal["user", "bot"]) -> None:
    board = session.board
    fen_before = board.fen()
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
            "fen_before": fen_before,
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
    moves_log = [
        {
            "ply": i + 1,
            "side": m.get("side"),
            "san": m.get("san"),
            "uci": m.get("uci"),
        }
        for i, m in enumerate(session.moves)
    ]
    return {
        "session_id": session.session_id,
        "status": status,
        "user_color": session.user_color,
        "bot_elo": session.bot_elo,
        "turn": "white" if board.turn == chess.WHITE else "black",
        "fen": board.fen(),
        "legal_moves": [mv.uci() for mv in board.legal_moves],
        "last_move": session.moves[-1] if session.moves else None,
        "moves_count": len(session.moves),
        "moves_log": moves_log,
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


def _engine_insights_for_mistakes(session: ChessSession, max_positions: int = 3) -> list[dict[str, Any]]:
    """So sánh nước người chơi với top engine lines (Stockfish full strength) trước nước đó — gần với post-game analysis."""
    sf = _engine_path()
    if not sf:
        return []
    user_moves = [m for m in session.moves if m.get("side") == "user"]
    candidates = sorted(
        [m for m in user_moves if float(m.get("eval_delta_cp") or 0) <= -60],
        key=lambda m: float(m.get("eval_delta_cp") or 0),
    )[:max_positions]
    out: list[dict[str, Any]] = []
    for m in candidates:
        fb = m.get("fen_before")
        if not isinstance(fb, str):
            continue
        try:
            b = chess.Board(fb)
        except Exception:
            continue
        your_san = m.get("san")
        try:
            with chess.engine.SimpleEngine.popen_uci(sf) as engine:
                try:
                    engine.configure({"UCI_LimitStrength": False})
                except Exception:
                    pass
                raw = engine.analyse(b, chess.engine.Limit(time=0.4), multipv=3)
        except Exception:
            continue
        infos = raw if isinstance(raw, list) else [raw]
        best_lines: list[dict[str, Any]] = []
        for i, inf in enumerate(infos):
            pv = inf.get("pv") or []
            if not pv:
                continue
            bm = pv[0]
            try:
                san = b.san(bm)
            except Exception:
                continue
            sc_obj = inf.get("score")
            cp_s = None
            if sc_obj is not None:
                pov = sc_obj.pov(b.turn)
                if pov.is_mate():
                    mate = pov.mate()
                    cp_s = f"Mate in {mate}" if mate is not None else "Mate"
                else:
                    cp_val = pov.score()
                    cp_s = f"{cp_val} cp" if cp_val is not None else None
            best_lines.append({"rank": i + 1, "san": san, "eval_hint": cp_s})
        out.append(
            {
                "your_move_san": your_san,
                "engine_top_moves": best_lines[:3],
            }
        )
    return out


async def _generate_review_text(
    stats: dict[str, Any],
    user_color: str,
    *,
    bot_elo: int,
) -> str:
    system = (
        "Bạn là AI coach cờ vua thân thiện, nói tiếng Việt tự nhiên, ngắn gọn, thực tế. "
        "Khi có user_move_analysis: mỗi nước có cp_loss (centipawn), classification (good/inaccuracy/mistake/blunder), "
        "best_move_san (nước engine tốt nhất tại thời điểm đó). So sánh SAN người chơi với best_move_san — không bịa nước không có trong dữ liệu. "
        "Nếu engine_analysis_available == false hoặc engine_insights rỗng, nói rõ phân tích chi tiết cần STOCKFISH_PATH trên server."
    )
    prompt = (
        f"Màu quân của người chơi: {user_color}\n"
        f"Độ mạnh bot đối thủ (ELO gần với thang chuẩn): khoảng {bot_elo}.\n"
        "Dữ liệu quan trọng:\n"
        "- eval_method: stockfish_cp_loss (nếu có) = phân tích từng nước user: cp_loss, best_move_san vs san; "
        "material_delta_heuristic = chỉ ước lượng thô khi không có Stockfish.\n"
        "- user_move_analysis: danh sách nước user với cp_loss, classification, best_move_san, san.\n"
        "- engine_insights: các vị trí tụt ≥50 cp (có top nước engine).\n"
        "- key_mistakes: worst moves (cp_loss cao).\n"
        "- move_sequence: toàn bộ ván.\n"
        f"Stats: {stats}\n"
        "Trả lời theo format:\n"
        "1) Nhận xét tổng quan (2-3 câu)\n"
        "2) Điểm làm tốt (1-2 ý)\n"
        "3) Cần cải thiện (2-3 ý)\n"
        "4) Phân tích nước sai/tụt lợi thế: dựa user_move_analysis + engine_insights — nêu ít nhất 1–2 ví dụ có "
        "ply/san, best_move_san, cp_loss (nếu có dữ liệu). Nếu không có Stockfish, nói không đủ dữ liệu engine.\n"
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


def _chess_bot_metadata() -> dict[str, Any]:
    sf = _engine_path()
    return {
        "engine": "stockfish" if sf else "heuristic_fallback",
        "stockfish_configured": bool(sf),
        "elo_range": {"min": BOT_ELO_MIN, "max": BOT_ELO_MAX},
        "play": {
            "new_game": "POST /game/chess/new",
            "move": "POST /game/chess/move",
            "review": "POST /game/chess/review",
        },
        "note": "Độ mạnh đối thủ theo ELO (thang gần FIDE/Lichess). Stockfish: UCI_Elo; không có engine thì heuristic. "
        "Post-review: với STOCKFISH_PATH, phân tích từng nước user (cp_loss vs nước engine tốt nhất); không thì material heuristic.",
    }


@router.get("/platforms")
async def game_platforms(current_user_id: str = Depends(get_current_user_id)):
    _ = UUID(current_user_id)
    return {
        "integrations": [
            {
                "id": "lichess.org",
                "kind": "public_api",
                "description": "Puzzle hằng ngày (read-only)",
                "docs": "https://lichess.org/api",
                "endpoint": "GET /game/chess/puzzle/daily",
            },
        ],
        "local_bot": _chess_bot_metadata(),
    }


@router.get("/chess/bot")
async def chess_bot_info(current_user_id: str = Depends(get_current_user_id)):
    _ = UUID(current_user_id)
    return _chess_bot_metadata()


@router.get("/chess/puzzle/daily")
async def chess_daily_puzzle(current_user_id: str = Depends(get_current_user_id)):
    _ = UUID(current_user_id)
    return await fetch_lichess_daily_puzzle()


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
        bot_elo=request.bot_elo,
        board=chess.Board(),
    )
    # If user chooses black, bot plays the first move.
    if request.user_color == "black" and not session.board.is_game_over(claim_draw=True):
        bot_move = _pick_bot_move(session.board, request.bot_elo)
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
        bot_move = _pick_bot_move(board, session.bot_elo)
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
    enriched = await asyncio.to_thread(_stockfish_enrich_review, session)
    if enriched:
        stats["engine_analysis_available"] = True
        stats["eval_method"] = "stockfish_cp_loss"
        stats["user_move_analysis"] = enriched["user_move_analysis"]
        stats["avg_cp_loss"] = enriched["avg_cp_loss"]
        stats["inaccuracy_like_moves"] = enriched["inaccuracy_count"]
        stats["mistake_like_moves"] = enriched["mistake_count"]
        stats["blunder_like_moves"] = enriched["blunder_count"]
        stats["key_mistakes"] = enriched["key_mistakes"]
        stats["engine_insights"] = enriched["engine_insights"]
    else:
        stats["engine_analysis_available"] = False
        stats["eval_method"] = "material_delta_heuristic"
        stats["engine_insights"] = await asyncio.to_thread(_engine_insights_for_mistakes, session)
    stats["move_sequence"] = [
        {"ply": i + 1, "side": m.get("side"), "san": m.get("san")}
        for i, m in enumerate(session.moves)
    ]
    stats["move_sequence_text"] = " ".join(
        f"{m.get('san')}({m.get('side')})" for m in session.moves if m.get("san")
    )
    status = "finished" if session.board.is_game_over(claim_draw=True) else "active"
    review_text = await _generate_review_text(stats, session.user_color, bot_elo=session.bot_elo)
    return ChessReviewResponse(
        session_id=session.session_id,
        status=status,
        review_text=review_text,
        stats=stats,
    )

