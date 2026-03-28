import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.agent_service.llm.agentic_retriever import agentic_retrieve


def _load_cases(path: Path, limit: int = 0) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(json.loads(s))
    if limit > 0:
        return out[:limit]
    return out


def _has_expected_source(sources: List[Dict[str, str]], expected: List[str]) -> bool:
    if not expected:
        return True
    got = {(s.get("source") or "").strip().lower() for s in sources}
    return any(e.lower() in got for e in expected)


async def _run(mode: str, cases: List[Dict[str, Any]], max_steps: int) -> None:
    os.environ["RETRIEVER_MODE"] = mode
    total = len(cases)
    passed = 0
    rows: List[Dict[str, Any]] = []
    for c in cases:
        query = str(c.get("query") or "").strip()
        expected = [str(x) for x in (c.get("expected_sources") or [])]
        sources, trace = await agentic_retrieve(query, allowed_tools=None, max_steps=max_steps)
        ok = bool(sources) and _has_expected_source(sources, expected)
        if ok:
            passed += 1
        rows.append(
            {
                "query": query,
                "ok": ok,
                "count": len(sources),
                "expected_sources": expected,
                "got_sources": list({(s.get("source") or "") for s in sources}),
                "reason": trace.get("reason"),
            }
        )

    print(f"mode={mode} pass={passed}/{total} ({(100.0 * passed / max(total, 1)):.1f}%)")
    failed = [r for r in rows if not r["ok"]]
    if failed:
        print("\nFailed cases:")
        for r in failed[:15]:
            print(f"- {r['query']} | got={r['got_sources']} expected={r['expected_sources']} reason={r['reason']} count={r['count']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="tests/golden_retrieval.jsonl")
    parser.add_argument("--mode", default="tavily_only")
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    load_dotenv(".env")
    cases = _load_cases(Path(args.cases), args.limit)
    asyncio.run(_run(args.mode, cases, args.max_steps))


if __name__ == "__main__":
    main()
