import os
import re
from typing import Any, Dict, List

import httpx
from loguru import logger

from services.agent_service.llm.client import generate


def _enabled() -> bool:
    return (os.environ.get("ENABLE_FANWIKI_SEARCH", "true") or "").strip().lower() in ("1", "true", "yes")


def _debug() -> bool:
    return (os.environ.get("DEBUG_FANWIKI_SEARCH", "") or "").strip().lower() in ("1", "true", "yes")


def _safe_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    d = re.sub(r"[^a-z0-9\-]", "", d)
    return d


def _remove_balanced_templates(text: str) -> str:
    """Bỏ {{ ... }} lồng nhau (infobox) — regex một tầng không đủ."""
    s = text or ""
    for _ in range(96):
        i = s.find("{{")
        if i < 0:
            break
        depth = 0
        j = i
        end = -1
        while j < len(s):
            if j + 1 < len(s) and s[j : j + 2] == "{{":
                depth += 1
                j += 2
            elif j + 1 < len(s) and s[j : j + 2] == "}}":
                depth -= 1
                j += 2
                if depth == 0:
                    end = j
                    break
            else:
                j += 1
        if end < 0:
            s = s[:i] + " " + s[i + 2 :]
            continue
        s = s[:i] + " " + s[end:]
    return s


def _strip_wikitext(text: str) -> str:
    out = text or ""
    out = _remove_balanced_templates(out)
    # Remove any tiny leftover templates
    for _ in range(12):
        nxt = re.sub(r"\{\{[^{}]*\}\}", " ", out)
        if nxt == out:
            break
        out = nxt
    out = re.sub(r"<ref[^>]*>.*?</ref>", " ", out, flags=re.IGNORECASE | re.DOTALL)
    # Convert wiki links [[A|B]] -> B, [[A]] -> A
    out = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", out)
    out = re.sub(r"\[\[([^\]]+)\]\]", r"\1", out)
    # Remove headings/format noise
    out = re.sub(r"={2,}\s*[^=\n]+\s*={2,}", " ", out)
    out = re.sub(r"[\*\#]{1,}\s*", " ", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def _fanwiki_snippet_usable(text: str) -> bool:
    """Không trả nội dung chủ yếu là infobox / wikitext máy."""
    t = (text or "").strip()
    if len(t) < 42:
        return False
    if t.count("{{") >= 2:
        return False
    if t.count("|") >= 18 and "voice_actor" in t:
        return False
    return True


def _keyword_domain_candidates(query: str) -> List[str]:
    """Chỉ gợi ý khi user nói rõ IP; còn lại để LLM _llm_domain_candidates quyết định."""
    low = (query or "").lower()
    if any(k in low for k in ["baldur", "bg3", "baldur's gate"]):
        return ["baldursgate"]
    return []


FANWIKI_DOMAIN_SYSTEM = """You infer which Fandom.com wiki subdomains best match the user's question.
Return strict JSON only:
{"domains":["subdomain1","subdomain2","subdomain3"]}
Rules:
- Lowercase, hyphenated subdomain only (e.g. eldenring, one-piece, baldursgate).
- Pick domains for the work/franchise the user is actually asking about — do not assume an IP they did not imply.
- Max 3 domains. If unsure, return fewer domains that still plausibly match.
"""


async def _llm_domain_candidates(query: str) -> List[str]:
    raw = await generate(FANWIKI_DOMAIN_SYSTEM, query)
    if not raw:
        return []
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    obj_text = m.group(0) if m else raw
    try:
        import json

        data = json.loads(obj_text)
    except Exception:
        return []
    domains = data.get("domains") if isinstance(data, dict) else None
    if not isinstance(domains, list):
        return []
    out: List[str] = []
    for d in domains[:3]:
        sd = _safe_domain(str(d or ""))
        if sd:
            out.append(sd)
    seen = set()
    return [d for d in out if not (d in seen or seen.add(d))]


async def fanwiki_search(query: str, *, max_results: int = 4) -> List[Dict[str, str]]:
    """
    Search Fandom wikis via MediaWiki API directly.
    Requires candidate fandom subdomains.
    """
    if not _enabled():
        return []
    q = (query or "").strip()
    if not q:
        return []

    llm_domains = await _llm_domain_candidates(q)
    kw_domains = _keyword_domain_candidates(q)
    domains = (llm_domains + kw_domains)[:3]
    if not domains:
        return []

    timeout = httpx.Timeout(10.0, connect=5.0)
    headers = {"User-Agent": "VirFriendo/1.0 (local fanwiki retriever)"}
    out: List[Dict[str, str]] = []
    seen = set()

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        for domain in domains:
            base = f"https://{domain}.fandom.com/api.php"
            params = {
                "action": "query",
                "list": "search",
                "srsearch": q,
                "srlimit": max(1, min(int(max_results), 8)),
                "format": "json",
                "utf8": 1,
            }
            try:
                r = await client.get(base, params=params)
                if r.status_code != 200:
                    continue
                data: Any = r.json()
            except Exception as e:
                if _debug():
                    logger.info("fanwiki_search failed domain={} q={!r} err={}", domain, q, e)
                continue

            query_obj = data.get("query") if isinstance(data, dict) else None
            search = query_obj.get("search") if isinstance(query_obj, dict) else None
            if not isinstance(search, list):
                continue
            for item in search:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                snippet = re.sub(r"<[^>]+>", "", str(item.get("snippet") or "")).strip()
                if not title:
                    continue
                extract = ""
                try:
                    er = await client.get(
                        base,
                        params={
                            "action": "query",
                            "prop": "extracts",
                            "titles": title,
                            "explaintext": 1,
                            "exintro": 1,
                            "format": "json",
                            "utf8": 1,
                        },
                    )
                    if er.status_code == 200:
                        ed: Any = er.json()
                        qobj = ed.get("query") if isinstance(ed, dict) else None
                        pages = qobj.get("pages") if isinstance(qobj, dict) else None
                        if isinstance(pages, dict):
                            for pv in pages.values():
                                if isinstance(pv, dict):
                                    extract = str(pv.get("extract") or "").strip()
                                    if extract:
                                        break
                except Exception:
                    extract = ""
                if not extract:
                    try:
                        rr = await client.get(
                            base,
                            params={
                                "action": "query",
                                "prop": "revisions",
                                "titles": title,
                                "rvprop": "content",
                                "rvslots": "main",
                                "format": "json",
                                "formatversion": 2,
                                "utf8": 1,
                            },
                        )
                        if rr.status_code == 200:
                            rd: Any = rr.json()
                            qobj2 = rd.get("query") if isinstance(rd, dict) else None
                            pages2 = qobj2.get("pages") if isinstance(qobj2, dict) else None
                            if isinstance(pages2, list):
                                for pv in pages2:
                                    if not isinstance(pv, dict):
                                        continue
                                    revs = pv.get("revisions")
                                    if not isinstance(revs, list) or not revs:
                                        continue
                                    slot = revs[0].get("slots") if isinstance(revs[0], dict) else None
                                    main = slot.get("main") if isinstance(slot, dict) else None
                                    content = main.get("content") if isinstance(main, dict) else ""
                                    cleaned = _strip_wikitext(str(content or ""))
                                    if cleaned:
                                        extract = cleaned[:2200]
                                        break
                    except Exception:
                        extract = ""
                url_title = title.replace(" ", "_")
                url = f"https://{domain}.fandom.com/wiki/{url_title}"
                if url in seen:
                    continue
                raw_snip = extract or snippet or title
                cleaned = _strip_wikitext(raw_snip)
                if not _fanwiki_snippet_usable(cleaned):
                    continue
                seen.add(url)
                out.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": cleaned[:2200],
                        "source": "fanwiki",
                    }
                )
                if len(out) >= max_results:
                    return out
    if _debug():
        logger.info("fanwiki_search q={!r} domains={} -> {} results", q, domains, len(out))
    return out
