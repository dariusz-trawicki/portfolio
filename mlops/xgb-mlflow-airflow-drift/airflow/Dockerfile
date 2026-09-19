FROM apache/airflow:2.10.5-python3.11

# Airflow's constraints file keeps transitive dependencies (e.g. protobuf) compatible with Airflow itself.
ARG CONSTRAINTS=https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.11.txt
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt --constraint "${CONSTRAINTS}"

# Directories used by named volumes: a fresh volume inherits ownership from the image.
USER root
RUN mkdir -p /opt/airflow/data /opt/airflow/logs && chown -R airflow:root /opt/airflow/data /opt/airflow/logs
USER airflow
