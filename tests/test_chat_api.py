"""Integration tests for /chat endpoints (conversations, history, delete).

POST /chat is tested lightly because it invokes the full LangGraph pipeline
which requires external LLM APIs. The conversation management endpoints
(list, history, delete) are tested fully.
"""
import uuid
import pytest
from sqlalchemy import select

from services.core.models import Conversation, Message


@pytest.mark.asyncio
async def test_get_conversations_empty(client, auth_token):
    token, _ = auth_token
    resp = await client.get("/chat/conversations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_conversations_unauthorized(client):
    resp = await client.get("/chat/conversations")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_history_not_found(client, auth_token):
    token, _ = auth_token
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/chat/history/{fake_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation_not_found(client, auth_token):
    token, _ = auth_token
    fake_id = str(uuid.uuid4())
    resp = await client.delete(f"/chat/conversations/{fake_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_conversation_crud_flow(client, auth_token, db_session):
    """Create a conversation + messages directly in DB, then test list/history/delete."""
    token, user_id = auth_token
    user_uuid = uuid.UUID(user_id)

    conv = Conversation(user_id=user_uuid, title="Test convo")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    msg1 = Message(conversation_id=conv.id, role="user", content="hello")
    msg2 = Message(conversation_id=conv.id, role="assistant", content="hey there!")
    db_session.add_all([msg1, msg2])
    await db_session.commit()

    # List conversations
    resp = await client.get("/chat/conversations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    convos = resp.json()
    assert len(convos) == 1
    assert convos[0]["title"] == "Test convo"

    # Get history
    resp = await client.get(f"/chat/history/{conv.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    msgs = resp.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"

    # Delete
    resp = await client.delete(f"/chat/conversations/{conv.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    # Verify gone
    resp = await client.get("/chat/conversations", headers={"Authorization": f"Bearer {token}"})
    assert resp.json() == []


@pytest.mark.asyncio
async def test_other_user_cannot_access_conversation(client, auth_token, db_session):
    """User A's conversation is not visible to User B."""
    token_a, user_a_id = auth_token
    user_a_uuid = uuid.UUID(user_a_id)

    conv = Conversation(user_id=user_a_uuid, title="A's convo")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Register user B
    unique = uuid.uuid4().hex[:8]
    await client.post("/auth/register", json={
        "username": f"userb_{unique}",
        "email": f"userb_{unique}@example.com",
        "password": "Pass1234",
    })
    login_b = await client.post("/auth/login", data={
        "username": f"userb_{unique}",
        "password": "Pass1234",
    })
    token_b = login_b.json()["access_token"]

    # User B tries to access User A's conversation
    resp = await client.get(f"/chat/history/{conv.id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404
