# Iris Flower Classification – MLOps on GCP (GKE + GitHub Actions)

This project is a **complete end-to-end MLOps example** showing how to train a machine learning model locally and deploy an inference application to **Google Kubernetes Engine (GKE)** using **Terraform** and **GitHub Actions CI/CD with Workload Identity Federation (OIDC)**.

The example predicts the **species of an Iris flower** based on four numerical features.

---

## Problem Definition

**Goal:**  
Build a machine learning model that predicts the species of an Iris flower based on its measurements.

**Input features:**
- `SepalLengthCm`
- `SepalWidthCm`
- `PetalLengthCm`
- `PetalWidthCm`

**Target:**
- `Species`
  - Iris-setosa
  - Iris-versicolor
  - Iris-virginica

**ML Task:**  
Multiclass classification (3 classes)

**Train/Test Split:**  
- Training: 80%
- Test: 20%

---

## Dataset

Source:  
UCI Machine Learning Repository  
https://archive.ics.uci.edu/ml/datasets/iris

Local file:
```
artifacts/raw/data.csv
```

Dataset contains 150 records with the following columns:
- `Id` (technical identifier)
- `SepalLengthCm`
- `SepalWidthCm`
- `PetalLengthCm`
- `PetalWidthCm`
- `Species`

---

## Model & Training

- Library: **scikit-learn**
- Training is executed **locally**, not in Kubernetes.
- The training pipeline:
  - loads and cleans data
  - handles outliers
  - splits data
  - trains the model
  - evaluates metrics
  - saves artifacts

### Run training locally

```bash
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Run the training pipeline:

```bash
python -m pipeline.training_pipeline
```

Outputs:
- Trained model
- `confusion_matrix.png`

Saved in:
```
artifacts/models/
```
---

## Infrastructure (GCP)

Provisioned with **Terraform**:

- Google Cloud Project
- Artifact Registry (Docker)
- GKE cluster
- IAM Service Accounts
- Workload Identity Federation for GitHub Actions

Terraform commands:

```bash
cd terraform
terraform init
terraform fmt
terraform validate
terraform plan
terraform apply
```

Example outputs:
```
artifact_registry_url = "europe-west1-docker.pkg.dev/ml-gke-iris-d509/ml-ops-iris"
github_actions_sa_email = "github-actions-sa@ml-gke-iris-d509.iam.gserviceaccount.com"
github_wif_provider = "projects/256931582682/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider"
project_id = "ml-gke-iris-d509"
```

---

## Authentication (GitHub Actions → GCP)

This project uses **Workload Identity Federation (OIDC)**.  
No service account keys are stored in GitHub.

### Required GitHub Secrets

1. **`GCP_WORKLOAD_IDENTITY_PROVIDER`**  
   Value from Terraform output (exqmple):
   ```
   projects/256931582682/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider
   ```

2. **`GCP_SERVICE_ACCOUNT`**  
   Example:
   ```
   github-actions-sa@ml-gke-iris-d509.iam.gserviceaccount.com
   ```

---

## CI/CD Pipeline (GitHub Actions)

High-level flow:

1. Build Docker image
2. Push image to Artifact Registry
3. Deploy image to GKE

Key characteristics:
- Uses OIDC (no static secrets)
- Pushes images with immutable tags (`GITHUB_SHA`)
- Deploys via `kubectl set image`

---

## Kubernetes Deployment

- Deployment runs **2 replicas**
- Application listens on port **5000**
- Service type: **LoadBalancer**
- External access via public IP

Check cluster access:

```bash
gcloud container clusters get-credentials ml-ops-iris   --zone europe-west1-b   --project ml-gke-iris-d509
```

Check resources:

```bash
kubectl get pods
kubectl get svc
```

Example service output:

```
mlops-service   LoadBalancer   10.52.4.147   34.76.180.55   80:32200/TCP
```

---

## Accessing the Application

Once deployed, open in browser or test via curl:

```bash
curl http://<EXTERNAL-IP>
```

Example:
```bash
curl http://34.76.180.55
```

Response:
```
HTTP/1.1 200 OK
```

---

## Cleaning

```bash
terraform destroy
```

---

## Key Takeaways

- Training and inference are **intentionally separated**
- Kubernetes is used only for **serving**
- GitHub Actions uses **OIDC (Workload Identity)** instead of JSON keys
- Artifact Registry is used for Docker images
- Infrastructure is fully reproducible via Terraform

---

## Status

✔ Model trained locally  
✔ CI/CD working  
✔ Image pushed to Artifact Registry  
✔ Application running on GKE  
✔ Public endpoint accessible  

---

## Notes

This repository is meant as a **learning-focused, production-inspired example** of modern MLOps on GCP, combining:
- ML training
- Docker
- Kubernetes
- Terraform
- Secure CI/CD

