from contextlib import AbstractAsyncContextManager
from typing import Annotated

import aioboto3
from botocore.config import Config
from fastapi import Depends, Request
from types_aiobotocore_s3 import S3Client

from app.core.config import S3Settings


def create_s3_client(settings: S3Settings, session: aioboto3.Session) -> AbstractAsyncContextManager[S3Client]:
    return session.client(
        "s3",
        endpoint_url=settings.endpoint_url,
        region_name=settings.region,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key.get_secret_value(),
        config=Config(
            request_checksum_calculation="when_required",
            s3={"addressing_style": "path"},
        ),
    )


async def get_s3(request: Request) -> S3Client:
    return request.app.state.s3


S3Dep = Annotated[S3Client, Depends(get_s3)]
