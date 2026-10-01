from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from taskiq import InMemoryBroker

from app.main import app


@pytest_asyncio.fixture
async def broker() -> AsyncGenerator[InMemoryBroker]:
    broker = InMemoryBroker()
    await broker.startup()
    yield broker
    await broker.shutdown()


@pytest.fixture(autouse=True)
def clear_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


covered_names: set[str] = set()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        marker = item.get_closest_marker("covers_endpoint")
        if not marker:
            continue
        covered_names.add(marker.args[0])
