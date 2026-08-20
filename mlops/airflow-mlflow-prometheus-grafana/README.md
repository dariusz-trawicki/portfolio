# Titanic Survival Prediction — MLOps Project

A complete MLOps pipeline for predicting Titanic passenger survival, featuring ETL with Apache Airflow, a Redis Feature Store, ML monitoring with Prometheus, and experiment tracking with MLflow.

---

## Architecture

```
GCS (raw data)
    ↓ Airflow DAG
PostgreSQL (titanic table)
    ↓ DataIngestion
train.csv / test.csv
    ↓ DataProcessing
Redis Feature Store
    ↓ ModelTraining
Random Forest Model (.pkl) + MLflow
    ↓ Flask API
Predictions + Drift Detection
    ↓ Prometheus + Grafana
ML Monitoring Dashboard
```

---

## Project Structure

```
project/
├── dags/
│   └── extract_data_from_gcp.py      # Airflow DAG: GCS → PostgreSQL
├── src/
│   ├── data_ingestion.py             # PostgreSQL → train.csv / test.csv
│   ├── data_processing.py            # Preprocessing + SMOTE + Redis
│   ├── model_training_mlflow.py      # Random Forest + MLflow tracking
│   ├── feature_store.py              # Redis Feature Store wrapper
│   ├── logger.py                     # Logging utility
│   └── custom_exception.py           # Custom exception handler
├── pipeline/
│   └── training_pipeline.py          # Orchestrator — runs all 3 steps
├── config/
│   ├── database_config.py            # PostgreSQL connection params
│   └── paths_config.py               # File paths (RAW_DIR, TRAIN_PATH...)
├── artifacts/
│   ├── raw/                          # train.csv, test.csv
│   └── models/                       # random_forest_model.pkl
├── templates/
│   └── index.html                    # Flask UI
├── terraform/
│   ├── main.tf                       # GCS Bucket + Service Account
│   ├── variables.tf
│   ├── outputs.tf
│   └── terraform.tfvars.example
├── application.py                    # Flask API + Drift Detection + Prometheus
├── prometheus.yml                    # Prometheus scrape config
├── requirements.txt
├── packages.txt
├── docker-compose.yml
└── Dockerfile                        # Astronomer Astro runtime
```

---

## Tech Stack

| Component | Technology |
|---|---|
| ETL Pipeline | Apache Airflow (Astronomer Astro) |
| Data Storage | PostgreSQL |
| Raw Data | Google Cloud Storage (GCS) |
| Feature Store | Redis |
| ML Model | Random Forest (scikit-learn) |
| Hyperparameter Tuning | RandomizedSearchCV |
| Class Imbalance | SMOTE (imbalanced-learn) |
| Experiment Tracking | MLflow |
| API | Flask |
| Drift Detection | Z-score (scipy) |
| Monitoring | Prometheus + Grafana |
| Infrastructure | Terraform (GCP) |

---

## Prerequisites

- Python 3.12
- Docker Desktop
- Google Cloud account with billing enabled
- Terraform
- Astronomer Astro CLI

---

## Setup

### 1. Infrastructure — GCS Bucket + Service Account

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars — set your project_id

terraform init
terraform plan
terraform apply

# Upload raw data to GCS
gsutil cp ../titanic-dataset/Titanic-Dataset.csv gs://$(terraform output -raw bucket_name)/raw/
```

### 2. Airflow — ETL Pipeline (GCS → PostgreSQL)

```bash
# Start Astronomer Astro
astro dev start

# Open Airflow UI
# http://localhost:8080  (admin/admin)

# Add connection: Admin → Connections
# Conn Id:   postgres_default
# Conn Type: Postgres
# Host:      postgres
# Schema:    postgres
# Login:     postgres
# Password:  postgres
# Port:      5432

# Add GCP connection:
# Conn Id:   google_cloud_default
# Conn Type: Google Cloud
# Keyfile:   /usr/local/airflow/include/gcp-key.json

# Place your GCP key:
cp keys/gcp-key.json ../include/gcp-key.json

# Trigger DAG: extract_titanic_data
```

### 3. Python Environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Redis

```bash
docker pull redis
docker run -d --name redis-container -p 6379:6379 redis
```

### 5. Run Training Pipeline

```bash
# Terminal 1 — MLflow UI
mlflow ui --port 5000

# Terminal 2 — Training pipeline
python -m pipeline.training_pipeline
```

Pipeline steps:
1. `DataIngestion` — PostgreSQL → train.csv / test.csv
2. `DataProcessing` — preprocessing + SMOTE → Redis Feature Store
3. `ModelTraining` — Random Forest + hyperparameter tuning → MLflow

View results: `http://localhost:5000`

### 6. Run Flask Application

```bash
python application.py
```

| Service | URL |
|---|---|
| Flask App | http://localhost:5001 |
| Prometheus metrics | http://localhost:8000 |
| MLflow UI | http://localhost:5000 |

### 7. Monitoring — Prometheus + Grafana

```bash
# Start Prometheus + Grafana
docker-compose up -d
```

Configure Grafana:
1. Open `http://localhost:3000` (admin/admin)
2. Add datasource: Prometheus → `http://prometheus:9090`
3. Create dashboard with metrics:
   - `prediction_count_total` — total predictions
   - `drift_count_total` — drift events
   - `rate(prediction_count_total[5m])` — predictions per second
   - etc.

---

## Feature Engineering

| Feature | Type | Description |
|---|---|---|
| Pclass | original | Ticket class (1/2/3) |
| Sex | encoded | Gender (0=female, 1=male) |
| Age | original | Passenger age |
| Fare | original | Ticket price |
| Embarked | encoded | Port (S=0, C=1, Q=2) |
| FamilySize | engineered | SibSp + Parch + 1 |
| IsAlone | engineered | FamilySize == 1 |
| HasCabin | engineered | Cabin is not null |
| Title | engineered | Extracted from Name (Mr=0, Miss=1, Mrs=2, Master=3, Rare=4) |
| Pclass_Fare | interaction | Pclass × Fare |
| Age_Fare | interaction | Age × Fare |


---

## Key Files

| File | Purpose |
|---|---|
| `pipeline/training_pipeline.py` | Run full ML pipeline |
| `application.py` | Flask API + monitoring |
| `src/feature_store.py` | Redis wrapper |
| `terraform/main.tf` | GCS + SA infrastructure |
| `dags/extract_data_from_gcp.py` | Airflow ETL DAG |
