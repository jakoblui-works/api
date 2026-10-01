import logging

from fastapi import APIRouter

from app.core.database import SessionDep
from app.core.redis import RedisDep
from app.core.s3 import S3Dep
from app.core.schemas import StatusResponse
from app.health.service import check_readiness

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> StatusResponse:
    return StatusResponse(status="ok")


@router.get("/health/ready")
async def ready_check(session: SessionDep, redis: RedisDep, s3: S3Dep) -> StatusResponse:

    await check_readiness(
        session=session,
        redis=redis,
        s3=s3,
    )

    return StatusResponse(status="ok")
