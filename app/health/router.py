import asyncio
import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.core.database import SessionDep
from app.core.schemas import StatusResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=StatusResponse)
async def health_check():
    return {"status": "ok"}


@router.get("/health/ready", response_model=StatusResponse)
async def ready_check(session: SessionDep):
    try:
        async with asyncio.timeout(3):
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed.")
        raise HTTPException(status_code=503, detail="Service unavailable")

    return {"status": "ok"}
