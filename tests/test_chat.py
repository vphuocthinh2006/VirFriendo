"""
Tests for /chat endpoints: conversations, history, delete, memories, relationship.
Does NOT test the LLM call (mocked out).
"""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _register_and_login(client: AsyncClient, username: str = "chatuser") -> str:
    await client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "pass123",
    })
    res = await client.post("/auth/login", data={"username": username, "password": "pass123"})
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_conversations_empty(client: AsyncClient):
    token = await _register_and_login(client)
    res = await client.get("/chat/conversations", headers=_auth(token))
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_get_conversations_pagination_params(client: AsyncClient):
    token = await _register_and_login(client, "paguser")
    res = await client.get(
        "/chat/conversations?limit=10&offset=0",
        headers=_auth(token),
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_delete_conversation_not_found(client: AsyncClient):
    token = await _register_and_login(client, "deluser")
    fake_id = "00000000-0000-0000-0000-000000000000"
    res = await client.delete(f"/chat/conversations/{fake_id}", headers=_auth(token))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_invalid_uuid(client: AsyncClient):
    token = await _register_and_login(client, "delinvalid")
    res = await client.delete("/chat/conversations/not-a-uuid", headers=_auth(token))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_history_not_found(client: AsyncClient):
    token = await _register_and_login(client, "histuser")
    fake_id = "00000000-0000-0000-0000-000000000001"
    res = await client.get(f"/chat/history/{fake_id}", headers=_auth(token))
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_memories_empty(client: AsyncClient):
    token = await _register_and_login(client, "memuser")
    res = await client.get("/chat/memories", headers=_auth(token))
    assert res.status_code == 200
    assert res.json() == []


# ---------------------------------------------------------------------------
# Relationship
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_relationship_default(client: AsyncClient):
    token = await _register_and_login(client, "reluser")
    res = await client.get(
        "/chat/relationship?agent_id=tuq27",
        headers=_auth(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["user_message_count"] == 0
    assert data["relationship_level"] == 1


@pytest.mark.asyncio
async def test_get_relationship_missing_agent_id(client: AsyncClient):
    token = await _register_and_login(client, "reluser2")
    res = await client.get("/chat/relationship", headers=_auth(token))
    # FastAPI returns 422 when required query param is missing
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_ack_fun_fact(client: AsyncClient):
    token = await _register_and_login(client, "ackuser")
    res = await client.post(
        "/chat/relationship/ack-fun-fact",
        json={"agent_id": "tuq27", "level": 2},
        headers=_auth(token),
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True


# ---------------------------------------------------------------------------
# Chat POST (mock LLM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_post_mocked(client: AsyncClient):
    """POST /chat with mocked LangGraph — verifies routing, not LLM output."""
    token = await _register_and_login(client, "chatpostuser")

    mock_state = {
        "reply": "Hello from mock!",
        "intent": "greeting_chitchat",
        "emotion": "happy",
        "avatar_action": "wave",
        "bibliotherapy_suggestion": None,
    }

    with patch(
        "services.core.api.chat._invoke_agent",
        new=AsyncMock(return_value=mock_state),
    ):
        res = await client.post(
            "/chat",
            json={"message": "Hello!", "conversation_id": None, "agent_id": "tuq27"},
            headers=_auth(token),
        )

    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    assert data["reply"] == "Hello from mock!"
    assert data["detected_intent"] == "greeting_chitchat"


@pytest.mark.asyncio
async def test_chat_post_creates_conversation(client: AsyncClient):
    """Second message with same conversation_id should reuse conversation."""
    token = await _register_and_login(client, "convuser")

    mock_state = {
        "reply": "reply",
        "intent": "greeting_chitchat",
        "emotion": "idle",
        "avatar_action": None,
        "bibliotherapy_suggestion": None,
    }

    with patch(
        "services.core.api.chat._invoke_agent",
        new=AsyncMock(return_value=mock_state),
    ):
        r1 = await client.post(
            "/chat",
            json={"message": "Hi", "conversation_id": None},
            headers=_auth(token),
        )
        conv_id = r1.json()["conversation_id"]

        r2 = await client.post(
            "/chat",
            json={"message": "How are you?", "conversation_id": conv_id},
            headers=_auth(token),
        )

    assert r2.status_code == 200
    assert r2.json()["conversation_id"] == conv_id

    # Verify conversation appears in list
    convs = await client.get("/chat/conversations", headers=_auth(token))
    ids = [c["id"] for c in convs.json()]
    assert conv_id in ids
