"""
Tests for /auth endpoints: register, login, google (mock), forgot-password.
"""
import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    res = await client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@example.com",
        "password": "password123",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    payload = {"username": "dupuser", "email": "a@example.com", "password": "pass"}
    await client.post("/auth/register", json=payload)
    res = await client.post("/auth/register", json={
        "username": "dupuser",
        "email": "b@example.com",
        "password": "pass",
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "user1", "email": "same@example.com", "password": "pass"
    })
    res = await client.post("/auth/register", json={
        "username": "user2", "email": "same@example.com", "password": "pass"
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    res = await client.post("/auth/register", json={
        "username": "user3", "email": "not-an-email", "password": "pass"
    })
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "loginuser", "email": "login@example.com", "password": "mypassword"
    })
    res = await client.post("/auth/login", data={
        "username": "loginuser", "password": "mypassword"
    })
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "user_wp", "email": "wp@example.com", "password": "correct"
    })
    res = await client.post("/auth/login", data={
        "username": "user_wp", "password": "wrong"
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    res = await client.post("/auth/login", data={
        "username": "ghost", "password": "pass"
    })
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Forgot password
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forgot_password_always_200(client: AsyncClient):
    """Should return 200 regardless of whether email exists (prevent enumeration)."""
    res = await client.post("/auth/forgot-password", json={"email": "anyone@example.com"})
    assert res.status_code == 200
    assert "message" in res.json()


# ---------------------------------------------------------------------------
# JWT token usage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_authenticated_endpoint_with_valid_token(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "authuser", "email": "auth@example.com", "password": "pass123"
    })
    login = await client.post("/auth/login", data={
        "username": "authuser", "password": "pass123"
    })
    token = login.json()["access_token"]

    res = await client.get(
        "/chat/conversations",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_authenticated_endpoint_without_token(client: AsyncClient):
    res = await client.get("/chat/conversations")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_authenticated_endpoint_invalid_token(client: AsyncClient):
    res = await client.get(
        "/chat/conversations",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert res.status_code == 401
