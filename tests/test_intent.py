"""Tests for intent classifier keyword fallback and output parser."""
import pytest
from services.agent_service.api.intent_classifier import _keyword_fallback, _parse_output


class TestKeywordFallback:
    @pytest.mark.parametrize("msg,expected", [
        ("tôi muốn chết", "crisis_alert"),
        ("I want to kill myself", "crisis_alert"),
        ("không muốn sống nữa", "crisis_alert"),
    ])
    def test_crisis_detected(self, msg, expected):
        assert _keyword_fallback(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("viết code python giúp tôi", "out_of_domain"),
        ("bitcoin hôm nay giá bao nhiêu", "out_of_domain"),
        ("giải bài toán này", "out_of_domain"),
    ])
    def test_out_of_domain(self, msg, expected):
        assert _keyword_fallback(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("tóm tắt One Piece chapter mới", "entertainment_knowledge"),
        ("attack on titan season 4 nói về gì", "entertainment_knowledge"),
        ("Baldur's Gate 3 gameplay thế nào", "entertainment_knowledge"),
        ("review phim netflix", "entertainment_knowledge"),
        ("nhân vật Gojo mạnh cỡ nào", "entertainment_knowledge"),
    ])
    def test_entertainment(self, msg, expected):
        assert _keyword_fallback(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("làm sao để bớt lo lắng", "psychology_advice_seeking"),
        ("cho mình tips vượt qua stress", "psychology_advice_seeking"),
    ])
    def test_advice(self, msg, expected):
        assert _keyword_fallback(msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("hôm nay mệt mỏi quá", "psychology_venting"),
        ("tôi cảm thấy cô đơn", "psychology_venting"),
    ])
    def test_venting(self, msg, expected):
        assert _keyword_fallback(msg) == expected

    def test_default_is_chitchat(self):
        assert _keyword_fallback("xin chào bạn") == "greeting_chitchat"
        assert _keyword_fallback("hello") == "greeting_chitchat"


class TestParseOutput:
    def test_exact_label(self):
        assert _parse_output("crisis_alert") == "crisis_alert"

    def test_label_with_whitespace(self):
        assert _parse_output("  entertainment_knowledge  \n") == "entertainment_knowledge"

    def test_label_in_sentence(self):
        assert _parse_output("The intent is psychology_venting.") == "psychology_venting"

    def test_unknown_returns_default(self):
        assert _parse_output("something_random") == "greeting_chitchat"

    def test_empty_returns_default(self):
        assert _parse_output("") == "greeting_chitchat"
