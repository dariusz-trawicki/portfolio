# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Dependencies only (cached layer, rebuilt only when the lockfile changes)
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra piper --no-install-project

# 2. Piper voice model (cross-platform TTS replacing macOS `say`)
ARG PIPER_VOICE=en_US-lessac-medium
ARG PIPER_VOICE_URL=https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium
RUN mkdir -p models \
    && curl -fsSL -o "models/${PIPER_VOICE}.onnx" "${PIPER_VOICE_URL}/${PIPER_VOICE}.onnx" \
    && curl -fsSL -o "models/${PIPER_VOICE}.onnx.json" "${PIPER_VOICE_URL}/${PIPER_VOICE}.onnx.json"

# 3. Application code
COPY src ./src
COPY config.yaml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra piper

RUN useradd --create-home --uid 1000 teacher \
    && mkdir -p /app/data /home/teacher/.cache/huggingface \
    && chown -R teacher:teacher /app/data /home/teacher/.cache
USER teacher

ENV PATH="/app/.venv/bin:${PATH}" \
    HF_HOME=/home/teacher/.cache/huggingface \
    TEACHER_SERVER__HOST=0.0.0.0 \
    TEACHER_TTS__BACKEND=piper \
    TEACHER_TTS__PIPER_MODEL=/app/models/en_US-lessac-medium.onnx

EXPOSE 7860 9100

HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9100/metrics', timeout=3)"

CMD ["english-teacher", "--config", "config.yaml"]
