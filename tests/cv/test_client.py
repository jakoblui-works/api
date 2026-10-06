import asyncio
import hashlib
import json
import uuid
from typing import NoReturn

import pytest
from hypothesis import given
from hypothesis import strategies as st
from taskiq import InMemoryBroker, TaskiqResult

from app.cv.client import GENERATE_V1, PING_V1, CvClient
from app.cv.schemas import DIGEST_PATTERN, GenerateStatusResponse

digests = st.from_regex(DIGEST_PATTERN, fullmatch=True)

# Results that look nothing like an S3 key, and ones that nearly do.
malformed_results = st.one_of(
    st.none(),
    st.integers(),
    st.lists(st.text()),
    st.text().filter(lambda s: not s.endswith(".pdf")),
    digests,
    digests.map(lambda d: f"{d}.png"),
    digests.map(lambda d: f"{d[:-1]}.pdf"),
    digests.filter(lambda d: d != d.upper()).map(lambda d: f"{d.upper()}.pdf"),
    digests.map(lambda d: f"{d}\n.pdf"),
    digests.map(lambda d: f"{d}.pdf\n"),
)


async def wait_for_generate(client: CvClient, task_id: str, limit: float = 2.0) -> GenerateStatusResponse:
    """Poll a generate task until it's no longer pending, failing after `limit` seconds."""
    async with asyncio.timeout(limit):
        while (status := await client.generate_status(task_id)).state == "pending":
            await asyncio.sleep(0.01)
    return status


async def finished_task(result: object) -> tuple[CvClient, str]:
    """A client whose result backend already holds a successful task returning `result`."""
    broker = InMemoryBroker()
    task_id = uuid.uuid4().hex
    await broker.result_backend.set_result(task_id, TaskiqResult(is_err=False, return_value=result, execution_time=0.0))
    return CvClient(broker), task_id


@pytest.mark.asyncio
async def test_ping(broker: InMemoryBroker) -> None:
    @broker.task(task_name=PING_V1)
    async def mock_ping(message: str) -> str:
        return f"pong: {message}"

    assert await CvClient(broker).ping("hello") == "pong: hello"


@pytest.mark.asyncio
async def test_generate_uses_chosen_task_id_and_reports_digest(broker: InMemoryBroker) -> None:
    seen: dict[str, object] = {}

    @broker.task(task_name=GENERATE_V1)
    async def fake_generate(request: dict[str, object]) -> str:
        seen["request"] = request
        seen["key"] = key = f"{hashlib.sha256(json.dumps(request).encode()).hexdigest()}.pdf"
        return key

    client = CvClient(broker)
    request: dict[str, object] = {"title": "some-title", "concepts": ["a", "b"], "skills": []}
    task_id = uuid.uuid4().hex

    assert await client.start_generate(request, task_id=task_id) == task_id

    status = await wait_for_generate(client, task_id)

    assert seen["request"] == request
    assert status.state == "done"
    assert status.digest is not None
    assert f"{status.digest}.pdf" == seen["key"]


@pytest.mark.asyncio
async def test_generate_status_failed_when_worker_raises(broker: InMemoryBroker) -> None:
    @broker.task(task_name=GENERATE_V1)
    async def fake_generate(request: dict[str, object]) -> NoReturn:
        raise ValueError("boom")

    client = CvClient(broker)
    task_id = await client.start_generate({}, task_id=uuid.uuid4().hex)

    status = await wait_for_generate(client, task_id)

    assert status.state == "failed"
    assert status.digest is None


@pytest.mark.asyncio
async def test_generate_status_pending_for_unknown_task(broker: InMemoryBroker) -> None:
    status = await CvClient(broker).generate_status("does-not-exist")

    assert status.state == "pending"
    assert status.digest is None


@pytest.mark.asyncio
@given(digest=digests)
async def test_generate_status_extracts_digest_from_key(digest: str) -> None:
    client, task_id = await finished_task(f"{digest}.pdf")

    status = await client.generate_status(task_id)

    assert status.state == "done"
    assert status.digest == digest


@pytest.mark.asyncio
@given(result=malformed_results)
async def test_generate_status_fails_on_malformed_result(result: object) -> None:
    client, task_id = await finished_task(result)

    status = await client.generate_status(task_id)

    assert status.state == "failed"
    assert status.digest is None
