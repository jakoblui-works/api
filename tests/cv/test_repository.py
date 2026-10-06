import uuid

import pytest
from redis.asyncio import Redis

from app.cv.repository import _inflight_key, _task_key, claim_generate, release_generate

TTL = 60


def new_id() -> str:
    return uuid.uuid4().hex


@pytest.mark.asyncio
async def test_first_claim_wins(redis: Redis) -> None:
    request_key, task_id = new_id(), new_id()

    assert await claim_generate(redis, request_key, task_id, TTL) == task_id


@pytest.mark.asyncio
async def test_later_claim_gets_the_first_task_id(redis: Redis) -> None:
    request_key, first, second = new_id(), new_id(), new_id()

    await claim_generate(redis, request_key, first, TTL)

    assert await claim_generate(redis, request_key, second, TTL) == first


@pytest.mark.asyncio
async def test_claims_expire(redis: Redis) -> None:
    request_key, task_id = new_id(), new_id()

    await claim_generate(redis, request_key, task_id, TTL)

    assert 0 < await redis.ttl(_inflight_key(request_key)) <= TTL
    assert 0 < await redis.ttl(_task_key(task_id)) <= TTL


@pytest.mark.asyncio
async def test_release_lets_a_new_claim_win(redis: Redis) -> None:
    request_key, first, second = new_id(), new_id(), new_id()
    await claim_generate(redis, request_key, first, TTL)

    await release_generate(redis, first)

    assert await claim_generate(redis, request_key, second, TTL) == second
    assert await redis.exists(_task_key(first)) == 0


@pytest.mark.asyncio
async def test_release_keeps_a_newer_claim(redis: Redis) -> None:
    request_key, stale, newer, third = new_id(), new_id(), new_id(), new_id()
    await claim_generate(redis, request_key, stale, TTL)
    # The stale claim's in-flight key expires while its reverse key is still around, and a newer task claims it.
    await redis.delete(_inflight_key(request_key))
    await claim_generate(redis, request_key, newer, TTL)

    await release_generate(redis, stale)

    assert await claim_generate(redis, request_key, third, TTL) == newer


@pytest.mark.asyncio
async def test_release_of_unknown_task_is_a_no_op(redis: Redis) -> None:
    await release_generate(redis, new_id())
