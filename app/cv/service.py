import hashlib
import json
import logging
import uuid

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from types_aiobotocore_s3 import S3Client

from app.cv.client import CvClient
from app.cv.repository import claim_generate, get_pdf, get_published_options, release_generate
from app.cv.schemas import FormOptionsResponse, GenerateRequest, GenerateStatusResponse

OPTIONS_VERSION = 1  # This indicates the cv-service options shape version this API understands
GENERATE_INFLIGHT_TTL = 120

logger = logging.getLogger(__name__)


async def get_form_options(session: AsyncSession) -> FormOptionsResponse:
    options = await get_published_options(session, OPTIONS_VERSION)
    if options is None:
        logger.warning("No published cv options for version %s", OPTIONS_VERSION)
        raise HTTPException(status_code=503, detail="CV options are not available yet")

    return FormOptionsResponse.model_validate(options)


async def get_cv_pdf(s3: S3Client, digest: str) -> bytes:
    pdf = await get_pdf(s3, digest)
    if pdf is None:
        raise HTTPException(status_code=404, detail="No such file found")

    return pdf


def validate_generate_request(request: GenerateRequest, options: FormOptionsResponse) -> None:
    valid_title_ids = {title.id for title in options.titles}
    valid_concept_ids = {concept.id for concept in options.concepts}
    valid_skill_ids = {skill.id for skill_group in options.skill_groups for skill in skill_group.skills}

    errors: list[dict[str, object]] = []

    if request.title_id not in valid_title_ids:
        errors.append(
            {
                "loc": ("body", "title_id"),
                "msg": "Unknown title id",
                "type": "value_error",
                "input": request.title_id,
            }
        )

    for index, concept_id in enumerate(request.concept_ids):
        if concept_id not in valid_concept_ids:
            errors.append(
                {
                    "loc": ("body", "concept_ids", index),
                    "msg": "Unknown concept id",
                    "type": "value_error",
                    "input": concept_id,
                }
            )

    for index, skill_id in enumerate(request.skill_ids):
        if skill_id not in valid_skill_ids:
            errors.append(
                {
                    "loc": ("body", "skill_ids", index),
                    "msg": "Unknown skill id",
                    "type": "value_error",
                    "input": skill_id,
                }
            )

    if errors:
        raise RequestValidationError(errors)


def canonicalise_generate_request(request: GenerateRequest) -> GenerateRequest:
    return GenerateRequest(
        title_id=request.title_id,
        concept_ids=sorted(set(request.concept_ids)),
        skill_ids=sorted(set(request.skill_ids)),
    )


def generate_request_key(request: GenerateRequest) -> str:
    payload = json.dumps(request.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


async def start_cv_generation(session: AsyncSession, redis: Redis, client: CvClient, request: GenerateRequest) -> str:
    options = await get_form_options(session)

    validate_generate_request(request, options)
    canonical_request = canonicalise_generate_request(request)

    request_key = generate_request_key(canonical_request)
    candidate = uuid.uuid4().hex

    owner = await claim_generate(redis, request_key, candidate, GENERATE_INFLIGHT_TTL)

    if owner == candidate:
        try:
            await client.start_generate(request=canonical_request.model_dump(), task_id=candidate)
        except Exception:
            await release_generate(redis, candidate)
            raise

    return owner


async def get_cv_generation_status(redis: Redis, client: CvClient, task_id: str) -> GenerateStatusResponse:
    status = await client.generate_status(task_id)

    if status.state == "failed":
        await release_generate(redis, task_id)

    return status
