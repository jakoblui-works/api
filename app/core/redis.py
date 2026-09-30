from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from app.core.config import RedisSettings


def create_redis_client(settings: RedisSettings) -> Redis:
    return Redis.from_url(settings.url, decode_responses=True)


async def get_redis(request: Request) -> Redis:
    return request.app.state.redis


RedisDep = Annotated[Redis, Depends(get_redis)]
