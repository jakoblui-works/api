from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.core.database import create_database_engine, create_session_factory
from app.core.logging import configure_logging
from app.core.sentry import init_sentry
from app.health.router import router as health_router

configure_logging(settings.log_level)

init_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    engine = create_database_engine(settings.database)
    factory = create_session_factory(engine)
    app.state.database_engine = engine
    app.state.session_factory = factory
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(health_router)
