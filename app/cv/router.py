from fastapi import APIRouter

from app.cv.client import CvClientDep
from app.cv.schemas import PingRequest, PingStartedResponse, PingStatusResponse

router = APIRouter(prefix="/cv", tags=["cv"])


@router.post("/ping", status_code=202)
async def cv_ping(client: CvClientDep, body: PingRequest) -> PingStartedResponse:
    task_id = await client.start_ping(message=body.message)

    return PingStartedResponse(task_id=task_id)


@router.get("/ping/{task_id}")
async def cv_ping_status(client: CvClientDep, task_id: str) -> PingStatusResponse:
    status = await client.ping_status(task_id)
    result = str(status.result) if status.result is not None else None

    return PingStatusResponse(state=status.state, result=result)
