import pytest
from httpx import AsyncClient


@pytest.mark.covers_endpoint("health_check")
@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.covers_endpoint("ready_check")
@pytest.mark.asyncio
async def test_ready_check(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
