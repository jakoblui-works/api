from taskiq import AsyncBroker, TaskiqResultTimeoutError
from taskiq.kicker import AsyncKicker
from taskiq_redis import RedisAsyncResultBackend, RedisStreamBroker

from app.core.config import RedisSettings


class ServiceTaskError(RuntimeError):
    """A task ran in a worker and failed there."""


class ServiceClient:
    def __init__(self, broker: AsyncBroker) -> None:
        self._broker = broker

    def _kicker(self, task_name: str) -> AsyncKicker:
        return AsyncKicker(task_name=task_name, broker=self._broker, labels={})

    async def _send(self, task_name: str, *args: object) -> str:
        """Enqueue a task and return its ID without waiting."""
        task = await self._kicker(task_name).kiq(*args)
        return task.task_id

    async def _call(self, task_name: str, *args: object, timeout: float = 10) -> object:
        """Enqueue a task and wait for its result."""
        task = await self._kicker(task_name).kiq(*args)

        try:
            result = await task.wait_result(timeout=timeout)
        except TaskiqResultTimeoutError as exc:
            raise ServiceTaskError(f"Task {task_name} timed out after {timeout}s") from exc

        if result.is_err:
            raise ServiceTaskError(f"Task {task_name} failed: {result.error}")

        return result.return_value


def create_service_broker(settings: RedisSettings, service: str) -> RedisStreamBroker:
    return RedisStreamBroker(
        url=settings.url,
        queue_name=service,
    ).with_result_backend(
        RedisAsyncResultBackend(
            settings.url,
            result_ex_time=3600,
            prefix_str=service,
        )
    )
