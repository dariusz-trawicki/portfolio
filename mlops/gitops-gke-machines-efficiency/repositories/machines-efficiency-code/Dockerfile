FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY templates/ ./templates/
COPY static/ ./static/
COPY artifacts/models/ ./artifacts/models/
COPY application.py ./

RUN useradd -m app && chown -R app:app /app
USER app

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "2", "--threads", "4", \
     "--preload", "--access-logfile", "-", \
     "application:app"]
