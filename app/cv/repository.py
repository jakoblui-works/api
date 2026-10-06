from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3 import S3Client

from app.core.config import settings


async def get_published_options(session: AsyncSession, version: int) -> object | None:
    """Raw published form options for a shape version, or None if cv-service hasn't published it."""
    result = await session.execute(
        text("SELECT options FROM cv.published_options WHERE version = :version"),
        {"version": version},
    )
    return result.scalar_one_or_none()


async def get_pdf(s3: S3Client, digest: str) -> bytes | None:
    """A compiled CV's PDF bytes, or None if it isn't in the bucket. cv-service stores them as "<digest>.pdf"."""
    try:
        obj = await s3.get_object(Bucket=settings.cv.bucket, Key=f"{digest}.pdf")
    except s3.exceptions.NoSuchKey:
        return None

    return await obj["Body"].read()


# In-flight generate claims. "v1" follows the cv.generate.v1 contract, so a new contract gets its own keys.
def _inflight_key(request_key: str) -> str:
    return f"cv:generate:v1:{request_key}"


def _task_key(task_id: str) -> str:
    return f"cv:generate:v1:task:{task_id}"


async def claim_generate(redis: Redis, request_key: str, task_id: str, ttl: int) -> str:
    await redis.set(_task_key(task_id), request_key, ex=ttl)

    existing = await redis.set(_inflight_key(request_key), task_id, nx=True, get=True, ex=ttl)

    if existing is None:
        return task_id

    if not isinstance(existing, str):
        raise TypeError(f"Expected str from SET ... GET, got {type(existing).__name__}")

    return existing


async def release_generate(redis: Redis, task_id: str) -> None:
    request_key = await redis.get(_task_key(task_id))

    if request_key is None:
        return

    if not isinstance(request_key, str):
        raise TypeError(f"Expected str from GET, got {type(request_key).__name__}")

    await redis.delex(_inflight_key(request_key), ifeq=task_id)

    await redis.delete(_task_key(task_id))
