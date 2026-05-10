"""Tests for LLM Agent (services/agent_service/llm_agent.py)."""
import os
import pytest
from unittest.mock import patch, AsyncMock

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-32chars!!")

from langchain_core.messages import HumanMessage, AIMessage
from services.agent_service.llm_agent import (
    run_agent,
    _build_system,
    _extract_last_user_text,
    _infer_emotion,
    _emotion_to_action,
)


class TestBuildSystem:
    def test_basic_system_prompt(self):
        prompt = _build_system("tuq27")
        assert "tuq27" in prompt
        assert "Tiếng Việt" in prompt

    def test_with_memories(self):
        prompt = _build_system("tuq27", memories=["likes anime", "name is Thinh"])
        assert "likes anime" in prompt
        assert "name is Thinh" in prompt

    def test_without_memories(self):
        prompt = _build_system("tuq27", memories=None)
        assert "Thông tin đã biết" not in prompt


class TestExtractLastUserText:
    def test_single_message(self):
        msgs = [HumanMessage(content="hello")]
        assert _extract_last_user_text(msgs) == "hello"

    def test_multiple_messages(self):
        msgs = [
            HumanMessage(content="first"),
            AIMessage(content="reply"),
            HumanMessage(content="second"),
        ]
        assert _extract_last_user_text(msgs) == "second"

    def test_empty_messages(self):
        assert _extract_last_user_text([]) == ""

    def test_only_ai_messages(self):
        msgs = [AIMessage(content="hi")]
        assert _extract_last_user_text(msgs) == ""


class TestInferEmotion:
    def test_happy(self):
        assert _infer_emotion("haha vui quá") == "happy"

    def test_sad(self):
        assert _infer_emotion("mình buồn quá") == "sad"

    def test_surprised(self):
        assert _infer_emotion("wow không ngờ luôn") == "surprised"

    def test_crisis(self):
        assert _infer_emotion("không muốn sống nữa") == "crisis"

    def test_neutral(self):
        assert _infer_emotion("hôm nay trời đẹp") == "neutral"


class TestEmotionToAction:
    def test_all_mappings(self):
        assert _emotion_to_action("happy") == "excited_wave"
        assert _emotion_to_action("sad") == "comfort_sit"
        assert _emotion_to_action("surprised") == "shocked_face"
        assert _emotion_to_action("crisis") == "serious_alert"
        assert _emotion_to_action("neutral") == "idle_typing"
        assert _emotion_to_action("unknown") == "idle_typing"


@pytest.mark.asyncio
class TestRunAgent:
    @patch("services.agent_service.llm_agent.generate_with_history", new_callable=AsyncMock)
    @patch("services.agent_service.llm_agent._should_search", new_callable=AsyncMock)
    async def test_basic_reply(self, mock_search, mock_generate):
        mock_search.return_value = False
        mock_generate.return_value = "Chào bạn! Mình là tuq27~"

        result = await run_agent([HumanMessage(content="hello")], agent_id="tuq27")

        assert result["reply"] == "Chào bạn! Mình là tuq27~"
        assert result["emotion"] == "neutral"
        assert result["avatar_action"] == "idle_typing"
        assert result["model_info"] is not None

    @patch("services.agent_service.llm_agent.generate_with_history", new_callable=AsyncMock)
    @patch("services.agent_service.llm_agent._should_search", new_callable=AsyncMock)
    async def test_empty_reply_fallback(self, mock_search, mock_generate):
        mock_search.return_value = False
        mock_generate.side_effect = [None, None]  # Both attempts fail

        result = await run_agent([HumanMessage(content="test")], agent_id="tuq27")

        assert "test" in result["reply"]  # Fallback includes user text
        assert result["reply"] != ""

    @patch("services.agent_service.llm_agent._do_web_search", new_callable=AsyncMock)
    @patch("services.agent_service.llm_agent.generate_with_history", new_callable=AsyncMock)
    @patch("services.agent_service.llm_agent._should_search", new_callable=AsyncMock)
    async def test_web_search_triggered(self, mock_search, mock_generate, mock_web):
        mock_search.return_value = True
        mock_web.return_value = "• One Piece chapter 1120 released"
        mock_generate.return_value = "Chapter mới nhất là 1120!"

        result = await run_agent(
            [HumanMessage(content="one piece chap mới nhất")],
            agent_id="tuq27",
        )

        assert result["model_info"]["web_search_used"] is True
        mock_web.assert_called_once()
