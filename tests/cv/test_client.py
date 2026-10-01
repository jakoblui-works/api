import pytest
from taskiq import InMemoryBroker

from app.cv.client import PING_V1, CvClient


@pytest.mark.asyncio
async def test_ping(broker: InMemoryBroker) -> None:
    @broker.task(task_name=PING_V1)
    async def mock_ping(message: str) -> str:
        return f"pong: {message}"

    assert await CvClient(broker).ping("hello") == "pong: hello"
