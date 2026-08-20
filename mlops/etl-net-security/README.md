
# Network Security – End-to-End ETL & Machine Learning Pipeline

This project implements a complete **MLOps-ready pipeline** for network intrusion detection. It covers all essential stages: **ETL → Validation → Transformation → Model Training → Evaluation → Deployment → Prediction API**.

## 1. Project Overview

The system processes raw network data, validates schema and integrity, transforms the dataset, trains ML models, evaluates them, and deploys the best model to a production API.

Main features:
- Automated data ingestion
- Schema validation and drift detection
- Feature engineering and preprocessing
- Model training with multiple algorithms
- MLflow experiment tracking
- Model serialization and deployment
- Optional AWS deployment (ECR + ECS/App Runner)

## 2. Pipeline Stages

### Data Ingestion
- Reads raw CSV files or remote sources (S3, databases).
- Produces validated train/test splits.

### Data Validation
- Checks schema consistency.
- Ensures correct column count.
- Performs numerical drift detection.
- Generates validation reports.

### Data Transformation
- Uses KNNImputer for missing values.
- Produces `preprocessor.pkl` with transformation logic.
- Converts cleaned data into training/test NumPy arrays.

### Model Training
- Trains Random Forest, Logistic Regression, Gradient Boosting, AdaBoost, Decision Tree.
- Hyperparameter tuning with custom utilities.
- Logs metrics and models to MLflow.

### Model Packaging
- Saves final model and preprocessing pipeline:
  - `final_model/model.pkl`
  - `final_model/preprocessor.pkl`

### Prediction API
- FastAPI/Flask service.
- Loads model from MLflow or local artifacts.
- Accepts uploaded CSV and returns predictions.

### Saving Artifacts to an S3 Bucket (AWS)

At the final stage of the pipeline, all relevant artifacts are uploaded to an `Amazon S3` bucket. This includes:
- the serialized preprocessing pipeline and trained model files,
- the `artifact` directory produced during the training process.


## 3. MLflow Integration

MLflow logs:
- Metrics: F1-score, precision, recall
- Models: serialized sklearn models


## 4. Technologies Used

- Python 3.10+
- Pandas, NumPy
- Scikit‑learn
- MLflow
- FastAPI / Flask
- terraform (S3 AWS)


## 5. Run

### Create S3 (AWS) - terraform

```bash
terraform init
terraform plan
terraform apply
```

### Install MongoDB 

```bash
brew tap mongodb/brew
brew install mongodb-community

brew services start mongodb-community
# test
mongosh
```

### Create enviroment

```bash
conda create -p ./venv python=3.12 -y
conda activate ./venv
pip install -r requirements.txt
```

### Load raw dataset from a local file into MongoDB

```bash
python push_data.py
# Test:
mongosh
show dbs
use networksecurity-db
show collections
# Output:
# NetworkData
db.NetworkData.find().pretty()
exit
```

### Run MLflow UI

```bash
mlflow ui
```

### Run the pipeline

```bash
python main.py
```

### Start FastAPI prediction API

```bash
uvicorn app:app --reload
```

## 6. Generated Artifacts

- `Artifacts/data_ingestion/`
- `Artifacts/data_transformation/`
- `Artifacts/data_validation/`
- `final_model/preprocessor.pkl`
- `final_model/model.pkl`
- `prediction_output/`

## 7. Saving Artifacts to an S3 Bucket (AWS)

At the final stage of the pipeline, all relevant artifacts are uploaded to an `Amazon S3` bucket.


## 8. CLEAN UP

```bash
conda deactivate
conda remove -p ./venv --all -y

cd terraform
terraform destroy
```