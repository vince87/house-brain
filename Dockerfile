FROM ghcr.io/astral-sh/uv:0.12.1 AS uv

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HOME=/tmp

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./

RUN apt-get update \
    && apt-get install --no-install-recommends --yes gosu \
    && rm -rf /var/lib/apt/lists/* \
    && uv sync --frozen --no-dev --no-install-project

COPY house_brain ./house_brain
COPY docker-entrypoint.sh /usr/local/bin/house-brain-entrypoint

RUN uv sync --frozen --no-dev \
    && chmod 755 /usr/local/bin/house-brain-entrypoint \
    && mkdir -p /config \
    && chown 1000:1000 /config

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health', timeout=3)"]

ENTRYPOINT ["house-brain-entrypoint"]
CMD ["/app/.venv/bin/uvicorn", "house_brain.main:app", "--host", "0.0.0.0", "--port", "8090", "--no-access-log"]
