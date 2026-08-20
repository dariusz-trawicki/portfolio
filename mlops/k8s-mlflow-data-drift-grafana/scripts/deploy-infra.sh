#!/bin/bash
set -e

echo "Deploying MLOps infrastructure"
echo "=============================="

# Deploy base infrastructure
echo "Deploying namespace and storage..."
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-storage.yaml

# Wait until PVC is bound
echo "Waiting for PVC..."
# kubectl wait --for=condition=bound pvc/models-pvc -n mlops --timeout=60s
# Check whether PVC is bound
until kubectl get pvc models-pvc -n mlops -o jsonpath='{.status.phase}' 2>/dev/null | grep -q "Bound"; do
  echo "Waiting for PVC..."
  sleep 2
done
echo "PVC is Bound"

# Deploy MLflow
echo "Deploying MLflow..."
kubectl apply -f k8s/02-mlflow.yaml

# Wait until MLflow is ready
echo "Waiting for MLflow..."
kubectl wait --for=condition=available --timeout=120s deployment/mlflow -n mlops

# Deploy Prometheus
echo "Deploying Prometheus..."
kubectl apply -f k8s/05-prometheus.yaml

# Wait for Prometheus
echo "Waiting for Prometheus..."
kubectl wait --for=condition=available --timeout=120s deployment/prometheus -n mlops

# Deploy Grafana
echo "Deploying Grafana..."
kubectl apply -f k8s/06-grafana.yaml

# Wait for Grafana
echo "Waiting for Grafana..."
kubectl wait --for=condition=available --timeout=120s deployment/grafana -n mlops

echo "Status:"
kubectl get all -n mlops
