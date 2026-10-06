import logging
import re
from typing import Annotated

from fastapi import Depends, Request

from app.core.queue import ServiceClient, TaskStatus
from app.cv.schemas import DIGEST_PATTERN, GenerateStatusResponse

logger = logging.getLogger(__name__)

PING_V1 = "cv.ping.v1"
GENERATE_V1 = "cv.generate.v1"


class CvClient(ServiceClient):
    async def ping(self, message: str) -> str:
        return str(await self._call(PING_V1, message))

    async def start_ping(self, message: str) -> str:
        return await self._send(PING_V1, message)

    async def ping_status(self, task_id: str) -> TaskStatus:
        return await self._status(task_id)

    async def start_generate(self, request: dict[str, object], task_id: str) -> str:
        return await self._send(GENERATE_V1, request, task_id=task_id)

    async def generate_status(self, task_id: str) -> GenerateStatusResponse:
        status = await self._status(task_id)

        if status.state != "done":
            return GenerateStatusResponse(state=status.state)

        # cv.generate.v1 returns the PDF's S3 key: "<digest>.pdf"
        result = status.result
        if isinstance(result, str) and result.endswith(".pdf"):
            digest = result.removesuffix(".pdf")
            if re.fullmatch(DIGEST_PATTERN, digest):
                return GenerateStatusResponse(state="done", digest=digest)

        logger.warning("Task %s returned an unexpected result shape", task_id)
        return GenerateStatusResponse(state="failed")


async def get_cv_client(request: Request) -> CvClient:
    return request.app.state.cv_client


CvClientDep = Annotated[CvClient, Depends(get_cv_client)]
