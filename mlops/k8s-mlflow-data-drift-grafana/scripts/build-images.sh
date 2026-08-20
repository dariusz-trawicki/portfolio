#!/bin/bash
set -e

echo "Building Docker images"
echo "======================"

# Make sure you are using Docker from Minikube
eval $(minikube docker-env)

# Build training image
echo "Building training image..."
cd model
docker build -t mlops-training:latest .
cd ..

# Build serving image
echo "Building serving image..."
cd serving
docker build -t mlops-serving:latest .
cd ..

echo ""
echo "Images built successfully"
echo ""
docker images | grep mlops
