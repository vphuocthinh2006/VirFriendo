import json
import os
from typing import Any, Dict, List, Optional, Tuple

from services.agent_service.llm.client import generate


JUDGE_SYSTEM = """Bạn là một reviewer cực kỳ khó tính cho câu trả lời dựa trên nguồn tham khảo.

Bạn sẽ được cung cấp:
- user_question
- references (một vài đoạn trích từ Wikipedia/web)
- draft_answer (câu trả lời dự thảo)

Nhiệm vụ:
1) Kiểm tra draft_answer có bịa/đoán chi tiết không có trong references không.
2) Nếu có, trả verdict=reject và nêu ngắn gọn lỗi.
3) Nếu ổn, trả verdict=accept và cho confidence 0..1.

Quy tắc:
- Nếu references HOÀN TOÀN TRỐNG hoặc không liên quan chút nào, verdict=reject.
- Nếu references có ÍT NHẤT một đoạn synopsis/summary/description liên quan đến chủ đề user hỏi, verdict=accept — vì đó chính là dữ liệu hợp lệ, dù ngắn.
- Nếu câu hỏi yêu cầu 'arc/season' cụ thể mà references chỉ là premise chung:
  - verdict=accept nếu user hỏi 'premise/setup' hoặc 'không spoil/khong spoil', hoặc nếu references có synopsis đủ dài (>100 ký tự).
  - verdict=reject chỉ khi references thật sự KHÔNG chứa gì liên quan.
- draft_answer được phép là bản DỊCH SANG TIẾNG VIỆT của nội dung trong references (từ ngữ tiếng Việt có thể khác hoàn toàn, miễn là nội dung tương ứng với references).
- KHÔNG được thêm thông tin mới ngoài references.
- KHÔNG được thêm câu cảm thán/nhận xét cá nhân/lời mời/chất hội thoại/phần hỏi người dùng nếu các nội dung đó không xuất hiện trong references.
- Luôn đảm bảo các thực thể/danh từ riêng/thuật ngữ viết hoa trong references được giữ nguyên (ví dụ: Founding Titan, Rumbling, Fort Salta...). Nếu bị đổi/biến mất thì verdict=reject.

Output: chỉ JSON, không thêm chữ khác:
{"verdict":"accept|reject","confidence":0.0,"reason":"...","fixed_answer":""}

Nếu reject và bạn có thể sửa bằng cách chỉ dùng references, hãy điền fixed_answer.
Nếu reject và không đủ data, fixed_answer để rỗng.
"""


def _enabled() -> bool:
    return (os.environ.get("ENABLE_KNOWLEDGE_JUDGE", "true") or "").strip().lower() in ("1", "true", "yes")


def _safe_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


async def judge_answer(user_question: str, references: str, draft_answer: str) -> Tuple[bool, float, str, str]:
    """
    Returns (accepted, confidence, reason, fixed_answer)
    If judge disabled/unavailable -> accept with low confidence (0.3).
    """
    if not _enabled():
        return True, 0.3, "judge_disabled", ""

    # Fast hard-fail filters for the common "chatty" leakage pattern.
    low = (draft_answer or "").strip().lower()
    if "..." in low:
        return False, 0.0, "judge_disallow_chatty_punctuation", ""
    chatty_markers = [
        "mình nghĩ",
        "mình vừa",
        "mình có thể",
        "bạn cũng",
        "bạn có muốn",
        "bạn muốn",
        "muốn biết",
        "hứng thú",
        "bạn sẽ",
        "mình sẽ",
        "khiến bạn",
    ]
    if any(m in low for m in chatty_markers):
        return False, 0.0, "judge_disallow_chatty_language", ""
    prompt = (
        f"user_question:\n{user_question.strip()}\n\n"
        f"references:\n{references.strip()}\n\n"
        f"draft_answer:\n{draft_answer.strip()}\n"
    )
    raw = await generate(JUDGE_SYSTEM, prompt)
    if not raw:
        return True, 0.3, "judge_no_reply", ""
    data = _safe_json(raw)
    if not data:
        return True, 0.3, "judge_unparseable", ""
    verdict = str(data.get("verdict") or "").strip().lower()
    conf = float(data.get("confidence") or 0.0)
    reason = str(data.get("reason") or "").strip()
    fixed = str(data.get("fixed_answer") or "").strip()
    if verdict == "accept":
        return True, max(0.0, min(conf, 1.0)), reason, fixed
    return False, max(0.0, min(conf, 1.0)), reason, fixed


