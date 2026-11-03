# syntax=docker/dockerfile:1

FROM node:24-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS api
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN uv sync --frozen --no-dev --extra backup --no-install-project
COPY apps/api/src ./src
RUN uv sync --frozen --no-dev --extra backup --no-editable

FROM python:3.12-slim
RUN useradd --create-home --uid 1000 app \
    && mkdir /data && chown app:app /data
WORKDIR /app
COPY --from=api /app/.venv /app/.venv
COPY --from=web /web/dist /app/web
ENV PATH="/app/.venv/bin:$PATH" \
    WEB_DIST_DIR=/app/web \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "finchart_api.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
