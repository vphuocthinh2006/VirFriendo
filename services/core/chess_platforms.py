"""
Tích hợp nền tảng cờ công khai (read-only):
- Chess.com Published Data API: https://www.chess.com/news/view/published-data-api
- Lichess HTTP API: https://lichess.org/api

Không có API chính thức để ghép trận trực tiếp trên chess.com từ server bên thứ ba;
bot trong app vẫn chơi local (Stockfish) — các endpoint này phục vụ stats / puzzle / liên kết.
"""
from __future__ import annotations

import re
from typing import Any

import httpx
from fastapi import HTTPException

CHESSCOM_PUB = "https://api.chess.com/pub/player"
LICHESS_API = "https://lichess.org/api"

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{2,50}$")


def normalize_username(raw: str) -> str:
    s = (raw or "").strip()
    if not _USERNAME_RE.match(s):
        raise HTTPException(status_code=400, detail="Username không hợp lệ (2–50 ký tự: chữ, số, _ -)")
    return s.lower()


async def fetch_chesscom_player_bundle(username: str) -> dict[str, Any]:
    u = normalize_username(username)
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        pr = await client.get(f"{CHESSCOM_PUB}/{u}")
        if pr.status_code == 404:
            raise HTTPException(status_code=404, detail="Không tìm thấy người chơi trên Chess.com")
        pr.raise_for_status()
        profile = pr.json()
        st = await client.get(f"{CHESSCOM_PUB}/{u}/stats")
        stats: dict[str, Any] | None
        if st.status_code == 200:
            stats = st.json()
        elif st.status_code == 404:
            stats = None
        else:
            st.raise_for_status()
            stats = None
        return {"source": "chess.com", "username": u, "profile": profile, "stats": stats}


async def fetch_lichess_user(username: str) -> dict[str, Any]:
    u = normalize_username(username)
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        r = await client.get(f"{LICHESS_API}/user/{u}")
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Không tìm thấy người chơi trên Lichess")
        r.raise_for_status()
        data = r.json()
        return {"source": "lichess.org", "username": u, "user": data}


async def fetch_lichess_daily_puzzle() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        r = await client.get(f"{LICHESS_API}/puzzle/daily")
        r.raise_for_status()
        return r.json()
