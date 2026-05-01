#!/usr/bin/env python3
"""Validate Secrets Manager JSON payload before deployment."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_KEYS = {
    "DATABASE_URL",
    "SECRET_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPGRAM_API_KEY",
    "REPLICATE_API_TOKEN",
    "TAVILY_API_KEY",
    "LLM_PROVIDER",
    "APP_ENV",
    "CORS_ORIGINS",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_secret_json.py <secret-json-file>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    raw = path.read_text(encoding="utf-8")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(payload, dict):
        print("Secret payload must be a JSON object.", file=sys.stderr)
        return 1

    missing = sorted(k for k in REQUIRED_KEYS if k not in payload)
    if missing:
        print(f"Missing required keys: {', '.join(missing)}", file=sys.stderr)
        return 1

    provider = str(payload.get("LLM_PROVIDER", "")).strip().lower()
    if provider not in {"auto", "claude", "openai", "groq"}:
        print("LLM_PROVIDER must be one of: auto, claude, openai, groq", file=sys.stderr)
        return 1

    app_env = str(payload.get("APP_ENV", "")).strip().lower()
    if app_env not in {"development", "staging", "production"}:
        print("APP_ENV must be one of: development, staging, production", file=sys.stderr)
        return 1

    print("Secret JSON validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
