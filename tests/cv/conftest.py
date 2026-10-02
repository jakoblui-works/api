import pytest_asyncio
from taskiq import InMemoryBroker

from app.cv.client import PING_V1, CvClient, get_cv_client
from app.main import app


@pytest_asyncio.fixture
async def fake_cv_client(broker: InMemoryBroker) -> CvClient:
    @broker.task(task_name=PING_V1)
    async def fake_ping(message: str) -> str:
        return f"pong: {message}"

    fake = CvClient(broker)
    app.dependency_overrides[get_cv_client] = lambda: fake
    return fake
