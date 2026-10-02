from typing import Annotated

from fastapi import Depends, Request

from app.core.queue import ServiceClient, TaskStatus

PING_V1 = "cv.ping.v1"


class CvClient(ServiceClient):
    async def ping(self, message: str) -> str:
        return str(await self._call(PING_V1, message))

    async def start_ping(self, message: str) -> str:
        return await self._send(PING_V1, message)

    async def ping_status(self, task_id: str) -> TaskStatus:
        return await self._status(task_id)


async def get_cv_client(request: Request) -> CvClient:
    return request.app.state.cv_client


CvClientDep = Annotated[CvClient, Depends(get_cv_client)]
