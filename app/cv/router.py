from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response

from app.core.config import settings
from app.core.s3 import S3Dep
from app.cv.client import CvClientDep
from app.cv.schemas import PingRequest, PingStartedResponse, PingStatusResponse

router = APIRouter(prefix="/cv", tags=["cv"])

Digest = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]


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
    try:
        obj = await s3.get_object(Bucket=settings.s3.bucket, Key=f"{digest}.pdf")
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="No such file found") from None

    data = await obj["Body"].read()
    return Response(content=data, media_type="application/pdf")
