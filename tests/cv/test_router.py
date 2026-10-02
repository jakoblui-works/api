import asyncio

import pytest
from httpx import AsyncClient


async def poll_until_finished(client: AsyncClient, task_id: str, limit: float = 2.0) -> dict[str, object]:
    """Poll the status endpoint until the task is no longer pending."""
    async with asyncio.timeout(limit):
        while True:
            response = await client.get(f"/cv/ping/{task_id}")
            body = response.json()
            if body["state"] != "pending":
                return body
            await asyncio.sleep(0.01)


@pytest.mark.covers_endpoint("cv_ping")
@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_cv_client")
async def test_cv_ping(client: AsyncClient) -> None:
    response = await client.post("/cv/ping", json={"message": "hello"})
    assert response.status_code == 202
    assert "task_id" in response.json()


@pytest.mark.covers_endpoint("cv_ping_status")
@pytest.mark.asyncio
@pytest.mark.usefixtures("fake_cv_client")
async def test_cv_ping_status(client: AsyncClient) -> None:
    response = await client.post("/cv/ping", json={"message": "hello"})
    task_id = response.json()["task_id"]

    body = await poll_until_finished(client, task_id)
    assert body["state"] == "done"
    assert body["result"] == "pong: hello"
