"""
Shared fixtures for VirFriendo test suite.

Uses an in-memory SQLite database (via aiosqlite) so tests run without Docker.
PostgreSQL-specific UUID columns are compiled as VARCHAR(36) for SQLite.
"""
import os, sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

import uuid
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.compiler import compiles

@compiles(PG_UUID, "sqlite")
def _pg_uuid_to_sqlite(element, compiler, **kw):
    return "VARCHAR(36)"

from services.core.database import Base, get_db
from services.core.models import User, Conversation, Message, UserMemory  # noqa: F401 — register models
from services.core.main import app

_test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_TestSession = async_sessionmaker(bind=_test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _override_get_db():
    async with _TestSession() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client():
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def db_session():
    async with _TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def auth_token(client):
    """Register a user and return (token, user_id) tuple."""
    unique = uuid.uuid4().hex[:8]
    reg = await client.post("/auth/register", json={
        "username": f"testuser_{unique}",
        "email": f"test_{unique}@example.com",
        "password": "TestPass123!",
    })
    assert reg.status_code == 201
    login = await client.post("/auth/login", data={
        "username": f"testuser_{unique}",
        "password": "TestPass123!",
    })
    assert login.status_code == 200
    token = login.json()["access_token"]
    user_id = reg.json()["id"]
    return token, user_id
