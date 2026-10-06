import hashlib
import json
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from taskiq import InMemoryBroker

from app.core.config import settings
from app.core.database import create_database_engine, get_session
from app.core.redis import create_redis_client
from app.cv.client import GENERATE_V1, PING_V1, CvClient, get_cv_client
from app.cv.schemas import FormOption, FormOptionsResponse, SkillGroup
from app.main import app


@pytest_asyncio.fixture
async def fake_cv_client(broker: InMemoryBroker) -> CvClient:
    @broker.task(task_name=PING_V1)
    async def fake_ping(message: str) -> str:
        return f"pong: {message}"

    fake = CvClient(broker)
    app.dependency_overrides[get_cv_client] = lambda: fake
    return fake


class FakeGenerateWorker:
    """Stands in for cv-service's cv.generate.v1: records each request and returns a key derived from it."""

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []
        self.fail = False

    async def run(self, request: dict[str, object]) -> str:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("compile failed")
        return f"{key_for(request)}.pdf"


def key_for(request: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()


@pytest_asyncio.fixture
async def fake_worker(broker: InMemoryBroker, fake_cv_client: CvClient) -> FakeGenerateWorker:
    worker = FakeGenerateWorker()

    @broker.task(task_name=GENERATE_V1)
    async def fake_generate(request: dict[str, object]) -> str:
        return await worker.run(request)

    return worker


@pytest_asyncio.fixture
async def redis() -> AsyncGenerator[Redis]:
    async with create_redis_client(settings.redis) as client:
        yield client


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    """A session inside a transaction that is always rolled back, also used by the app's routes.

    cv-service owns cv.published_options, so the table may not exist here (e.g. in CI). It is created inside the
    transaction when missing, and any rows written never reach the real database.
    """
    engine = create_database_engine(settings.database)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, join_transaction_mode="create_savepoint")
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS cv"))
        await session.execute(
            text(
                "CREATE TABLE IF NOT EXISTS cv.published_options ("
                " version integer PRIMARY KEY,"
                " options jsonb NOT NULL,"
                " updated_at timestamptz NOT NULL DEFAULT now())"
            )
        )
        await session.execute(text("DELETE FROM cv.published_options"))

        async def override() -> AsyncGenerator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = override
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


def random_options() -> FormOptionsResponse:
    """Options with ids unique to this test, so request keys never collide in the shared Redis."""

    def option(kind: str) -> FormOption:
        suffix = uuid.uuid4().hex[:8]
        return FormOption(id=f"{kind}-{suffix}", label=f"{kind.title()} {suffix}")

    return FormOptionsResponse(
        titles=[option("title") for _ in range(2)],
        concepts=[option("concept") for _ in range(3)],
        skill_groups=[
            SkillGroup(id=f"group-{i}", label=f"Group {i}", skills=[option("skill") for _ in range(3)])
            for i in range(2)
        ],
    )


PublishOptions = Callable[[FormOptionsResponse], Awaitable[None]]


@pytest_asyncio.fixture
async def publish_options(db_session: AsyncSession) -> PublishOptions:
    """Write a version 1 row the way cv-service publishes it."""

    async def publish(options: FormOptionsResponse) -> None:
        await db_session.execute(
            text("INSERT INTO cv.published_options (version, options) VALUES (1, CAST(:options AS jsonb))"),
            {"options": options.model_dump_json()},
        )

    return publish


@pytest_asyncio.fixture
async def published(publish_options: PublishOptions) -> FormOptionsResponse:
    options = random_options()
    await publish_options(options)
    return options
