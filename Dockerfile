FROM python:3.13
COPY --from=ghcr.io/astral-sh/uv:0.8.23 /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
  ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-cache
RUN uv run playwright install --with-deps chromium

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONPATH=/app

EXPOSE 8000

CMD ["uv", "run", "-m", "src.main"]