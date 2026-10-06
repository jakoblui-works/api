import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.s3 import get_s3
from app.cv.schemas import FormOptionsResponse
from app.main import app
from tests.cv.conftest import FakeGenerateWorker, key_for


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


async def poll_generate(client: AsyncClient, task_id: str, limit: float = 2.0) -> dict[str, object]:
    """Poll the generate status endpoint until the task is no longer pending."""
    async with asyncio.timeout(limit):
        while True:
            body: dict[str, object] = (await client.get(f"/cv/generate/{task_id}")).json()
            if body["state"] != "pending":
                return body
            await asyncio.sleep(0.01)


def valid_body(options: FormOptionsResponse) -> dict[str, Any]:
    return {
        "title_id": options.titles[0].id,
        "concept_ids": [c.id for c in options.concepts[:2]],
        "skill_ids": [options.skill_groups[0].skills[0].id, options.skill_groups[1].skills[0].id],
    }


@pytest.mark.covers_endpoint("cv_get_options")
@pytest.mark.asyncio
async def test_cv_get_options(client: AsyncClient, published: FormOptionsResponse) -> None:
    response = await client.get("/cv/options")

    assert response.status_code == 200
    assert FormOptionsResponse.model_validate(response.json()) == published


@pytest.mark.covers_endpoint("cv_get_options")
@pytest.mark.asyncio
@pytest.mark.usefixtures("db_session")
async def test_cv_get_options_unpublished(client: AsyncClient) -> None:
    response = await client.get("/cv/options")

    assert response.status_code == 503


@pytest.mark.covers_endpoint("cv_generate")
@pytest.mark.asyncio
async def test_cv_generate_sends_the_canonical_request(
    client: AsyncClient, published: FormOptionsResponse, fake_worker: FakeGenerateWorker
) -> None:
    body = valid_body(published)

    response = await client.post("/cv/generate", json=body)
    assert response.status_code == 202
    await poll_generate(client, response.json()["task_id"])

    assert fake_worker.requests == [
        {
            "title_id": body["title_id"],
            "concept_ids": sorted(body["concept_ids"]),
            "skill_ids": sorted(body["skill_ids"]),
        }
    ]


@pytest.mark.covers_endpoint("cv_generate")
@pytest.mark.asyncio
async def test_cv_generate_same_request_shares_one_task(
    client: AsyncClient, published: FormOptionsResponse, fake_worker: FakeGenerateWorker
) -> None:
    body = valid_body(published)
    concept_ids = body["concept_ids"]
    reordered = {**body, "concept_ids": [*reversed(concept_ids), concept_ids[0]]}

    first = (await client.post("/cv/generate", json=body)).json()["task_id"]
    again = (await client.post("/cv/generate", json=body)).json()["task_id"]
    shuffled = (await client.post("/cv/generate", json=reordered)).json()["task_id"]
    await poll_generate(client, first)

    assert first == again == shuffled
    assert len(fake_worker.requests) == 1


@pytest.mark.covers_endpoint("cv_generate")
@pytest.mark.asyncio
async def test_cv_generate_different_requests_get_different_tasks(
    client: AsyncClient, published: FormOptionsResponse, fake_worker: FakeGenerateWorker
) -> None:
    body = valid_body(published)
    other = {**body, "title_id": published.titles[1].id}

    first = (await client.post("/cv/generate", json=body)).json()["task_id"]
    second = (await client.post("/cv/generate", json=other)).json()["task_id"]

    assert first != second


@pytest.mark.covers_endpoint("cv_generate")
@pytest.mark.asyncio
async def test_cv_generate_unknown_id(
    client: AsyncClient, published: FormOptionsResponse, fake_worker: FakeGenerateWorker
) -> None:
    body = {**valid_body(published), "skill_ids": ["no-such-skill"]}

    response = await client.post("/cv/generate", json=body)

    assert response.status_code == 422
    assert [error["loc"] for error in response.json()["detail"]] == [["body", "skill_ids", 0]]
    assert fake_worker.requests == []


@pytest.mark.covers_endpoint("cv_generate")
@pytest.mark.asyncio
@pytest.mark.usefixtures("db_session", "fake_worker")
async def test_cv_generate_unpublished(client: AsyncClient) -> None:
    response = await client.post("/cv/generate", json={"title_id": "anything"})

    assert response.status_code == 503


@pytest.mark.covers_endpoint("cv_generate_status")
@pytest.mark.asyncio
async def test_cv_generate_status_done(
    client: AsyncClient, published: FormOptionsResponse, fake_worker: FakeGenerateWorker
) -> None:
    task_id = (await client.post("/cv/generate", json=valid_body(published))).json()["task_id"]

    status = await poll_generate(client, task_id)

    assert status == {"state": "done", "digest": key_for(fake_worker.requests[0])}


@pytest.mark.covers_endpoint("cv_generate_status")
@pytest.mark.asyncio
async def test_cv_generate_status_failed_frees_the_request(
    client: AsyncClient, published: FormOptionsResponse, fake_worker: FakeGenerateWorker
) -> None:
    body = valid_body(published)
    fake_worker.fail = True
    failed = (await client.post("/cv/generate", json=body)).json()["task_id"]

    status = await poll_generate(client, failed)
    retry = (await client.post("/cv/generate", json=body)).json()["task_id"]

    assert status["state"] == "failed"
    assert retry != failed


@pytest.mark.covers_endpoint("cv_generate_status")
@pytest.mark.asyncio
async def test_cv_generate_status_invalid_task_id(client: AsyncClient) -> None:
    response = await client.get("/cv/generate/not-a-task-id")

    assert response.status_code == 422
