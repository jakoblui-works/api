from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac


covered_names: set[str] = set()


def pytest_collection_modifyitems(items: list[pytest.Item]):
    for item in items:
        marker = item.get_closest_marker("covers_endpoint")
        if not marker:
            continue
        covered_names.add(marker.args[0])
