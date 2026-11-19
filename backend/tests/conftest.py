from collections.abc import AsyncIterator
from uuid import UUID

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from invoice_agent.api.auth import Principal, current_principal
from invoice_agent.main import app
from invoice_agent.persistence.database import get_session
from invoice_agent.persistence.models import Base, Tenant


@pytest_asyncio.fixture
async def test_client() -> AsyncIterator[tuple[AsyncClient, async_sessionmaker[AsyncSession]]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(Tenant(id=UUID("00000000-0000-4000-8000-000000000001"), name="Test Tenant"))
        await session.commit()

    async def session_dependency() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def principal_dependency() -> Principal:
        return Principal(
            "test-operator",
            UUID("00000000-0000-4000-8000-000000000001"),
            frozenset({"operator", "reviewer"}),
            "test-csrf-token",
        )

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[current_principal] = principal_dependency
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.clear()
    await engine.dispose()
