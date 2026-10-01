import asyncio
from typing import NoReturn

import pytest
from taskiq import InMemoryBroker

from app.core.queue import ServiceClient, ServiceTaskError, TaskStatus


async def wait_until_finished(client: ServiceClient, task_id: str, limit: float = 2.0) -> TaskStatus:
    """Poll a task's status until it's no longer pending, failing after `limit` seconds."""
    async with asyncio.timeout(limit):
        while (status := await client._status(task_id)).state == "pending":
            await asyncio.sleep(0.01)
    return status


@pytest.mark.asyncio
async def test_service_client_failure(broker: InMemoryBroker) -> None:
    @broker.task(task_name="test.fails")
    async def mock_service_failure() -> NoReturn:
        raise ValueError("boom")

    with pytest.raises(ServiceTaskError):
        await ServiceClient(broker)._call("test.fails")


@pytest.mark.asyncio
async def test_service_client_timeout(broker: InMemoryBroker) -> None:
    @broker.task(task_name="test.slow")
    async def mock_service_timeout() -> None:
        await asyncio.sleep(0.5)

    with pytest.raises(ServiceTaskError):
        await ServiceClient(broker)._call("test.slow", timeout=0.05)


@pytest.mark.asyncio
async def test_service_client_status_done(broker: InMemoryBroker) -> None:
    @broker.task(task_name="test.done")
    async def mock_service_task_done() -> str:
        return "worked"

    client = ServiceClient(broker)

    task_id = await client._send("test.done")

    task_result = await wait_until_finished(client, task_id)

    assert task_result.state == "done"
    assert task_result.result == "worked"


@pytest.mark.asyncio
async def test_service_client_status_failed(broker: InMemoryBroker) -> None:
    @broker.task(task_name="test.failed")
    async def mock_service_task_failed() -> NoReturn:
        raise ValueError("boom")

    client = ServiceClient(broker)

    task_id = await client._send("test.failed")

    task_result = await wait_until_finished(client, task_id)

    assert task_result.state == "failed"
    assert task_result.result is None


@pytest.mark.asyncio
async def test_service_client_status_pending(broker: InMemoryBroker) -> None:

    client = ServiceClient(broker)

    task_result = await client._status("does-not-exist")

    assert task_result.state == "pending"
    assert task_result.result is None
