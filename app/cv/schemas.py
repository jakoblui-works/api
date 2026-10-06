from typing import Literal

from pydantic import BaseModel

DIGEST_PATTERN = r"^[0-9a-f]{64}$"


class PingRequest(BaseModel):
    message: str


class PingStartedResponse(BaseModel):
    task_id: str


class PingStatusResponse(BaseModel):
    state: Literal["pending", "done", "failed"]
    result: str | None = None


# Field names match cv-service's SelectionRequest; the request is forwarded to cv.generate.v1.
class GenerateRequest(BaseModel):
    title_id: str
    concept_ids: list[str] = []
    skill_ids: list[str] = []


class GenerateStartedResponse(BaseModel):
    task_id: str


class GenerateStatusResponse(BaseModel):
    state: Literal["pending", "done", "failed"]
    digest: str | None = None


# Mirror of cv-service's published form options (cv.published_options, version 1).
# Field names are the contract; class names are ours.
class FormOption(BaseModel):
    id: str
    label: str


class SkillGroup(BaseModel):
    id: str
    label: str
    skills: list[FormOption]


class FormOptionsResponse(BaseModel):
    titles: list[FormOption]
    concepts: list[FormOption]
    skill_groups: list[SkillGroup]
