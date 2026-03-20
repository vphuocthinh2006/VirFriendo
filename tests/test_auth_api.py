"""Integration tests for /auth endpoints (register + login)."""
import pytest


@pytest.mark.asyncio
async def test_register_new_user(client):
    resp = await client.post("/auth/register", json={
        "username": "alice",
        "email": "alice@example.com",
        "password": "Str0ngP@ss",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert "id" in body
    assert "password" not in body and "password_hash" not in body


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    payload = {"username": "bob", "email": "bob@example.com", "password": "Pass1234"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json={
        "username": "bob",
        "email": "bob2@example.com",
        "password": "Pass1234",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/auth/register", json={
        "username": "carol",
        "email": "carol@example.com",
        "password": "Secret99",
    })
    resp = await client.post("/auth/login", data={
        "username": "carol",
        "password": "Secret99",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "username": "dave",
        "email": "dave@example.com",
        "password": "Correct1",
    })
    resp = await client.post("/auth/login", data={
        "username": "dave",
        "password": "WrongPass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    resp = await client.post("/auth/login", data={
        "username": "ghost",
        "password": "whatever",
    })
    assert resp.status_code == 401
