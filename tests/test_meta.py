from collections.abc import Iterable, Iterator

from fastapi.routing import APIRoute, _IncludedRouter
from starlette.routing import BaseRoute

from app.main import app
from tests.conftest import covered_names


def _api_routes(routes: Iterable[BaseRoute]) -> Iterator[APIRoute]:
    for route in routes:
        if isinstance(route, _IncludedRouter):
            yield from _api_routes(route.original_router.routes)
        elif isinstance(route, APIRoute):
            yield route


def _route_exempt(route: APIRoute) -> bool:
    exempt_reason: str | None = (route.openapi_extra or {}).get("x-test-exempt")
    return bool(exempt_reason)


def _route_covered(route: APIRoute) -> bool:
    return route.name in covered_names


def test_coverage() -> None:
    for route in _api_routes(app.routes):
        if _route_exempt(route):
            continue

        assert _route_covered(route), f"Route '{route.name}' has no test and is not exempt"
