import asyncio
from typing import NoReturn

import pytest
from taskiq import InMemoryBroker

from app.core.queue import ServiceClient, ServiceTaskError


@pytest.mark.asyncio
async def test_service_client_failure(broker: InMemoryBroker) -> None:
    @broker.task(task_name="test.fails.v1")
    async def mock_service_failure() -> NoReturn:
        raise ValueError("boom")

    with pytest.raises(ServiceTaskError):
        await ServiceClient(broker)._call("test.fails.v1")


@pytest.mark.asyncio
async def test_service_client_timeout(broker: InMemoryBroker) -> None:
    @broker.task(task_name="test.slow.v1")
    async def mock_service_timeout() -> None:
        await asyncio.sleep(0.5)

    with pytest.raises(ServiceTaskError):
        await ServiceClient(broker)._call("test.slow.v1", timeout=0.05)
