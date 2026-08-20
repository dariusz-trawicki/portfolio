FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    fastapi==0.111.0 \
    uvicorn==0.30.1 \
    mlflow==2.14.1 \
    scikit-learn==1.5.0 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    psycopg2-binary==2.9.9 \
    kafka-python==2.0.2 \
    requests==2.32.3

COPY serving/app.py /app/app.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
