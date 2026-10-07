# api

Shared FastAPI gateway for all jakoblui-works projects. Served behind Traefik at `/api` (uvicorn `--root-path /api`; Traefik strips the prefix). Domain work is sent to workers over Redis (Taskiq); the api itself stays thin.

## Commands
```sh
docker compose -f compose.dev.yml up -d --wait   # Postgres 18, Redis 8.10, Garage
./scripts/garage-dev-init.sh                     # one-time Garage layout/key/bucket setup
uv sync
uv run ruff check && uv run ruff format --check
uv run pytest
uv run alembic upgrade head
uv run uvicorn app.main:app --reload             # http://localhost:8000
```
Local DB shell (no `psql` on the host): `docker exec api-postgres-1 psql -U works_user -d jakoblui_works`

## Layout
`app/<domain>/` = `router.py` / `service.py` / `repository.py` / `schemas.py` (+ `client.py` for worker calls). Routes only wire dependencies; logic goes in the service; SQL/Redis/S3 goes in the repository (no HTTP, no pydantic).
- `app/core/`: settings, database, Redis, S3, Sentry, `ServiceClient` (Taskiq sender, supports a caller-chosen `task_id`).
- `app/health/`: liveness/readiness (readiness heads `settings.cv.bucket`).
- `app/cv/`: options, generate (dedup via Redis claim/release), status, PDF.

## Contracts
- **Consumes** `cv.published_options` (owned by cv-service): plain SQL plus mirror models in `app/cv/schemas.py`. Field names are the contract; class names are ours. Never migrate the `cv` schema from here.
- **Sends** `cv.generate.v1` with a `GenerateRequest` dict (field names = cv-service `SelectionRequest`). Reads back `"<digest>.pdf"`.
- **Serves** an OpenAPI spec consumed by cv-web's Orval. operationId = router function name; renaming a route function is a breaking change for cv-web.

## Gotchas
- Tests need the compose.dev.yml services up (same as CI). `tests/cv/conftest.py` creates `cv.published_options` when it's missing, since the CI DB has no cv-service migrations.
- `CV__BUCKET` is required. `S3__BUCKET` is ignored by the api.
- Redis must be ≥ 8.4 for `DELEX … IFEQ`. redis-py warns that `delex` is experimental; that warning is expected.
- Rate limiting is done by Traefik (infra), not here.
- Every route test is tagged `@pytest.mark.covers_endpoint(name)`; `tests/test_meta.py` fails if a route is neither covered nor marked `x-test-exempt`.
