import asyncio

from app.core.config import settings
from app.core.queue import create_service_broker
from app.cv.client import CvClient


async def main() -> None:
    cv_broker = create_service_broker(settings.redis, "cv")
    await cv_broker.startup()

    try:
        print(await CvClient(cv_broker).ping("hello"))
    finally:
        await cv_broker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
