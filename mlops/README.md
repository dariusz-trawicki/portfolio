# MLOps

Taking models from notebook to production — experiment tracking, automated
delivery, serving, and monitoring for drift and failure.

## Projects

### End-to-end systems

| Project | Description | Stack |
|---|---|---|
| [bearing-fault-detection](bearing-fault-detection/) | Predictive maintenance from streaming sensor data: feature extraction, training, registry, serving | Kafka, MLflow, Airflow, Postgres, Docker |
| [etl-net-security](etl-net-security/) | Network threat detection pipeline — ingestion, training, prediction API | Python, FastAPI, MongoDB, Terraform |
| [airflow-mlflow-prometheus-grafana](airflow-mlflow-prometheus-grafana/) | Orchestrated training pipeline with tracking and full observability | Airflow, MLflow, Prometheus, Grafana, Terraform |

### CI/CD for ML

| Project | Description | Stack |
|---|---|---|
| [cicd-with-gke-and-tf](cicd-with-gke-and-tf/) | Model application built, tested and deployed to managed Kubernetes | GKE, Terraform, GitHub Actions |
| [e2e-flask-jenkins-ecs](e2e-flask-jenkins-ecs/) | Training, packaging and deployment driven by a Jenkins pipeline | Jenkins, Flask, ECS, Terraform |
| [cicd-with-ec2-and-tf](cicd-with-ec2-and-tf/) | Automated delivery of a model service to EC2 | Terraform, EC2, GitHub Actions |
| [gitops-gke-machines-efficiency](gitops-gke-machines-efficiency/) | Model delivery to GKE managed declaratively through Git | ArgoCD, GKE, Terraform |


### Serving

| Project | Description | Stack |
|---|---|---|
| [fastapi-ec2-tf](fastapi-ec2-tf/) | Model-serving API layer deployed to EC2 as code | FastAPI, Docker, Terraform |

### Tracking & monitoring

| Project | Description | Stack |
|---|---|---|
| [k8s-mlflow-data-drift-grafana](k8s-mlflow-data-drift-grafana/) | Serving on Kubernetes with data drift detection and dashboards | Kubernetes, MLflow, Grafana |
| [mlflow-on-ec2-tf](mlflow-on-ec2-tf/) | Self-hosted tracking server with remote artifact storage | MLflow, EC2, S3, Terraform |
| [ann-deep-learning-with-mlflow](ann-deep-learning-with-mlflow/) | Neural network training with systematic experiment logging | TensorFlow, MLflow |
