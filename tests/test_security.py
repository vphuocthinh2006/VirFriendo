"""Tests for security: rate limiting, auth edge cases."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_rate_limit_login(client: AsyncClient):
    """After 10 failed logins from same IP, should get 429."""
    for _ in range(10):
        await client.post("/auth/login", data={"username": "ghost", "password": "wrong"})

    res = await client.post("/auth/login", data={"username": "ghost", "password": "wrong"})
    assert res.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_register(client: AsyncClient):
    """After 10 register attempts, should get 429."""
    for i in range(10):
        await client.post("/auth/register", json={
            "username": f"ratelimituser{i}",
            "email": f"rl{i}@example.com",
            "password": "pass",
        })

    res = await client.post("/auth/register", json={
        "username": "ratelimituser_extra",
        "email": "rl_extra@example.com",
        "password": "pass",
    })
    assert res.status_code == 429


@pytest.mark.asyncio
async def test_no_password_in_register_response(client: AsyncClient):
    """Password hash must never be returned."""
    res = await client.post("/auth/register", json={
        "username": "secuser", "email": "sec@example.com", "password": "secret123"
    })
    assert res.status_code == 201
    body = res.text
    assert "secret123" not in body
    assert "password_hash" not in body
    assert "password" not in res.json()


@pytest.mark.asyncio
async def test_bearer_token_required(client: AsyncClient):
    """Protected endpoints must reject requests without token."""
    protected = [
        ("GET", "/chat/conversations"),
        ("GET", "/chat/memories"),
        ("GET", "/chat/relationship?agent_id=tuq27"),
    ]
    for method, path in protected:
        res = await client.request(method, path)
        assert res.status_code == 401, f"{method} {path} should be 401"
