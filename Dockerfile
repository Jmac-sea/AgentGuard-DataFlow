FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY policies ./policies

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "agentguard", "serve-api", "--host", "0.0.0.0", "--port", "8000", "--runtime-dir", "/data/runtime", "--policy", "/app/policies/default.yaml"]

