from typing import Literal

from pydantic import BaseModel


class PingRequest(BaseModel):
    message: str


class PingStartedResponse(BaseModel):
    task_id: str


class PingStatusResponse(BaseModel):
    state: Literal["pending", "done", "failed"]
    result: str | None = None
