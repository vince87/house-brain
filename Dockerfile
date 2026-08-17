FROM ghcr.io/astral-sh/uv:0.12.1 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev --no-install-project

COPY house_brain ./house_brain

RUN uv sync --frozen --no-dev \
    && useradd --create-home --uid 10001 housebrain \
    && mkdir -p /config \
    && chown housebrain:housebrain /config

USER housebrain

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3)"]

CMD ["/app/.venv/bin/uvicorn", "house_brain.main:app", "--host", "0.0.0.0", "--port", "8090", "--no-access-log"]
