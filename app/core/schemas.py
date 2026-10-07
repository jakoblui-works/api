from pydantic import BaseModel


class StatusResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str


class EmptyResponse(BaseModel):
    pass
