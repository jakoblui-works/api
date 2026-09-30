from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager

import aioboto3
from fastapi import FastAPI

from app.core.config import settings
from app.core.database import create_database_engine, create_session_factory
from app.core.logging import configure_logging
from app.core.redis import create_redis_client
from app.core.s3 import create_s3_client
from app.core.sentry import init_sentry
from app.health.router import router as health_router

configure_logging(settings.log_level)

init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    async with AsyncExitStack() as stack:
        engine = create_database_engine(settings.database)
        stack.push_async_callback(engine.dispose)

        app.state.database_engine = engine
        app.state.session_factory = create_session_factory(engine)

        app.state.redis = await stack.enter_async_context(create_redis_client(settings.redis))

        s3_session = aioboto3.Session()
        app.state.s3 = await stack.enter_async_context(
            create_s3_client(
                settings.s3,
                s3_session,
            )
        )

        yield


app = FastAPI(lifespan=lifespan)

app.include_router(health_router)
