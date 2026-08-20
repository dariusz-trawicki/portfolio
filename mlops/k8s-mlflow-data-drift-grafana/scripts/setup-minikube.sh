#!/bin/bash
set -e

echo "Minikube configuration for MLOps demo"
echo "====================================="

# Check if minikube is installed
if ! command -v minikube &> /dev/null; then
    echo "Minikube is not installed!"
    echo "Install it from: https://minikube.sigs.k8s.io/docs/start/"
    exit 1
fi

# Start Minikube with sufficient resources
echo "Starting Minikube..."
minikube start \
    --cpus=4 \
    --memory=8192 \
    --disk-size=20g \
    --driver=docker \
    --kubernetes-version=v1.28.3

# Enable addons
echo "Enabling addons..."
minikube addons enable metrics-server
minikube addons enable ingress

# Configure docker environment
echo "Configuring Docker environment..."
eval $(minikube docker-env)

echo ""
echo "Minikube is ready!"
echo ""
echo "Useful commands:"
echo "   minikube dashboard    - Open the Kubernetes dashboard"
echo "   minikube ip           - Show cluster IP"
echo "   minikube stop         - Stop the cluster"
echo "   minikube delete       - Delete the cluster"
echo ""
echo "Tip: use: eval \$(minikube docker-env)"
echo "to build images directly inside Minikube"
