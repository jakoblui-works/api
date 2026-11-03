import sentry_sdk

from app.core.config import settings


def init_sentry() -> None:
    sentry_sdk.init(
        dsn=settings.sentry.dsn,
        environment=settings.sentry.environment,
        traces_sample_rate=1.0,
        include_local_variables=False,  # Tracebacks would carry request data (bodies, ids) into Sentry.
    )
