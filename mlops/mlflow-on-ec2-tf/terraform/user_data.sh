#!/bin/bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

# Base packages
apt-get update -y
apt-get install -y python3-venv awscli

# Create directory for the backend (sqlite) and MLflow metadata
install -d -o ubuntu -g ubuntu /var/mlflow

# Virtual environment for MLflow
python3 -m venv /opt/mlflow/venv
/opt/mlflow/venv/bin/pip install --upgrade pip
/opt/mlflow/venv/bin/pip install "mlflow>=3.4,<3.5" boto3

# systemd unit for MLflow (runs as 'ubuntu' user)
cat >/etc/systemd/system/mlflow.service <<SERVICE
[Unit]
Description=MLflow Tracking Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/var/mlflow
Environment=AWS_DEFAULT_REGION=${region}
ExecStart=/opt/mlflow/venv/bin/python -m mlflow server \
  --host 0.0.0.0 \
  --port 5000 \
  --backend-store-uri sqlite:////var/mlflow/mlflow.db \
  --default-artifact-root s3://${bucket_name}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

# Start the service
systemctl daemon-reload
systemctl enable --now mlflow
