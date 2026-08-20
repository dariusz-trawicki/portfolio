FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

USER airflow

RUN pip install --no-cache-dir \
    mlflow==2.14.1 \
    scikit-learn==1.5.0 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    scipy==1.13.0 \
    joblib==1.4.2 \
    psycopg2-binary==2.9.9 \
    "SQLAlchemy>=1.4.36,<2.0" \
    apache-airflow-providers-postgres==5.11.1

# Shared modules (feature_extraction, data_generator, bearing_physics)
COPY --chown=airflow:root shared/ /opt/airflow/shared/
ENV PYTHONPATH="/opt/airflow/shared:${PYTHONPATH}"
