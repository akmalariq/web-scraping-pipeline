FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN uv sync --no-dev
RUN uv run playwright install --with-deps chromium

ENV SCRAPER_DATA_DIR=/app/data

ENTRYPOINT ["uv", "run", "scrape"]
CMD ["run"]
