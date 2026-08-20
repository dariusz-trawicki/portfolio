#!/bin/bash
set -e

echo "Deploying model serving"
echo "======================="

kubectl apply -f k8s/04-model-serving.yaml

echo "Waiting for model serving..."
kubectl wait --for=condition=available --timeout=120s deployment/model-serving -n mlops

sleep 10

echo ""
echo "Model serving deployed successfully"
echo ""
kubectl get pods -n mlops -l app=model-serving
