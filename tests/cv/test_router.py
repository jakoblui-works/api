import asyncio
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.core.s3 import get_s3
from app.main import app


async def poll_until_finished(client: AsyncClient, task_id: str, limit: float = 2.0) -> dict[str, object]:
    """Poll the status endpoint until the task is no longer pending."""
    async with asyncio.timeout(limit):
        while True:
            response = await client.get(f"/cv/ping/{task_id}")
            body = response.json()
            if body["state"] != "pending":
                return body
            await asyncio.sleep(0.01)


class NoSuchKey(Exception):
    pass


class FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


class FakeS3:
    exceptions = SimpleNamespace(NoSuchKey=NoSuchKey)

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    async def get_object(self, Bucket: str, Key: str) -> dict:
        if Key not in self.objects:
            raise NoSuchKey
        return {"Body": FakeBody(self.objects[Key])}


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


DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64


@pytest.mark.covers_endpoint("cv_get_pdf")
@pytest.mark.asyncio
async def test_cv_get_pdf_found(client: AsyncClient) -> None:
    app.dependency_overrides[get_s3] = lambda: FakeS3({DIGEST + ".pdf": b"%PDF-fake"})

    response = await client.get(f"/cv/pdf/{DIGEST}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-fake"


@pytest.mark.covers_endpoint("cv_get_pdf")
@pytest.mark.asyncio
async def test_cv_get_pdf_missing(client: AsyncClient) -> None:
    app.dependency_overrides[get_s3] = lambda: FakeS3({DIGEST + ".pdf": b"%PDF-fake"})

    response = await client.get(f"/cv/pdf/{OTHER_DIGEST}")

    assert response.status_code == 404


@pytest.mark.covers_endpoint("cv_get_pdf")
@pytest.mark.asyncio
async def test_cv_get_pdf_invalid(client: AsyncClient) -> None:

    response = await client.get("/cv/pdf/abc")

    assert response.status_code == 422
