#!/bin/bash
set -e

echo "Drift Simulator"
echo "=================="

echo "Setting up port forwarding..."

# Model serving
kubectl port-forward -n mlops svc/model-serving 8000:8000 > /dev/null 2>&1 &
PF_MODEL=$!

# Drift detector
kubectl port-forward -n mlops svc/drift-detector 8002:8002 > /dev/null 2>&1 &
PF_DETECTOR=$!

# Wait a moment
sleep 3

echo "Port forwarding active"
echo "   Model API: http://localhost:8000"
echo "   Detector:  http://localhost:8002"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up port forwarding..."
    kill $PF_MODEL $PF_DETECTOR 2>/dev/null || true
    echo "Bye!"
}

trap cleanup EXIT INT TERM

# Check
echo "Checking Python dependencies..."
python3 -c "import requests, numpy, scipy, sklearn" 2>/dev/null || {
    echo "Installing required packages..."
    pip3 install requests numpy scipy scikit-learn --break-system-packages
}

# Run simulator
echo ""
echo "Starting drift simulator..."
echo ""

cd drift-detection
python3 simulator.py

cd ..
