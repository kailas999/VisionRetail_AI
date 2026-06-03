"""
pytest fixtures and configuration for VisionRetail AI tests.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.database import Base, get_db
from app.models.db_models import Store

# ── In-memory SQLite for tests ──────────────────────────────────────────────
import os
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")



@pytest_asyncio.fixture
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB override."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def sample_store_id() -> str:
    return "STORE_BLR_002"


@pytest.fixture
def sample_event_payload(sample_store_id):
    return {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "store_id": sample_store_id,
                "visitor_id": "VIS_TEST001",
                "event_type": "ENTRY",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": 0.92,
                "is_staff": False,
            }
        ]
    }
