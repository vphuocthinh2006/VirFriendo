"""Tests for Intent Classifier (keyword fallback mode)."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-32chars!!")

from services.agent_service.api.intent_classifier import _keyword_fallback


class TestKeywordFallback:
    def test_greeting(self):
        assert _keyword_fallback("xin chào") == "greeting_chitchat"
        assert _keyword_fallback("hi") == "greeting_chitchat"
        assert _keyword_fallback("alo") == "greeting_chitchat"

    def test_entertainment(self):
        assert _keyword_fallback("one piece chapter mới nhất") == "entertainment_knowledge"
        assert _keyword_fallback("gojo vs sukuna ai mạnh hơn") == "entertainment_knowledge"
        assert _keyword_fallback("review phim hannibal") == "entertainment_knowledge"
        assert _keyword_fallback("genshin impact build Hu Tao") == "entertainment_knowledge"

    def test_out_of_domain(self):
        assert _keyword_fallback("viết code python cho tôi") == "out_of_domain"
        assert _keyword_fallback("shell sort algorithm") == "out_of_domain"
        assert _keyword_fallback("bitcoin giá bao nhiêu") == "out_of_domain"

    def test_crisis(self):
        assert _keyword_fallback("tôi muốn tự tử") == "crisis_alert"
        assert _keyword_fallback("không muốn sống nữa") == "crisis_alert"

    def test_venting(self):
        assert _keyword_fallback("mình mệt mỏi quá, áp lực công việc") == "psychology_venting"
        assert _keyword_fallback("buồn quá, cô đơn ghê") == "psychology_venting"

    def test_advice(self):
        assert _keyword_fallback("làm sao để hết buồn") == "psychology_advice_seeking"
        assert _keyword_fallback("cho mình lời khuyên đi") == "psychology_advice_seeking"

    def test_short_greeting(self):
        # Short messages without clear title → greeting
        assert _keyword_fallback("hey") == "greeting_chitchat"
        assert _keyword_fallback("yo") == "greeting_chitchat"

    def test_short_with_title(self):
        # Short but contains known title → entertainment
        assert _keyword_fallback("one piece") == "entertainment_knowledge"
        assert _keyword_fallback("genshin") == "entertainment_knowledge"
