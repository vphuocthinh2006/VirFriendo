import json
import os
import re
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
- Nếu references chỉ là trang wiki rỗng, template HTML, hoặc lặp category/stub không trả lời trọng tâm câu hỏi, coi như không đủ — verdict=reject (trừ khi draft thừa nhận rõ hạn chế và không bịa thêm).
- Nếu references HOÀN TOÀN TRỐNG hoặc không liên quan chút nào, verdict=reject.
- Nếu references có ÍT NHẤT một đoạn synopsis/summary/description liên quan đến chủ đề user hỏi, verdict=accept — vì đó chính là dữ liệu hợp lệ, dù ngắn.
- Draft phải trả lời ĐÚNG trọng tâm câu hỏi của user. Nếu user hỏi A mà draft nói lan sang B dù đều có trong nguồn, verdict=reject.
- Draft phải là đoạn tiếng Việt hoàn chỉnh (có chủ đề rõ), không được chỉ là nhãn kiểu "You", "User:", không được mở đầu như kịch bản chat thô.
- Nếu draft chứa khẳng định chắc chắn (always, chắc chắn, chắc chắn rằng, chắc kèo, tuyệt đối) nhưng references không đủ mạnh để kết luận chắc chắn, verdict=reject hoặc hạ confidence rất thấp.
- Với câu hỏi kiểu preference/opinion cộng đồng (ví dụ: "fandom thích X hay Y hơn"):
  - verdict=accept nếu references có các ý kiến/nhận xét cộng đồng liên quan (Reddit/community), dù không có câu kết luận trực tiếp "X > Y".
  - draft_answer phải nêu rõ mức chắc chắn và được phép nói "chưa có đồng thuận rõ ràng" nếu nguồn không đủ để chốt tuyệt đối.
- Nếu câu hỏi yêu cầu 'arc/season' cụ thể mà references chỉ là premise chung:
  - verdict=accept nếu user hỏi 'premise/setup' hoặc 'không spoil/khong spoil', hoặc nếu references có synopsis đủ dài (>100 ký tự).
  - verdict=reject chỉ khi references thật sự KHÔNG chứa gì liên quan.
- Câu hỏi tóm tắt cốt truyện / plot / synopsis / storyline (ví dụ Attack on Titan):
  - Nếu references có synopsis, plot summary, description, overview, hoặc đoạn mô tả nhân vật/bối cảnh từ AniList/Wikipedia/Fandom liên quan IP đó → verdict=accept nếu draft dịch/tóm lại đúng các ý đó (không cần trùng từng câu).
  - Chỉ reject nếu references hoàn toàn không nhắc tới tác phẩm/topic user hỏi, hoặc draft bịa chi tiết không có trong references.
- draft_answer được phép là bản DỊCH SANG TIẾNG VIỆT của nội dung trong references (từ ngữ tiếng Việt có thể khác hoàn toàn, miễn là nội dung tương ứng với references).
- KHÔNG được thêm thông tin mới ngoài references.
- KHÔNG được thêm câu cảm thán/nhận xét cá nhân/lời mời/chất hội thoại/phần hỏi người dùng nếu các nội dung đó không xuất hiện trong references.
- Luôn đảm bảo các thực thể/danh từ riêng/thuật ngữ viết hoa trong references được giữ nguyên (ví dụ: Founding Titan, Rumbling, Fort Salta...). Nếu bị đổi/biến mất thì verdict=reject.
- Nếu draft dùng dữ kiện số (mốc thời gian, chapter/season, cấp sức mạnh, tỉ lệ, rank) mà references không nêu, verdict=reject.

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


async def judge_answer(
    user_question: str,
    references: str,
    draft_answer: str,
    *,
    fail_open: bool = False,
    accept_on_reject: bool = False,
) -> Tuple[bool, float, str, str]:
    """
    Returns (accepted, confidence, reason, fixed_answer)
    If judge disabled/unavailable:
    - fail_open=True  -> accept with low confidence
    - fail_open=False -> reject
    """
    if not _enabled():
        if fail_open:
            return True, 0.3, "judge_disabled", ""
        return False, 0.0, "judge_disabled", ""

    # Chỉ chặn ellipsis kiểu placeholder — không chặn "..." trong câu tiếng Việt bình thường.
    raw_da = (draft_answer or "").strip()
    low = raw_da.lower()
    if raw_da in ("...", "…") or re.fullmatch(r"[\s.…]{1,24}", raw_da):
        return False, 0.0, "judge_disallow_empty_placeholder", ""
    chatty_markers = [
        "mình nghĩ",
        "mình vừa",
        "bạn có muốn",
        "muốn biết thêm",
        "hứng thú không",
        "khiến bạn",
    ]
    # Chỉ áp dụng lọc chatty khi bản nháp ngắn (tránh bắn nhầm bản dài có cụm vô hại).
    if len(low) < 220 and any(m in low for m in chatty_markers):
        return False, 0.0, "judge_disallow_chatty_language", ""
    prompt = (
        f"user_question:\n{user_question.strip()}\n\n"
        f"references:\n{references.strip()}\n\n"
        f"draft_answer:\n{draft_answer.strip()}\n"
    )
    raw = await generate(JUDGE_SYSTEM, prompt)
    if not raw:
        if fail_open:
            return True, 0.3, "judge_no_reply", ""
        return False, 0.0, "judge_no_reply", ""
    data = _safe_json(raw)
    if not data:
        if fail_open:
            return True, 0.3, "judge_unparseable", ""
        return False, 0.0, "judge_unparseable", ""
    verdict = str(data.get("verdict") or "").strip().lower()
    conf = float(data.get("confidence") or 0.0)
    reason = str(data.get("reason") or "").strip()
    fixed = str(data.get("fixed_answer") or "").strip()
    if verdict == "accept":
        return True, max(0.0, min(conf, 1.0)), reason, fixed
    # Plot/synopsis: judge often rejects valid grounded drafts when snippets are partial.
    if accept_on_reject:
        da = (draft_answer or "").strip()
        if len(da) >= 40:
            low = da.lower()
            refusal = any(
                m in low
                for m in (
                    "không đủ dữ liệu",
                    "thiếu dữ liệu",
                    "không tìm được",
                    "không lấy được",
                    "dừng lại để tránh",
                    "cannot answer",
                    "i don't have",
                )
            )
            if not refusal:
                return True, 0.42, "accept_on_reject_synopsis:" + reason, fixed
    return False, max(0.0, min(conf, 1.0)), reason, fixed


