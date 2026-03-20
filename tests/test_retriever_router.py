"""Tests for retriever router keyword fallback and JSON parser."""
import pytest
from services.agent_service.llm.retriever_router import _keyword_fallback, _parse_router_json


class TestKeywordFallback:
    def test_reddit_routes_to_community(self):
        r = _keyword_fallback("review Baldur's Gate 3 trên reddit")
        assert r["retriever"] == "community"

    def test_opinion_routes_to_community(self):
        r = _keyword_fallback("ý kiến cộng đồng về Elden Ring")
        assert r["retriever"] == "community"

    def test_anime_title_routes_to_anilist(self):
        r = _keyword_fallback("tóm tắt Attack on Titan season 4")
        assert r["retriever"] == "anilist"

    def test_manga_routes_to_anilist(self):
        r = _keyword_fallback("manga One Piece chapter 1120")
        assert r["retriever"] == "anilist"

    def test_game_routes_to_wiki(self):
        r = _keyword_fallback("cốt truyện game Elden Ring")
        assert r["retriever"] == "wiki"

    def test_movie_routes_to_wiki(self):
        r = _keyword_fallback("plot phim Inception")
        assert r["retriever"] == "wiki"

    def test_unknown_defaults_to_wiki(self):
        r = _keyword_fallback("xin chào bạn ơi")
        assert r["retriever"] == "wiki"


class TestParseRouterJson:
    def test_clean_json(self):
        raw = '{"retriever": "anilist", "query_en": "Attack on Titan", "reason": "anime query"}'
        result = _parse_router_json(raw)
        assert result["retriever"] == "anilist"
        assert result["query_en"] == "Attack on Titan"

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"retriever": "wiki", "query_en": "Elden Ring", "reason": "game lore"}\n```'
        result = _parse_router_json(raw)
        assert result["retriever"] == "wiki"

    def test_json_embedded_in_text(self):
        raw = 'Sure! Here is the routing: {"retriever": "community", "query_en": "BG3 review", "reason": "review"}'
        result = _parse_router_json(raw)
        assert result["retriever"] == "community"

    def test_invalid_json_returns_none(self):
        assert _parse_router_json("not json at all") is None

    def test_empty_returns_none(self):
        assert _parse_router_json("") is None

    def test_none_returns_none(self):
        assert _parse_router_json(None) is None

    def test_json_without_retriever_key_returns_none(self):
        assert _parse_router_json('{"query": "test"}') is None
