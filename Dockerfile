FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock alembic.ini ./

RUN uv sync --locked --no-dev

COPY ./app ./app
COPY migrations ./migrations

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/api"]