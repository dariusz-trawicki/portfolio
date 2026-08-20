# MLOps Demo – Complete Pipeline

A complete MLOps project covering the full model lifecycle:  
`training → serving → monitoring → automatic retraining`

![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=flat&logo=kubernetes&logoColor=white)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![MLflow](https://img.shields.io/badge/MLflow-Tracking-0194E2?style=flat&logo=mlflow)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg?style=flat&logo=fastapi)

## What’s included?

- **Training Pipeline** – Automated model training with MLflow tracking  
- **Model Registry** – Model versioning and storage  
- **Model Serving** – FastAPI REST API with auto-reload  
- **Monitoring** – Prometheus metrics + Grafana dashboards  
- **Automatic Retraining** – CronJob for periodic retraining  
- **Data Drift Detection** – KS test + auto-retraining on drift 


## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Minikube / K8s Cluster                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐        ┌──────────────┐        ┌───────────────┐   │
│  │ Training Job │ ───▶   │   MLflow     │ ───▶   │ Model Storage │   │
│  │  (Batch)     │        │ (Tracking &  │        │   (PVC)       │   │
│  └──────┬───────┘        │  Registry)   │        └───────┬───────┘   │
│         │                └──────┬───────┘                │           │
│         │                       │                        │           │
│         ▼                       ▼                        ▼           │
│    Training Metrics       Experiments & Runs        Model Artifacts  │
│                                                                      │
│                                  ┌──────────────────────────────┐    │
│                                  │   Model Serving (FastAPI)    │    │
│                                  │  - REST API                  │    │
│                                  │  - Swagger /docs             │    │
│                                  │  - Auto-reload model         │    │
│                                  └─────────────┬────────────────┘    │
│                                                │                     │
│                         ┌──────────────────────▼────────────────┐    │
│                         │        Prometheus Metrics             │    │
│                         │  - latency                            │    │
│                         │  - accuracy                           │    │
│                         │  - drift score                        │    │
│                         └─────────────┬─────────────────────────┘    │
│                                       │                              │
│                         ┌─────────────▼──────────────────────────┐   │
│                         │           Grafana Dashboards           │   │
│                         │  - Model Performance                   │   │
│                         │  - Data Drift Monitoring               │   │
│                         └────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────┐                                                    │
│  │   CronJob    │ ───▶ Automatic Retraining (daily / on drift)       │
│  │ (Scheduler)  │                                                    │
│  └──────────────┘                                                    │
│                                                                      │
│  ┌────────────────┐        ┌──────────────────────────────────────┐  │
│  │ Drift Detector │ ───▶   │  Retraining Trigger (Job)            │  │
│  │ (KS Test)      │        │  - threshold exceeded                │  │
│  └────────────────┘        │  - new model version                 │  │
│                            └──────────────────────────────────────┘  │
│                                                                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
mlops-demo/
├── model/                     # Model training
│   ├── train.py               # Training script z MLflow
│   ├── requirements.txt       # Python dependencies
│   └── Dockerfile             # Training image
│
├── serving/                   # Model serving
│   ├── app.py                 # FastAPI application
│   ├── requirements.txt       # Dependencies
│   └── Dockerfile             # Serving image
│
├── k8s/                                  # Kubernetes manifests
│   ├── 00-namespace.yaml                 # Namespace
│   ├── 01-storage.yaml                   # PV/PVC dla modeli
│   ├── 02-mlflow.yaml                    # MLflow deployment
│   ├── 03-training-job.yaml              # Training Job + CronJob
│   ├── 04-model-serving.yaml             # Serving deployment
│   ├── 05-prometheus.yaml                # Prometheus + RBAC
│   ├── 06-grafana.yaml                   # Grafana
│   ├── 07-drift-detector.yaml            # Drift Detector
│   └── 08-grafana-drift-dashboard.yaml   # Grafana dashboards
│
├── monitoring/             
│   ├── prometheus.yml          # Prometheus config
│   └── grafana-datasources.yml # Grafana datasource
│
├── scripts/                   
│   ├── setup-minikube.sh           # Setup Minikube
│   ├── build-images.sh             # Build Docker images
│   ├── deploy-infra.sh             # Deploy infrastructure
│   ├── deploy-drift-detection.sh   # Deploy drift detection
│   ├── train-model.sh              # Run training job
│   ├── deploy-model.sh             # Deploy serving
│   ├── test-api.sh                 # Test API
│   ├── open-dashboards.sh          # Open UIs
│   ├── run-port-forwards.sh        # Port Forwards
│   ├── simulate-drift.sh           # Drift Simulator
│   └── cleanup.sh                  # Cleanup resources
│
└── README.md               
```

## Requirements

### Software
- Docker >= 20.10
- Minikube >= 1.32
- kubectl >= 1.28
- jq, curl

### Resources
- CPU: 4 cores minimum
- RAM: 8 GB minimum
- Disk: 20 GB free

## Run

```bash
#### Run in terminal I:
./scripts/setup-minikube.sh
## Docker:
# - Build training image
# - Build serving image
./scripts/build-images.sh
## Deploy infrastructure (MLflow, Prometheus, Grafana)
./scripts/deploy-infra.sh

# NOTE: Wait for the end of deployment - and then run:

#### Run in terminal II:
# Port forward
./scripts/run-port-forwards.sh

#### Run in terminal I:
# Open dashboards:
./scripts/open-dashboards.sh
# (Grafana [user:admin, pass: admin])
# Train model
./scripts/train-model.sh
# Deploy model serving
./scripts/deploy-model.sh

# Run in terminal III:
kubectl port-forward -n mlops svc/model-serving 8000:8000

#### Run in terminal I:
open "http://localhost:8000/docs"  # optional
## Test API
./scripts/test-api.sh
## Deploy drift detection system
./scripts/deploy-drift-detection.sh
# NOTE: # This script restarts Grafana, among other things, to load a new dashboard.
# This command disables Grafana's port-forward, requiring a restart.
# In Terminal II:
# [ctr+C] and run: 
./scripts/run-port-forwards-dt.sh

# terminal IV:
kubectl -n mlops port-forward svc/drift-detector 8002:8002

# Optional:
open "http://localhost:8002/docs"
open "http://localhost:8002/drift_status"


## Terminal V:
# Simulate data drift
./scripts/simulate-drift.sh

curl -s http://localhost:8002/drift_status
open "http://localhost:8002/drift_status"

open "http://localhost:3000"  # Check dashboards...
```

## Available Services

| Service | Local Port | URL | Description |
|--------|------|-----|-------------|
| MLflow | 5000 | http://localhost:5000 | Tracking UI |
| Prometheus | 9090 | http://localhost:9090 | Metrics |
| Grafana | 3000 | http://localhost:3000 | Dashboards (admin/admin) |
| Model API | 8000 | http://localhost:8000 | REST API |
| Swagger UI | 8000 | http://localhost:8000/docs | API Docs |
| Drift Status   | 8002 | http://localhost:8002/drift_status | Drift Status Endpoint     |

## Automatic Retraining

The model is retrained daily at 02:00 using a Kubernetes CronJob, or
when data drift is detected.

```bash
# Test after data drift detection:
curl -s http://localhost:8002/metrics | grep drift_retraining_triggered
open "http://localhost:8002/metrics"
```


## Clean Up
```bash
./scripts/cleanup.sh
```

## Security Notes

For production use:
- Change default passwords
- Use Kubernetes Secrets
- Enable RBAC & Network Policies
- Use Ingress with TLS
- Scan Docker images for vulnerabilities

## License

MIT License – free to use.
