#!/bin/bash
set -e

echo "Deployment Drift Detection System"
echo "====================================="

# Make sure you are using Docker with Minikube
eval $(minikube docker-env)

# Build image drift detector
echo "Building a drift detector image..."
cd drift-detection
docker build -t mlops-drift-detector:latest .
cd ..

# Deploy drift detector
echo "📦 Deploying drift detector..."
kubectl apply -f k8s/07-drift-detector.yaml

# Wait for deployment
echo "I'm waiting for the drift detector..."
kubectl wait --for=condition=available --timeout=120s deployment/drift-detector -n mlops

# Deploy Grafana dashboard
echo "Deploying Grafana drift dashboard..."
kubectl apply -f k8s/08-grafana-drift-dashboard.yaml

# Restart Grafana to load the new dashboard
echo "Restarting Grafana..."
kubectl rollout restart deployment/grafana -n mlops
kubectl wait --for=condition=available --timeout=120s deployment/grafana -n mlops

echo ""
echo "Drift Detection - the system is ready!"
echo ""
echo "Endpointy:"
URL="localhost"

echo "   Drift Status:  kubectl port-forward -n mlops svc/drift-detector 8002:8002"
echo "                  http://localhost:8002/drift_status"
echo ""
echo "   Grafana:       http://${URL}:3000"
echo "                  Dashboard: 'MLOps - Data Drift Monitoring'"
echo ""
echo "To simulate drift:"
echo "   ./scripts/simulate-drift.sh"
