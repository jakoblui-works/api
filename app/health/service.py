import asyncio
import logging
from collections.abc import Awaitable

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3 import S3Client

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _check(name: str, probe: Awaitable[object]) -> None:
    try:
        async with asyncio.timeout(3):
            await probe
    except Exception:
        logger.exception("Readiness check failed: %s", name)
        raise HTTPException(status_code=503, detail="Service unavailable")


async def check_readiness(session: AsyncSession, redis: Redis, s3: S3Client) -> None:
    await _check("Database", session.execute(text("SELECT 1")))
    await _check("Redis", redis.ping())
    await _check("S3", s3.head_bucket(Bucket=settings.cv.bucket))
