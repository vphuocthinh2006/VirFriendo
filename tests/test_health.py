"""Tests for /health and basic app setup."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "project" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_404_unknown_route(client: AsyncClient):
    res = await client.get("/this-route-does-not-exist")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_security_headers(client: AsyncClient):
    res = await client.get("/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
