#!/bin/bash
set -e

echo "Model training"
echo "=============="

# Remove previous job if it exists
kubectl delete job model-training -n mlops --ignore-not-found=true

# Start a new job
echo "Starting training job..."
kubectl apply -f k8s/03-training-job.yaml

# Wait for the job to complete
echo "Waiting for training to complete..."
kubectl wait --for=condition=complete --timeout=300s job/model-training -n mlops

# Show logs
echo ""
echo "Training logs:"
echo "=============="
kubectl logs -n mlops job/model-training

# Check if the model was saved
echo ""
echo "Checking saved model..."
TRAINING_POD=$(kubectl get pods -n mlops -l job-name=model-training -o jsonpath='{.items[0].metadata.name}')
echo "Pod: $TRAINING_POD"

echo ""
echo "Training completed!"
echo ""
echo "See details in MLflow: http://localhost:5000"
