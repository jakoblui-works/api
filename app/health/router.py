import logging

from fastapi import APIRouter

from app.core.database import SessionDep
from app.core.redis import RedisDep
from app.core.s3 import S3Dep
from app.core.schemas import StatusResponse
from app.health.service import check_readiness

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=StatusResponse)
async def health_check():
    return {"status": "ok"}


@router.get("/health/ready", response_model=StatusResponse)
async def ready_check(session: SessionDep, redis: RedisDep, s3: S3Dep):

    await check_readiness(
        session=session,
        redis=redis,
        s3=s3,
    )

    return {"status": "ok"}
