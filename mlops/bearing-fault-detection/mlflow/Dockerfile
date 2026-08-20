FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    mlflow==2.14.1 \
    psycopg2-binary==2.9.9 \
    boto3==1.34.144

EXPOSE 5000

# --backend-store-uri: experiment/run/registry metadata in Postgres
# --artifacts-destination: artifacts (models, plots) on a local volume
CMD mlflow server \
    --backend-store-uri postgresql://postgres:postgres@postgres:5432/mlflow \
    --artifacts-destination /mlartifacts \
    --serve-artifacts \
    --host 0.0.0.0 \
    --port 5000
