"""
Lichess public HTTP API — chỉ dùng puzzle hằng ngày (read-only).
"""
from __future__ import annotations

import httpx
from fastapi import HTTPException

LICHESS_API = "https://lichess.org/api"


def _upstream_http_error(exc: httpx.HTTPError) -> HTTPException:
    if isinstance(exc, httpx.HTTPStatusError):
        return HTTPException(
            status_code=502,
            detail=f"Dịch vụ cờ trả lỗi HTTP {exc.response.status_code}",
        )
    return HTTPException(status_code=502, detail="Không kết nối được dịch vụ cờ ngoài")


async def fetch_lichess_daily_puzzle() -> dict:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(f"{LICHESS_API}/puzzle/daily")
            r.raise_for_status()
            return r.json()
    except httpx.HTTPError as e:
        raise _upstream_http_error(e) from e
