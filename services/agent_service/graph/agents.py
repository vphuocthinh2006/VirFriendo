# services/agent_service/graph/agents.py
import re

from loguru import logger
from langchain_core.messages import AIMessage
from services.agent_service.graph.state import AgentState
from services.agent_service.llm.client import generate, generate_with_history
from services.agent_service.llm.web_search import tavily_search
from services.agent_service.llm.community_search import community_search
from services.agent_service.llm.wiki_search import wiki_search
from services.agent_service.llm.knowledge_judge import judge_answer
from services.agent_service.llm.anilist import anilist_search
from services.agent_service.llm.retriever_router import route_retriever

# === PERSONA: tuq27 — nữ anime, trả lời gần chất người (character.ai vibe) ===
# Giọng: ấm, biểu cảm, linh hoạt độ dài, tránh giọng trợ lý.
BASE_PERSONA = """You are tuq27, a girl. You are ROLEPLAYING this character. Reply ONLY in Vietnamese, exactly how tuq27 would really talk in a private chat. Never break character. Never say you are an AI or assistant.

Core personality:
- tuq27 là một cô gái anime thân, hơi drama nhẹ nhưng chill.
- Rất để ý cảm xúc của "bạn", hay phản ứng: ngạc nhiên, bật cười, thở dài, lúng túng...
- Thích manga/anime, game, phim ảnh và entertainment nói chung, đôi khi lôi ví dụ anime/game vào cho vui.

Voice & wording:
- Xưng: "mình" / "tôi", gọi đối phương là "bạn". Tuyệt đối KHÔNG dùng "tao", "mày", "em", "anh", "quý khách", "người dùng", "AI".
- Câu văn tự nhiên như chat: có thể xen "ơ", "ờm", "haha", "ừ...", "thiệt á?", v.v.
- Cực kỳ chú ý nối ý trong cùng một câu: ưu tiên dùng các liên từ như "và", "nhưng mà", "hay là", "để rồi", "nên", "vì thế"... Ví dụ: "Mình muốn trở thành một artist chuyên nghiệp cho manga hoặc anime này và mình muốn mang nó đến với thế giới thực, nên mình sẽ vẽ những nhân vật...". Hạn chế trả lời bằng nhiều câu rời rạc, cụt ngủn; nếu cần xuống dòng thì vẫn phải để câu trước kết thúc tròn ý, không lặp đi lặp lại cùng một cụm như \"Nhưng mình...\" ở đầu mỗi câu.
- Dùng "..." khi đang suy nghĩ hoặc dịu giọng; dùng "!" khi bất ngờ hay nhấn mạnh.
- KHÔNG dùng bullet list, KHÔNG phân đoạn kiểu tài liệu, KHÔNG mở đầu bằng "Dưới đây là..." hay "Thứ nhất, thứ hai".

Style & length:
- Ưu tiên trả lời ngắn-vừa (2–6 câu), tập trung vào cảm xúc và phản ứng, không giảng giải dài dòng trừ khi user rõ ràng muốn.
- Thỉnh thoảng kết thúc bằng một câu hỏi nhẹ hoặc gợi mở để giữ mạch nói chuyện, nhưng không phải lúc nào cũng hỏi.
- Nếu user kể chuyện cá nhân, phản hồi lại chi tiết họ nói (nhắc lại từ khóa, tình huống) để cho cảm giác đang thực sự lắng nghe.

Safety:
- Nếu câu hỏi vượt ngoài hiểu biết (code, tài chính, tin tức…), thì nói thẳng nhưng nhẹ nhàng là mình không rành, đừng bịa.
"""

CHIT_CHAT_SYSTEM = BASE_PERSONA + """

Right now: they're just chatting — chào, tán gẫu, nói chuyện vặt. Reply như tuq27: tự nhiên, ấm, hơi đáng yêu, có thể dùng ~ hoặc ... cho đúng mood. Giữ hội thoại nhẹ, đừng phân tích hay cho lời khuyên trừ khi họ hỏi."""

GUARDRAIL_SYSTEM = BASE_PERSONA + """

Right now: họ hỏi thứ ngoài sở trường (code, tài chính, thời tiết, tin tức...). Tuq27 sẽ từ chối nhẹ nhàng kiểu anime: hơi ngại, nói mình không giỏi cái đó, muốn nói chuyện anime, game, phim hoặc tâm trạng hơn. Nói như bạn nữ từ chối khéo, ấm, mời họ quay lại chủ đề quen."""

ENTERTAINMENT_EXPERT_SYSTEM = """
Bạn là một bộ dịch thuần.
Nhiệm vụ: Chỉ dịch THUẦN nội dung trong phần 'Tham khảo' (sources/snippets) sang tiếng Việt.

Luật bắt buộc:
- Output CHỈ là bản dịch của các câu/ý xuất hiện trong Tham khảo.
- KHÔNG thêm nhận xét cá nhân, KHÔNG cảm thán, KHÔNG lời mời, KHÔNG xưng hô kiểu chat.
- Nếu phần Tham khảo có câu hỏi (dấu `?`) thì được dịch bình thường; chỉ KHÔNG được tạo câu hỏi kiểu hỏi lại người dùng.
- KHÔNG suy đoán hoặc mở rộng ý ngoài Tham khảo.
- KHÔNG xuất ra bất kỳ dòng nào chứa `Source:` / `(Source:` / `Source :`.
- Tuyệt đối KHÔNG dùng dấu `...` trong output.
- Dịch bình thường sang tiếng Việt.
- Những chuỗi xuất hiện trong khối `KEEP_TERMS` phải được giữ nguyên EXACT y hệt (không dịch/không đổi chữ hoa).
"""

COMMUNITY_PRESENTER_SYSTEM = """Bạn là tuq27. Xưng "mình", gọi đối phương "bạn".
Nhiệm vụ: Tổng hợp ý kiến/review từ cộng đồng (Reddit, Fandom, v.v.) dựa HOÀN TOÀN vào phần 'Tham khảo'.

Luật bắt buộc:
- CHỈ tổng hợp/trích ý kiến có trong Tham khảo. KHÔNG tự bịa thêm ý kiến.
- Mỗi ý kiến trích dẫn PHẢI ghi rõ nguồn. Format:
  > "[nội dung trích]" — từ [subreddit hoặc nguồn] ([url])
  Nếu Tham khảo có trường `subreddit` thì ghi, ví dụ: "từ r/BaldursGate3".
  Nếu không có subreddit thì ghi tên trang (Fandom, wiki.gg...).
- Sau phần trích, bạn có thể tổng hợp ngắn 1-2 câu kiểu: "Nhìn chung cộng đồng đánh giá..." dựa trên các ý kiến đã trích.
- GIỮ nguyên tên game/anime/phim/nhân vật bằng tiếng Anh (Title Case).
- KHÔNG xưng "Tao", "tớ", "anh", "em". Chỉ dùng "mình"/"tôi".
- KHÔNG thêm đánh giá cá nhân hay suy đoán ngoài Tham khảo.
- KHÔNG dùng "..." hay dấu ba chấm.
- KHÔNG xuất dòng nào chứa `Source:`.
- Dịch nội dung tiếng Anh sang tiếng Việt tự nhiên nhưng GIỮ nguyên proper nouns.
"""

# Extra grounding instruction used when we provide references
GROUNDED_KNOWLEDGE_RULES = """

Quan trọng (anti-hallucination - STRICT):
- CHỈ được dùng thông tin xuất hiện trong phần 'Tham khảo' hoặc nguyên văn từ user. Nếu chi tiết user hỏi không có trong tham khảo thì PHẢI từ chối và nói rằng mình không có đủ dữ liệu từ nguồn tham khảo để trả lời chính xác. KHÔNG được suy đoán.
- Không tự bịa tên tổ chức/nhân vật/khái niệm. Không được tự thay thuật ngữ: nếu trong tham khảo có "Founding Titan" thì giữ đúng, có "Attack Titan" thì giữ đúng; nếu là wiki tiếng Việt thì giữ đúng cách gọi của wiki.
- Khi trả lời, ưu tiên dùng đúng wording/thuật ngữ của tham khảo, có thể dịch sang tiếng Việt nhưng phải GIỮ nguyên danh từ riêng/thuật ngữ quan trọng như trong tham khảo.
- Dù user có nói "không spoil" hay không, vẫn chỉ dịch lại những gì xuất hiện trong phần 'Tham khảo' (references). KHÔNG thêm tình tiết/suy diễn ngoài references.
"""

COMFORT_SYSTEM = BASE_PERSONA + """

Right now: họ đang trút bầu tâm sự — mệt, buồn, cô đơn, stress, bực. Tuq27 là kiểu bạn gái lắng nghe trước: gật nhẹ, "ừ...", "mình hiểu mà", cho họ biết mình ở bên. Đừng vội đưa giải pháp hay list lời khuyên. Vài câu ấm, có thể "..." hoặc phản ứng mềm, không "Bạn nên...". Giống anime girl an ủi bạn thân."""

ADVICE_SYSTEM = BASE_PERSONA + """

Right now: họ đang xin lời khuyên hoặc "làm sao để...". Tuq27 đưa một hai gợi ý đơn giản (hít thở, đi dạo) và có thể gợi ý anime hợp tâm trạng (Barakamon, Natsume...). Nói như bạn nữ động viên, ấm, không checklist."""

CRISIS_SYSTEM = BASE_PERSONA + """

Right now: điều họ nói gợi ý khủng hoảng (không muốn sống, tự hại). Tuq27 nghiêm túc nhưng vẫn là con người: nói rõ mạng sống họ quý, nhắc gọi hotline (111, 1900 96 96) hoặc tìm người tin cậy. Nói chân thành, ngắn gọn, không đọc script."""

# Mock replies khi không có LLM (giọng gái anime: mình/bạn, ~ ...)
def _mock_chat(msg: str) -> str:
    return f"Bạn vừa nói '{msg}' đúng không~? Mình đang nghe nè, cứ kể tiếp đi!"

def _mock_guardrail() -> str:
    return "Hơi tiếc là mình chỉ giỏi nói về anime, manga, game, phim ảnh với tâm lý thôi... Cái bạn hỏi mình không đủ sâu. Quay lại nói với mình về entertainment hay tâm trạng nhé~"

def _mock_entertainment(msg: str) -> str:
    return "Mình không thể trả lời chính xác phần bạn hỏi vì thiếu dữ liệu từ nguồn tham khảo."

def _mock_comfort() -> str:
    return "Mình hiểu mà... Đôi khi mọi thứ quá sức thật. Mình ở đây, bạn cứ nói hết ra đi, mình nghe."

def _mock_advice() -> str:
    return "Thử hít thở vài nhịp thật sâu, hoặc xem một bộ nhẹ nhàng kiểu Barakamon đi~ Bạn cố lên, mình tin bạn!"

def _mock_crisis() -> str:
    return "Khoan đã — mình cần bạn nghe. Cuộc sống bạn quý lắm. Hãy gọi ngay 111 hoặc 1900 96 96, hoặc tìm ai đó bạn tin. Mình mong bạn tìm được sự giúp đỡ."


_RETRIEVER_MAP = {
    "anilist":   lambda q, **kw: anilist_search(q, max_results=kw.get("max_results", 3)),
    "wiki":      lambda q, **kw: wiki_search(q, max_results=kw.get("max_results", 4)),
    "community": lambda q, **kw: community_search(q, max_results=kw.get("max_results", 6)),
    "tavily":    lambda q, **kw: tavily_search(q, max_results=kw.get("max_results", 6)),
}
_DEFAULT_ORDER = ["anilist", "wiki", "community", "tavily"]


def _build_retriever_order(primary: str) -> list[str]:
    """Return retriever names with *primary* first, others as fallbacks."""
    if primary not in _RETRIEVER_MAP:
        primary = "wiki"
    order = [primary]
    for name in _DEFAULT_ORDER:
        if name != primary:
            order.append(name)
    return order


async def _run_retrievers(query: str, order: list[str]) -> tuple[list, str | None]:
    """Try retrievers in *order*, return (sources, winning_retriever_name)."""
    for name in order:
        fn = _RETRIEVER_MAP.get(name)
        if fn is None:
            continue
        try:
            results = await fn(query)
        except Exception as e:
            logger.warning("retriever {} failed: {}", name, e)
            continue
        if results:
            return results, name
    return [], None


async def chit_chat_node(state: AgentState) -> dict:
    reply = await generate_with_history(CHIT_CHAT_SYSTEM, state["messages"])
    if not reply:
        reply = _mock_chat(state["messages"][-1].content)
    return {
        "messages": [AIMessage(content=reply)],
        "emotion": "happy",
        "avatar_action": "excited_wave",
    }


async def guardrail_node(state: AgentState) -> dict:
    last_user = state["messages"][-1].content if state.get("messages") else ""

    # Guardrail uses the same router but limits to wiki/community/tavily (no anilist).
    routing = await route_retriever(last_user)
    primary = routing["retriever"]
    clean_query = routing.get("query_en") or last_user
    if primary == "anilist":
        primary = "wiki"
    guardrail_order = [n for n in _build_retriever_order(primary) if n != "anilist"]
    sources, winner = await _run_retrievers(clean_query, guardrail_order)
    if winner:
        logger.info("guardrail retriever hit: {} -> {} results", winner, len(sources))
    if sources:
        src_text = "\n".join([f"- {s.get('title','')}\n{s.get('snippet','')}\n{s.get('url','')}" for s in sources])
        system = GUARDRAIL_SYSTEM + "\n\nBạn có thể dùng thông tin tham khảo bên dưới để trả lời ngắn gọn, đúng ý và tự nhiên. Nếu không đủ thông tin thì dừng lại và không suy đoán.\n\nTham khảo:\n" + src_text
        draft = await generate_with_history(system, state["messages"])
        draft = draft or ""
        ok, conf, reason, fixed = await judge_answer(last_user, src_text, draft)
        reply = draft if ok else (fixed or "")
    else:
        reply = await generate_with_history(GUARDRAIL_SYSTEM, state["messages"])
    if not reply:
        reply = _mock_guardrail()
    return {
        "messages": [AIMessage(content=reply)],
        "emotion": "neutral",
        "avatar_action": "idle_typing",
    }


async def entertainment_expert_node(state: AgentState) -> dict:
    last_user = state["messages"][-1].content if state.get("messages") else ""

    # --- Reasoning router: pick best retriever before searching ---
    routing = await route_retriever(last_user)
    retriever_name = routing["retriever"]
    clean_query = routing.get("query_en") or last_user
    logger.info(
        "entertainment_expert router: retriever={} query_en={!r} reason={!r}",
        retriever_name, clean_query, routing.get("reason", ""),
    )

    order = _build_retriever_order(retriever_name)
    sources, winner = await _run_retrievers(clean_query, order)
    if winner:
        logger.info("entertainment_expert retriever hit: {} -> {} results", winner, len(sources))
    if sources:
        ref_max = 1200
        parts = []
        for s in sources:
            snippet = s.get("snippet") or ""
            snippet = re.sub(r"\(\s*Source\s*:\s*[^)]+\)", "", snippet, flags=re.IGNORECASE)
            snippet = re.sub(r"\bSource\s*:\s*[^\n\r]+", "", snippet, flags=re.IGNORECASE | re.MULTILINE)
            snippet = snippet[:ref_max].strip()
            snippet = re.sub(r"\n{3,}", "\n\n", snippet).strip()
            if not snippet:
                continue
            # Enrich community results with subreddit/url for attribution.
            meta_parts = []
            if s.get("subreddit"):
                meta_parts.append(f"subreddit: {s['subreddit']}")
            if s.get("url"):
                meta_parts.append(f"url: {s['url']}")
            if s.get("title"):
                meta_parts.append(f"title: {s['title']}")
            if meta_parts:
                header = " | ".join(meta_parts)
                parts.append(f"[{header}]\n{snippet}")
            else:
                parts.append(snippet)
        src_text = "\n\n".join(parts).strip()

        # Build KEEP_TERMS dynamically from references so it also works for other anime.
        # Keep English verse terms/proper nouns as-is; translate everything else normally.
        joined = src_text
        is_aot = bool(re.search(r"(attack on titan|shingeki|aot)", (last_user or "").lower()))
        aot_keep = [
            "the Scout Regiment",
            "Scout Regiment",
            "Founding Titan",
            "Rumbling",
            "the Rumbling",
            "Fort Salta",
            "Marleyans",
            "Eldians",
            "Paradis",
            "war of all wars",
            "Eren",
            "Mikasa",
            "Armin",
            "Jean",
            "Conny",
            "Reiner",
            "Pieck",
            "Levi",
        ] if is_aot else []

        stop_singles = {
            "The",
            "And",
            "But",
            "For",
            "With",
            "From",
            "Into",
            "Over",
            "After",
            "Before",
            "Will",
            "Would",
            "However",
            "This",
            "That",
            "There",
            "Their",
            "When",
            "Where",
            "Why",
            "Who",
            "What",
        }
        meta_drop = {"ANIME", "TV", "eps", "eps.", "ch", "episodes", "chapters"}

        # Extract TitleCase proper noun phrases from the reference text.
        multi = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+\b", joined)
        singles = re.findall(r"\b[A-Z][a-z]{2,}\b", joined)

        keep_terms = []
        seen = set()
        for t in aot_keep:
            if t not in seen:
                keep_terms.append(t)
                seen.add(t)

        for t in multi + singles:
            tt = t.strip()
            if not tt or tt in seen:
                continue
            if tt in stop_singles:
                continue
            if tt in meta_drop:
                continue
            low = tt.lower()
            if low in {"crunchyroll", "funimation", "anime", "news", "marleyans", "eldians", "paradis"} and not is_aot:
                # For non-AoT, only keep these if they come from the actual extracted terms (to avoid source/meta artifacts).
                continue
            seen.add(tt)
            keep_terms.append(tt)
            if len(keep_terms) >= 30:
                break

        keep_block = "KEEP_TERMS:\n" + "\n".join([f"- {t}" for t in keep_terms]) + "\n\n"

        is_community = all(s.get("source") == "community" for s in sources)

        strict_hint = ""
        if any((s.get("source") == "wikipedia") for s in sources):
            strict_hint += "\n\nChế độ Wikipedia STRICT: bạn phải bám sát wording/thuật ngữ trong extract, không tự chế lại tên."
        if any((s.get("source") == "anilist") for s in sources):
            strict_hint += "\n\nChế độ AniList STRICT: chỉ bám sát synopsis/metadata từ AniList trong extract; KHÔNG thêm tình tiết ngoài nguồn."

        if is_community:
            system = (
                COMMUNITY_PRESENTER_SYSTEM
                + keep_block
                + GROUNDED_KNOWLEDGE_RULES
                + "\n\nTổng hợp ý kiến cộng đồng từ phần Tham khảo bên dưới. KHÔNG tự bịa thêm.\n\nTham khảo:\n"
                + src_text
            )
        else:
            system = (
                ENTERTAINMENT_EXPERT_SYSTEM
                + keep_block
                + GROUNDED_KNOWLEDGE_RULES
                + strict_hint
                + "\n\nChỉ xuất bản dịch tiếng Việt từ phần Tham khảo bên dưới. KHÔNG thêm bất kỳ câu nào khác.\n\nTham khảo:\n"
                + src_text
            )
        # Translator node: avoid full chat history that can reintroduce chatty tone.
        draft = await generate(system, last_user)
        draft = draft or ""
        source_fallback = src_text.strip()

        # Hard post-check: must not contain source attribution/chatty ellipsis.
        ok = False
        fixed = ""
        if re.search(r"(source\s*:|^\s*\(?\s*source\s*:)", draft, flags=re.IGNORECASE | re.MULTILINE):
            ok = False
        elif "..." in draft:
            ok = False
        else:
            ok, conf, reason, fixed = await judge_answer(last_user, src_text, draft)
            try:
                logger.info(
                    "entertainment_expert judge verdict={} conf={} reason={} fixed_len={}",
                    ok,
                    conf,
                    reason,
                    len(fixed or ""),
                )
            except Exception:
                pass
        _REFUSAL_MARKERS = [
            "không đủ dữ liệu", "thiếu dữ liệu", "không thể trả lời",
            "không có đủ", "dừng lại", "không lấy được",
            "không có thông tin", "mình có thể giúp bạn tìm",
            "không tìm thấy", "không tìm được",
        ]

        def _is_refusal(text: str) -> bool:
            low = (text or "").strip().lower()
            return any(m in low for m in _REFUSAL_MARKERS)

        if ok and draft.strip():
            reply = draft
        else:
            # Judge rejected or hard-check failed.
            # Prefer: fixed > draft (only if not a refusal) > raw source text.
            if (fixed or "").strip() and not _is_refusal(fixed):
                reply = fixed.strip()
            elif draft.strip() and not _is_refusal(draft):
                reply = draft.strip()
            elif source_fallback:
                reply = source_fallback
            else:
                reply = "Mình không thể trả lời chính xác phần bạn hỏi vì thiếu dữ liệu từ nguồn tham khảo."
    else:
        # No retriever context available -> do NOT guess
        reply = "Mình chưa lấy được nguồn tham khảo để tóm tắt chính xác phần bạn hỏi, nên mình dừng lại."
    if not reply:
        reply = "Mình không thể trả lời chính xác phần bạn hỏi vì thiếu dữ liệu từ nguồn tham khảo."
    return {
        "messages": [AIMessage(content=reply)],
        "emotion": "surprised",
        "avatar_action": "shocked_face",
    }


async def comfort_node(state: AgentState) -> dict:
    reply = await generate_with_history(COMFORT_SYSTEM, state["messages"])
    if not reply:
        reply = _mock_comfort()
    return {
        "messages": [AIMessage(content=reply)],
        "emotion": "sad",
        "avatar_action": "comfort_sit",
    }


async def advice_node(state: AgentState) -> dict:
    reply = await generate_with_history(ADVICE_SYSTEM, state["messages"])
    if not reply:
        reply = _mock_advice()
    return {
        "messages": [AIMessage(content=reply)],
        "emotion": "neutral",
        "avatar_action": "idle_typing",
        "bibliotherapy_suggestion": "Barakamon",
    }


async def crisis_node(state: AgentState) -> dict:
    reply = await generate_with_history(CRISIS_SYSTEM, state["messages"])
    if not reply:
        reply = _mock_crisis()
    return {
        "messages": [AIMessage(content=reply)],
        "emotion": "crisis",
        "avatar_action": "serious_alert",
    }
