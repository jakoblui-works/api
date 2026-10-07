from typing import Annotated

from fastapi import APIRouter, Path, Response

from app.core.database import SessionDep
from app.core.redis import RedisDep
from app.core.s3 import S3Dep
from app.core.schemas import ErrorResponse
from app.cv.client import CvClientDep
from app.cv.schemas import (
    DIGEST_PATTERN,
    FormOptionsResponse,
    GenerateRequest,
    GenerateStartedResponse,
    GenerateStatusResponse,
    PingRequest,
    PingStartedResponse,
    PingStatusResponse,
)
from app.cv.service import get_cv_generation_status, get_cv_pdf, get_form_options, start_cv_generation

router = APIRouter(prefix="/cv", tags=["cv"])

Digest = Annotated[str, Path(pattern=DIGEST_PATTERN)]
TaskId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]


@router.post("/ping", status_code=202)
async def cv_ping(client: CvClientDep, body: PingRequest) -> PingStartedResponse:
    task_id = await client.start_ping(message=body.message)

    return PingStartedResponse(task_id=task_id)


@router.get("/ping/{task_id}")
async def cv_ping_status(client: CvClientDep, task_id: str) -> PingStatusResponse:
    status = await client.ping_status(task_id)
    result = str(status.result) if status.result is not None else None

    return PingStatusResponse(state=status.state, result=result)


@router.get("/pdf/{digest}")
async def cv_get_pdf(digest: Digest, s3: S3Dep) -> Response:
    pdf = await get_cv_pdf(s3, digest)

    return Response(content=pdf, media_type="application/pdf")


@router.get(
    "/options",
    responses={503: {"model": ErrorResponse, "description": "No CV options have been published yet"}},
)
async def cv_get_options(session: SessionDep) -> FormOptionsResponse:
    return await get_form_options(session)


@router.post("/generate", status_code=202)
async def cv_generate(
    body: GenerateRequest, session: SessionDep, redis: RedisDep, client: CvClientDep
) -> GenerateStartedResponse:
    task_id = await start_cv_generation(session, redis, client, body)

    return GenerateStartedResponse(task_id=task_id)


@router.get("/generate/{task_id}")
async def cv_generate_status(task_id: TaskId, redis: RedisDep, client: CvClientDep) -> GenerateStatusResponse:
    return await get_cv_generation_status(redis, client, task_id)
