from typing import Annotated

from fastapi import Depends, Request

from app.core.queue import ServiceClient

PING_V1 = "cv.ping.v1"


class CvClient(ServiceClient):
    async def ping(self, message: str) -> str:
        return str(await self._call(PING_V1, message))


async def get_cv_client(request: Request) -> CvClient:
    return request.app.state.cv_client


CvClientDep = Annotated[CvClient, Depends(get_cv_client)]
