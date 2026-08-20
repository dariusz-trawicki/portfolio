#!/bin/bash

echo "Starting port-forwards..."

# Run all in the background
kubectl port-forward -n mlops svc/mlflow 5000:5000 &
kubectl port-forward -n mlops svc/prometheus 9090:9090 &
kubectl port-forward -n mlops svc/grafana 3000:3000 &

echo "Port-forwards started!"
echo "Press Ctrl+C to stop all..."

# Wait for Ctrl+C
wait
