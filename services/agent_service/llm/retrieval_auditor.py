"""
Agent duyệt kết quả search: không hardcode IP — LLM quyết định mục nào đúng chủ đề,
và có thể đề xuất query Tavily tinh chỉnh khi toàn bộ lệch.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from services.agent_service.llm.client import generate


def _enabled() -> bool:
    return (os.environ.get("ENABLE_RETRIEVAL_AUDITOR", "true") or "").strip().lower() in ("1", "true", "yes")


def _parse_json(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


AUDITOR_SYSTEM = """Bạn là agent duyệt kết quả tìm kiếm cho trợ lý giải trí.

Nhiệm vụ: So sánh CÂU HỎI NGƯỜI DÙNG với từng KẾT QUẢ (title, url, snippet). Quyết định mục nào thực sự giúp trả lời đúng trọng tâm (đúng tác phẩm / đúng nhân vật / đúng chủ đề).

Quy tắc:
- Giữ (keep_indices) chỉ mục có liên quan trực tiếp. Loại mục trùng IP sai, nhân vật khác tên, wiki khác franchise, hoặc chỉ trùng từ khóp chung chung.
- Nếu không có mục nào ổn: keep_indices = [], refined_query = chuỗi tìm kiếm mới (tiếng Anh hoặc ngữ cảnh rõ: thêm game/anime/album/năm/viết tắt để phân biệt) — KHÔNG bịa dữ kiện, chỉ làm rõ truy vấn.
- Nếu có vài mục ổn: refined_query có thể là null.
- Nếu cả batch đều lệch: needs_retry = true và refined_query bắt buộc (khác query cũ).

Chỉ trả JSON, không giải thích ngoài JSON:
{"keep_indices":[0,2],"needs_retry":false,"refined_query":null,"reason_short":"..."}

keep_indices: chỉ số 0-based trong danh sách candidates.
"""


def _format_candidates(user_query: str, candidates: List[Dict[str, str]], tool: str) -> str:
    lines = [f"USER_QUESTION:\n{user_query.strip()}\n", f"TOOL: {tool}\n", "CANDIDATES:\n"]
    for i, c in enumerate(candidates):
        title = (c.get("title") or "")[:200]
        url = (c.get("url") or "")[:300]
        sn = (c.get("snippet") or "")[:500].replace("\n", " ")
        lines.append(f"[{i}] title={title}\n    url={url}\n    snippet={sn}\n")
    return "\n".join(lines)


async def audit_search_results(
    user_query: str,
    candidates: List[Dict[str, str]],
    *,
    tool: str,
) -> Tuple[List[Dict[str, str]], Optional[str], str]:
    """
    Returns (filtered_results, refined_query_or_none, reason_short).
    Nếu không bật auditor hoặc lỗi parse → trả nguyên candidates, refined_query=None.
    """
    if not _enabled() or not candidates:
        return candidates, None, "auditor_disabled_or_empty"

    prompt = _format_candidates(user_query, candidates, tool)
    raw = await generate(AUDITOR_SYSTEM, prompt)
    data = _parse_json(raw or "")
    if not data:
        logger.warning("retrieval_auditor: unparseable response")
        return candidates, None, "auditor_unparseable"

    keep = data.get("keep_indices")
    if not isinstance(keep, list):
        return candidates, None, "auditor_bad_indices"

    idx_set = set()
    for x in keep:
        try:
            if isinstance(x, int) and 0 <= x < len(candidates):
                idx_set.add(x)
        except Exception:
            continue

    if not idx_set:
        rq = data.get("refined_query")
        refined = str(rq).strip() if rq is not None else None
        if refined and len(refined) < 3:
            refined = None
        return [], refined, str(data.get("reason_short") or "no_relevant")

    kept = [candidates[i] for i in sorted(idx_set)]
    refined = data.get("refined_query")
    refined_s = str(refined).strip() if refined is not None else None
    if refined_s and len(refined_s) < 3:
        refined_s = None
    needs_retry = bool(data.get("needs_retry"))
    if needs_retry and refined_s:
        return kept, refined_s, str(data.get("reason_short") or "retry_with_refined")
    return kept, None, str(data.get("reason_short") or "ok")
