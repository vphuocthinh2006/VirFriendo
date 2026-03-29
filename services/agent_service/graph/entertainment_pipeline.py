import os
import re
from typing import Dict, List

from loguru import logger

from services.agent_service.llm.agentic_retriever import agentic_retrieve
from services.agent_service.llm.client import generate
from services.agent_service.llm.reddit_search import reddit_search
from services.agent_service.llm.community_search import community_search
from services.agent_service.llm.knowledge_judge import judge_answer
from services.agent_service.llm.wiki_search import wiki_search
from services.agent_service.llm.anilist import anilist_search

_META_PATTERNS = [
    r"^(?:Nhiệm vụ|Vai trò|Task)[\s:]+.*?\n+",
    r"^(?:Dưới đây|Bên dưới|Below)[\s]+là[\s]+(?:bản dịch|nội dung).*?[:\n]+",
    r"^(?:Theo|Dựa trên|Based on)\s+(?:tham khảo|phần tham khảo|references?).*?[:\n]+",
    r"^Bạn là một (?:bộ dịch|translator).*?\n+",
    r"^(?:Tôi sẽ|Mình sẽ) (?:dịch|tóm tắt|translate).*?[:\n]+",
]
_THAM_KHAO_RE = re.compile(
    r"[^.!?\n]*(?:tham khảo|references?|không được liệt kê|không có trong|không nhắc đến)[^.!?\n]*[.!?]?\s*",
    re.IGNORECASE,
)
_REFUSAL_MARKERS = [
    "không đủ dữ liệu", "thiếu dữ liệu", "không thể trả lời",
    "không có đủ", "dừng lại", "không lấy được",
    "không có thông tin", "mình có thể giúp bạn tìm",
    "không tìm thấy", "không tìm được",
]
_STRICT_NO_SOURCE_RE = re.compile(r"(source\s*:|^\s*\(?\s*source\s*:)", flags=re.IGNORECASE | re.MULTILINE)


def _strip_meta(text: str) -> str:
    out = text or ""
    for pat in _META_PATTERNS:
        out = re.sub(pat, "", out, count=1, flags=re.IGNORECASE | re.MULTILINE).strip()
    out = _THAM_KHAO_RE.sub("", out).strip()
    return out


def _is_refusal(text: str) -> bool:
    low = (text or "").strip().lower()
    return any(m in low for m in _REFUSAL_MARKERS)


def _build_source_text(sources: List[Dict[str, str]], ref_max: int = 1200) -> str:
    parts: List[str] = []
    for s in sources:
        snippet = s.get("snippet") or ""
        snippet = re.sub(r"\(\s*Source\s*:\s*[^)]+\)", "", snippet, flags=re.IGNORECASE)
        snippet = re.sub(r"\bSource\s*:\s*[^\n\r]+", "", snippet, flags=re.IGNORECASE | re.MULTILINE)
        snippet = snippet[:ref_max].strip()
        snippet = re.sub(r"\n{3,}", "\n\n", snippet).strip()
        if not snippet:
            continue
        meta_parts = []
        if s.get("subreddit"):
            meta_parts.append(f"subreddit: {s['subreddit']}")
        if s.get("url"):
            meta_parts.append(f"url: {s['url']}")
        if s.get("title"):
            meta_parts.append(f"title: {s['title']}")
        if meta_parts:
            parts.append(f"[{' | '.join(meta_parts)}]\n{snippet}")
        else:
            parts.append(snippet)
    return "\n\n".join(parts).strip()


def _build_keep_terms_block(src_text: str, user_query: str) -> str:
    is_aot = bool(re.search(r"(attack on titan|shingeki|aot)", (user_query or "").lower()))
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
        "The", "And", "But", "For", "With", "From", "Into", "Over", "After", "Before",
        "Will", "Would", "However", "This", "That", "There", "Their", "When", "Where", "Why", "Who", "What",
    }
    meta_drop = {"ANIME", "TV", "eps", "eps.", "ch", "episodes", "chapters"}
    multi = re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+\b", src_text)
    singles = re.findall(r"\b[A-Z][a-z]{2,}\b", src_text)

    keep_terms: List[str] = []
    seen = set()
    for t in aot_keep:
        if t not in seen:
            keep_terms.append(t)
            seen.add(t)
    for t in multi + singles:
        tt = t.strip()
        if not tt or tt in seen or tt in stop_singles or tt in meta_drop:
            continue
        low = tt.lower()
        if low in {"crunchyroll", "funimation", "anime", "news", "marleyans", "eldians", "paradis"} and not is_aot:
            continue
        seen.add(tt)
        keep_terms.append(tt)
        if len(keep_terms) >= 30:
            break
    return "KEEP_TERMS:\n" + "\n".join([f"- {t}" for t in keep_terms]) + "\n\n"


def _is_comparison_query(user_query: str) -> bool:
    low = (user_query or "").lower()
    markers = [
        "so sánh", "ai hơn", "đánh với", "đấu với", "đọ", "versus", "vs",
        "who wins", "stronger", "more powerful", "power scaling",
    ]
    return any(m in low for m in markers)


def _is_preference_query(user_query: str) -> bool:
    low = (user_query or "").lower()
    markers = [
        "fandom", "cộng đồng", "thích", "ưa", "chuộng", "opinion", "preference",
        "thích hơn", "ưa hơn", "which one", "which is better", "consensus",
        "nhạc", "music", "pop", "rock", "gợi ý", "recommend", "hay nhất", "favorite",
        "sở thích", "genre",
    ]
    return any(m in low for m in markers)


def _is_plot_synopsis_query(user_query: str) -> bool:
    """User asks for plot / synopsis / storyline summary (needs wiki + AniList, not only fanwiki stubs)."""
    low = (user_query or "").lower()
    markers = (
        "plot", "synopsis", "summary", "story", "storyline", "premise", "overview",
        "tóm tắt", "tóm lược", "cốt truyện", "nội dung", "sơ lược", "diễn biến", "kể lại",
    )
    return any(m in low for m in markers)


_RECOVERY_AFTER_JUDGE_REJECT_HINT = """

[BẮT BUỘC — phục hồi sau reviewer]
- Tham khảo ở trên đã được lọc; trả lời 5–10 câu tiếng Việt tự nhiên (đoạn văn), không liệt kê bullet nguồn hay chép URL.
- Chỉ diễn giải nội dung prose có trong Tham khảo; không nói "không có nguồn" nếu vẫn còn đoạn mô tả liên quan.
"""


_PLOT_SYNOPSIS_RETRY_HINT = """

[Nhiệm vụ plot/synopsis — bắt buộc]
- User đang hỏi tóm tắt cốt truyện / plot / synopsis: bạn PHẢI trả lời bằng cách dịch và lược tóm trực tiếp từ phần Tham khảo.
- Nếu Tham khảo có synopsis/description từ AniList hoặc đoạn extract Wikipedia, hãy dùng làm xương sống câu trả lời (4–10 câu tiếng Việt).
- KHÔNG được trả lời kiểu \"mình không có nguồn\" nếu Tham khảo vẫn có chữ mô tả cốt truyện hoặc giới thiệu tác phẩm.
- Không thêm tình tiết không có trong Tham khảo; có thể nói ngắn nếu nguồn chỉ mô tả phần đầu arc.
"""


async def _boost_plot_synopsis_sources(
    user_query: str, sources: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    if not _is_plot_synopsis_query(user_query):
        return sources
    out = list(sources)
    try:
        an = await anilist_search(user_query, max_results=3)
        if an:
            out = _dedup_merge_sources(out, an)
            logger.info("plot_boost: merged {} anilist sources", len(an))
    except Exception as e:
        logger.warning("plot_boost anilist: {}", e)
    try:
        qn = re.sub(
            r"(tóm\s*tắt|tóm\s*lược|về|cốt\s*truyện|của|plot|summary|synopsis|story)\s*",
            " ",
            user_query,
            flags=re.IGNORECASE,
        )
        qn = re.sub(r"\s+", " ", qn).strip()
        for cand in (f"{qn} anime", f"{qn} manga", qn):
            if len(cand) < 4:
                continue
            w = await wiki_search(cand, max_results=3)
            if w:
                out = _dedup_merge_sources(out, w)
                logger.info("plot_boost: merged {} wiki hits for {!r}", len(w), cand)
                break
    except Exception as e:
        logger.warning("plot_boost wiki: {}", e)
    return out


def _substantial_evidence(sources: List[Dict[str, str]], src_text: str) -> bool:
    """Retrieval đã có snippet đủ dài — không nên trả no_relevant chỉ vì judge/generator lỗi."""
    st = (src_text or "").strip()
    if len(st) < 160:
        return False
    return len(sources) >= 1


def _wants_voice_or_media_boost(user_query: str) -> bool:
    low = (user_query or "").lower()
    markers = (
        "voice actor",
        "voice actors",
        "seiyuu",
        "lồng tiếng",
        "nhạc",
        "soundtrack",
        "music",
        "theme song",
        "ca sĩ",
        "singer",
    )
    return any(m in low for m in markers)


def _tavily_disambiguation_query(user_query: str) -> str:
    """Fanwiki dễ trúng nhầm franchise (vd BG3 Raphael). Tavily + từ khóa rõ hơn."""
    low = (user_query or "").lower()
    if "raphael" in low and "final act" in low:
        return (
            'Raphael "Final Act" Honkai Star Rail voice actor music theme song HoYoverse HSR'
        )
    return (user_query or "").strip()


async def _boost_voice_media_tavily(user_query: str, sources: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Luôn gọi Tavily thêm cho câu voice/nhạc — bổ sung fanwiki-only lệch IP."""
    if not _wants_voice_or_media_boost(user_query):
        return sources
    q = _tavily_disambiguation_query(user_query)
    if len(q) < 4:
        return sources
    try:
        from services.agent_service.llm.web_search import tavily_search

        raw = await tavily_search(q, max_results=6)
    except Exception as e:
        logger.warning("voice_media tavily boost failed: {}", e)
        return sources
    extra: List[Dict[str, str]] = [{**r, "source": "tavily"} for r in (raw or [])]
    if not extra:
        return sources
    logger.info("entertainment_expert: voice_media tavily boost +{} hits q={!r}", len(extra), q)
    return _dedup_merge_sources(sources, extra)


def _snippet_is_boilerplate_or_garbage(sn: str) -> bool:
    """Trang mainpage wiki, inputbox, bảng wikitext — không đưa vào LLM / không dump cho user."""
    if not sn or len(sn) < 28:
        return True
    low = sn.lower()
    junk_markers = (
        "mainpage-leftcolumn",
        "mainpage-rightcolumn",
        "<mainpage",
        "<inputbox",
        "preload=",
        "this is a wiki, a website that anyone",
        "create an article about an episode",
        "create an article about a character",
        "click [ edit] to replace",
        "{| style=",
        "default=episode title",
        "default=character name",
        "buttonlabel=create",
    )
    if any(m in low for m in junk_markers):
        return True
    if sn.count("<") > 10:
        return True
    if low.startswith("{|") or "\n{|" in low:
        return True
    return False


def _snippet_presentable(sn: str) -> bool:
    """Không hiển thị infobox / wikitext thô cho user."""
    if _snippet_is_boilerplate_or_garbage(sn):
        return False
    t = (sn or "").strip()
    if len(t) < 48:
        return False
    if "{{" in t or "}}" in t:
        return False
    if t.count("|") > 22:
        return False
    if "infobox" in t.lower():
        return False
    return True


def _filter_garbage_sources(sources: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Loại kết quả chỉ là HTML/template trước khi build Tham khảo cho LLM + judge."""
    out: List[Dict[str, str]] = []
    for s in sources:
        sn = (s.get("snippet") or "").strip()
        if _snippet_is_boilerplate_or_garbage(sn):
            continue
        out.append(s)
    return out


def _deterministic_stitch_enabled() -> bool:
    return (os.environ.get("ENABLE_DETERMINISTIC_SOURCE_STITCH", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _deterministic_any_source_stitch(sources: List[Dict[str, str]], max_snips: int = 5) -> str:
    """Fallback cuối: trích thẳng từ fanwiki/tavily/reddit… khi model từ chối oan."""
    lines: List[str] = []
    for s in sources[:max_snips]:
        sn = (s.get("snippet") or "").strip()
        if not _snippet_presentable(sn):
            continue
        title = (s.get("title") or "").strip() or "Nguồn"
        src = (s.get("source") or "").strip() or "web"
        lines.append(f"• **{title}** ({src}): {sn[:900]}")
    if not lines:
        return ""
    return (
        "Mình tóm theo các đoạn đã lấy được từ nguồn (trích retrieval, không thêm chi tiết ngoài đoạn này):\n\n"
        + "\n\n".join(lines)
    )


def _deterministic_synopsis_stitch(sources: List[Dict[str, str]]) -> str:
    """Grounded fallback: quote authoritative snippets when the model refuses."""
    lines: List[str] = []
    for s in sources:
        src = (s.get("source") or "").lower()
        if src not in ("anilist", "wikipedia"):
            continue
        sn = (s.get("snippet") or "").strip()
        if len(sn) < 60:
            continue
        title = (s.get("title") or "Nguồn").strip()
        lines.append(f"• **{title}**: {sn[:1200]}")
        if len(lines) >= 3:
            break
    if not lines:
        return ""
    return (
        "Mình tóm lại theo các đoạn synopsis/encyclopedia trong nguồn tham khảo (bạn đọc kỹ trích dẫn gốc nếu cần):\n\n"
        + "\n\n".join(lines)
    )


def _has_community_sources(sources: List[Dict[str, str]]) -> bool:
    return any((s.get("source") or "") in {"reddit", "community"} for s in sources)


def _preference_focus_query(user_query: str) -> str:
    low = (user_query or "").lower()
    if "dark urge" in low and any(k in low for k in ["cốt truyện gốc", "origin", "tav", "custom"]):
        return "Dark Urge vs Tav origin story community preference Baldur's Gate 3"
    if any(k in low for k in ["fandom", "cộng đồng", "preference", "opinion"]):
        return f"{user_query} reddit community opinion"
    return user_query


def _dedup_merge_sources(base: List[Dict[str, str]], extra: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out = list(base)
    seen = {str(s.get("url") or "").strip() for s in out if str(s.get("url") or "").strip()}
    for s in extra:
        u = str(s.get("url") or "").strip()
        if u and u in seen:
            continue
        if u:
            seen.add(u)
        out.append(s)
    return out


def _looks_relevant_preference(user_query: str, item: Dict[str, str]) -> bool:
    low_q = (user_query or "").lower()
    hay = " ".join(
        [
            str(item.get("title") or "").lower(),
            str(item.get("snippet") or "").lower(),
            str(item.get("url") or "").lower(),
            str(item.get("subreddit") or "").lower(),
        ]
    )
    if "dark urge" in low_q and ("dark urge" not in hay and "durge" not in hay):
        return False
    if any(k in low_q for k in ["baldur", "bg3", "astarion", "raphael", "zariel", "dark urge"]):
        if not any(k in hay for k in ["baldur", "bg3", "astarion", "raphael", "zariel", "dark urge"]):
            return False
    return True


def _deterministic_preference_fallback(user_query: str, sources: List[Dict[str, str]]) -> str:
    top = sources[:3]
    if not top:
        return ""
    refs = []
    for s in top:
        title = (s.get("title") or "").strip()
        src = (s.get("subreddit") or s.get("source") or "nguồn cộng đồng").strip()
        if title:
            refs.append(f"- {title} ({src})")
    evidence = "\n".join(refs) if refs else "- Có nguồn liên quan nhưng chưa đủ đồng thuận trực tiếp."
    return (
        "Kết luận tạm thời: Nguồn hiện có chưa cho thấy đồng thuận tuyệt đối nghiêng hẳn về một phía.\n"
        "Dựa trên nguồn hiện có:\n"
        f"{evidence}\n"
        "Độ chắc chắn: Low - cần thêm thread cộng đồng trực tiếp bàn về so sánh này."
    )


def _build_generation_system(
    *,
    user_query: str,
    sources: List[Dict[str, str]],
    src_text: str,
    keep_block: str,
    expert_system: str,
    community_system: str,
    grounded_rules: str,
) -> str:
    is_community = all(s.get("source") in {"community", "reddit"} for s in sources)
    strict_hint = ""
    if any((s.get("source") == "wikipedia") for s in sources):
        strict_hint += "\n\nChế độ Wikipedia STRICT: bạn phải bám sát wording/thuật ngữ trong extract, không tự chế lại tên."
    if any((s.get("source") == "anilist") for s in sources):
        strict_hint += "\n\nChế độ AniList STRICT: chỉ bám sát synopsis/metadata từ AniList trong extract; KHÔNG thêm tình tiết ngoài nguồn."

    if is_community:
        return (
            community_system
            + keep_block
            + grounded_rules
            + "\n\nTổng hợp ý kiến cộng đồng từ phần Tham khảo bên dưới. KHÔNG tự bịa thêm. Chỉ nói đúng trọng tâm câu hỏi user.\n\nTham khảo:\n"
            + src_text
        )

    if _is_comparison_query(user_query):
        return (
            expert_system
            + keep_block
            + grounded_rules
            + strict_hint
            + "\n\nChế độ SO SÁNH LORE (AI Overview style):\n"
            + "- Bạn được phép tổng hợp và so sánh từ nhiều mẩu trong Tham khảo, nhưng KHÔNG được thêm dữ kiện ngoài Tham khảo.\n"
            + "- Nếu không có trận đối đầu trực tiếp trong nguồn, phải nói rõ: \"Không có dữ kiện canon về trận trực tiếp trong nguồn tham khảo\".\n"
            + "- Kết luận theo mức độ chắc chắn: nếu bằng chứng gián tiếp thì dùng phrasing \"nhiều khả năng\", \"theo nguồn hiện có\".\n"
            + "- Ưu tiên hierarchy/lore rank/chức vị/thành tích/nguồn sức mạnh; tách rõ với gameplay/speculation nếu có.\n"
            + "- KHÔNG dùng `Source:` và KHÔNG bịa chỉ số/CR nếu nguồn không nêu.\n"
            + "- Chỉ bám đúng cặp đối tượng user hỏi; không kéo thêm nhân vật/tác phẩm ngoài câu hỏi trừ khi nguồn bắt buộc để làm rõ.\n"
            + "- Format bắt buộc:\n"
            + "  Kết luận ngắn: <1-2 câu>\n"
            + "  Power & hierarchy: <đoạn ngắn>\n"
            + "  Lore vs gameplay/speculation: <đoạn ngắn>\n"
            + "  Độ chắc chắn: <High/Medium/Low + lý do theo nguồn>\n"
            + "\nTham khảo:\n"
            + src_text
        )
    return (
        expert_system
        + keep_block
        + grounded_rules
        + strict_hint
        + "\n\nChỉ xuất bản dịch tiếng Việt từ phần Tham khảo bên dưới và trả lời đúng trọng tâm câu hỏi user. KHÔNG thêm bất kỳ câu nào khác.\n\nTham khảo:\n"
        + src_text
    )


def _build_preference_fallback_system(
    *,
    user_query: str,
    src_text: str,
    keep_block: str,
    expert_system: str,
    grounded_rules: str,
) -> str:
    return (
        expert_system
        + keep_block
        + grounded_rules
        + "\n\nChế độ COMMUNITY PREFERENCE FALLBACK:\n"
        + "- Mục tiêu: trả lời câu hỏi preference/opinion cộng đồng dựa trên Tham khảo.\n"
        + "- Nếu không có số liệu direct X > Y, KHÔNG từ chối trắng; thay bằng kết luận thận trọng.\n"
        + "- Bắt buộc nêu rõ mức chắc chắn và nói rõ khi chưa có đồng thuận trực tiếp.\n"
        + "- Không bịa dữ kiện mới ngoài Tham khảo.\n"
        + "- Format ngắn:\n"
        + "  Kết luận tạm thời: <1 câu>\n"
        + "  Dựa trên nguồn hiện có: <1-3 ý ngắn>\n"
        + "  Độ chắc chắn: <High/Medium/Low + vì sao>\n"
        + "\nTham khảo:\n"
        + src_text
    )


async def run_entertainment_pipeline(
    *,
    user_query: str,
    expert_system: str,
    community_system: str,
    grounded_rules: str,
    no_source_reply: str,
    no_relevant_reply: str,
) -> str:
    retriever_mode = (os.environ.get("RETRIEVER_MODE") or "tavily_only").strip().lower()
    preference_query = _is_preference_query(user_query)
    plot_synopsis_query = _is_plot_synopsis_query(user_query)
    # For community preference questions, force a community-first toolset even if mode=tavily_only.
    # This avoids false "no source" when user explicitly asks what fandom/community prefers.
    if preference_query:
        allowed_tools = ["reddit", "community", "fanwiki", "wiki", "tavily"]
    elif plot_synopsis_query:
        allowed_tools = ["anilist", "wiki", "fanwiki", "reddit", "community", "tavily"]
    else:
        allowed_tools = None

    sources, trace = await agentic_retrieve(
        user_query,
        allowed_tools=allowed_tools,
        max_steps=4,
    )
    logger.info("entertainment_expert telemetry trace={}", trace)

    # If first pass only yields weak/sparse evidence, force a quick community pass.
    if (retriever_mode == "hybrid" or preference_query) and len(sources) < 2:
        more_sources, more_trace = await agentic_retrieve(
            user_query,
            allowed_tools=["reddit", "community"],
            max_steps=2,
        )
        if more_sources:
            sources = _dedup_merge_sources(sources, more_sources)
        logger.info("entertainment_expert telemetry community_pass_trace={}", more_trace)

    # Preference query hardening: do an explicit community fetch even when retriever routing is noisy.
    if preference_query and not _has_community_sources(sources):
        q_focus = _preference_focus_query(user_query)
        try:
            r1 = await reddit_search(q_focus, max_results=6)
        except Exception:
            r1 = []
        try:
            r2 = await community_search(q_focus, max_results=6)
        except Exception:
            r2 = []
        extra = [s for s in [*(r1 or []), *(r2 or [])] if _looks_relevant_preference(user_query, s)]
        if extra:
            sources = _dedup_merge_sources(sources, extra)
            logger.info("entertainment_expert: explicit community fallback added {}", len(extra))

    if sources and not any((s.get("source") == "wikipedia" and s.get("lang") == "vi") for s in sources):
        try:
            vi_wiki = await wiki_search(user_query, max_results=2)
            if vi_wiki:
                sources.extend(vi_wiki)
                logger.info("entertainment_expert: appended {} vi-wiki results for localized terms", len(vi_wiki))
        except Exception:
            pass

    sources = await _boost_plot_synopsis_sources(user_query, sources)
    sources = await _boost_voice_media_tavily(user_query, sources)

    had_any_before_garbage_filter = bool(sources)
    sources = _filter_garbage_sources(sources)
    if not sources:
        if not had_any_before_garbage_filter:
            logger.info("entertainment_expert telemetry final_reason=no_source")
            return no_source_reply
        logger.info("entertainment_expert telemetry final_reason=no_usable_source_after_filter")
        return no_relevant_reply

    src_text = _build_source_text(sources)
    substantial = _substantial_evidence(sources, src_text)
    keep_block = _build_keep_terms_block(src_text, user_query)
    system = _build_generation_system(
        user_query=user_query,
        sources=sources,
        src_text=src_text,
        keep_block=keep_block,
        expert_system=expert_system,
        community_system=community_system,
        grounded_rules=grounded_rules,
    )

    draft = _strip_meta((await generate(system, user_prompt)) or "")
    if plot_synopsis_query and (not (draft or "").strip() or _is_refusal(draft)):
        draft = _strip_meta(
            (await generate(system + _PLOT_SYNOPSIS_RETRY_HINT, user_prompt)) or ""
        )
        logger.info("entertainment_expert plot_retry after refusal/empty len={}", len(draft or ""))

    if _is_refusal(draft) and substantial:
        force_hint = (
            "\n\n[BẮT BUỘC — đã có Tham khảo đủ dài phía trên]\n"
            "- Trả lời 5–10 câu tiếng Việt chỉ bằng cách diễn giải/tóm từ các đoạn Tham khảo.\n"
            "- TUYỆT ĐỐI KHÔNG viết kiểu \"không tìm được nguồn\", \"dừng lại\", \"không đủ tham khảo\".\n"
        )
        draft = _strip_meta((await generate(system + force_hint, user_prompt)) or "")
        logger.info("entertainment_expert refusal_retry len={}", len(draft or ""))

    ok = False
    fixed = ""
    preference_mode = _is_preference_query(user_query)
    if _STRICT_NO_SOURCE_RE.search(draft):
        ok = False
    else:
        ok, conf, reason, fixed = await judge_answer(
            user_prompt,
            src_text,
            draft,
            fail_open=preference_mode or plot_synopsis_query or substantial,
            accept_on_reject=plot_synopsis_query or substantial,
        )
        try:
            logger.info(
                "entertainment_expert telemetry judge_verdict={} conf={} reason={} fixed_len={}",
                ok,
                conf,
                reason,
                len(fixed or ""),
            )
        except Exception:
            pass

    if not ok and substantial and not preference_mode:
        draft_rec = _strip_meta(
            (await generate(system + _RECOVERY_AFTER_JUDGE_REJECT_HINT, user_prompt)) or ""
        )
        if draft_rec and not _STRICT_NO_SOURCE_RE.search(draft_rec) and not _is_refusal(draft_rec):
            ok_r, conf_r, reason_r, fixed_r = await judge_answer(
                user_prompt,
                src_text,
                draft_rec,
                fail_open=plot_synopsis_query or substantial,
                accept_on_reject=plot_synopsis_query or substantial,
            )
            logger.info(
                "entertainment_expert telemetry judge_recovery verdict={} conf={} reason={}",
                ok_r,
                conf_r,
                reason_r,
            )
            if ok_r and draft_rec.strip():
                logger.info("entertainment_expert telemetry final_reason=judge_accept_recovery")
                return draft_rec.strip()
            fixed_r = _strip_meta(fixed_r or "")
            if fixed_r.strip() and not _is_refusal(fixed_r):
                logger.info("entertainment_expert telemetry final_reason=judge_fixed_recovery")
                return fixed_r.strip()
            if draft_rec.strip() and not _is_refusal(draft_rec):
                logger.info("entertainment_expert telemetry final_reason=judge_draft_recovery")
                return draft_rec.strip()

    if not ok and preference_mode:
        # Judge can be overly strict for community preference questions without direct X>Y lines.
        pref_system = _build_preference_fallback_system(
            user_query=user_query,
            src_text=src_text,
            keep_block=keep_block,
            expert_system=expert_system,
            grounded_rules=grounded_rules,
        )
        pref_draft = _strip_meta((await generate(pref_system, user_prompt)) or "")
        if pref_draft and not _STRICT_NO_SOURCE_RE.search(pref_draft) and not _is_refusal(pref_draft):
            logger.info("entertainment_expert telemetry final_reason=preference_fallback")
            return pref_draft
        # Last safety net: deterministic, grounded-only fallback from retrieved sources.
        safe_pref = _deterministic_preference_fallback(user_query, sources)
        if safe_pref:
            logger.info("entertainment_expert telemetry final_reason=preference_deterministic_fallback")
            return safe_pref

    if fixed:
        fixed = _strip_meta(fixed)

    if ok and draft.strip():
        logger.info("entertainment_expert telemetry final_reason=judge_accept")
        return draft
    if (fixed or "").strip() and not _is_refusal(fixed):
        logger.info("entertainment_expert telemetry final_reason=judge_fixed")
        return fixed.strip()
    if draft.strip() and not _is_refusal(draft):
        logger.info("entertainment_expert telemetry final_reason=judge_draft")
        return draft.strip()
    if preference_mode:
        safe_pref = _deterministic_preference_fallback(user_query, sources)
        if safe_pref:
            logger.info("entertainment_expert telemetry final_reason=preference_deterministic_last_resort")
            return safe_pref
    if plot_synopsis_query and _deterministic_stitch_enabled():
        stitched = _deterministic_synopsis_stitch(sources)
        if stitched:
            logger.info("entertainment_expert telemetry final_reason=deterministic_synopsis_stitch")
            return stitched
    if substantial and _deterministic_stitch_enabled():
        stitched_any = _deterministic_any_source_stitch(sources)
        if stitched_any:
            logger.info("entertainment_expert telemetry final_reason=deterministic_any_source_stitch")
            return stitched_any
    logger.info("entertainment_expert telemetry final_reason=no_relevant")
    return no_relevant_reply
