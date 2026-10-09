# SERVING image (no MLflow or scikit-learn: smaller image, smaller attack surface).
# Run `make train` first so that artifacts/ contains a bundle and registry.json.
FROM python:3.12-slim

ENV KERAS_BACKEND=jax \
    PYTHONUNBUFFERED=1 \
    MLOPS_ARTIFACTS=/app/artifacts

WORKDIR /app
RUN pip install --no-cache-dir keras jax numpy pandas fastapi "uvicorn[standard]"

COPY src/ src/
COPY artifacts/registry.json artifacts/registry.json
COPY artifacts/models/ artifacts/models/

ENV PYTHONPATH=/app/src
# Do not run as root.
RUN useradd --create-home app && mkdir -p /app/artifacts && chown -R app /app/artifacts
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "mlops_demo.serve:app", "--host", "0.0.0.0", "--port", "8000"]
