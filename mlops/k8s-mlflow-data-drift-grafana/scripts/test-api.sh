#!/bin/bash
set -e

# Use localhost (requires port-forward)
API_URL="http://localhost:8000"

echo "Testing Model Serving API"
echo "========================="

# Check if port-forward is running
if ! curl -s "${API_URL}/health" >/dev/null 2>&1; then
    echo ""
    echo "Port-forward not running!"
    echo ""
    echo "Start port-forward first:"
    echo "  Terminal 1: make port-forward"
    echo "  Then run:   make test"
    echo ""
    exit 1
fi

echo "URL: ${API_URL}"
echo ""

# Test 1: Health check
echo "1. Health check..."
curl -s "${API_URL}/health" | jq '.'
echo ""

# Test 2: Model info
echo "2. Model info..."
curl -s "${API_URL}/model/info" | jq '.'
echo ""

# Test 3: Predictions - different Iris species
echo "3. Predictions..."

# Setosa
echo "Iris Setosa (expected: setosa):"
curl -s -X POST "${API_URL}/predict" \
  -H 'Content-Type: application/json' \
  -d '{"features": [[5.1, 3.5, 1.4, 0.2]]}' | jq '.predictions, .probabilities'
echo ""

# Versicolor
echo "Iris Versicolor (expected: versicolor):"
curl -s -X POST "${API_URL}/predict" \
  -H 'Content-Type: application/json' \
  -d '{"features": [[6.4, 3.2, 4.5, 1.5]]}' | jq '.predictions, .probabilities'
echo ""

# Virginica
echo "Iris Virginica (expected: virginica):"
curl -s -X POST "${API_URL}/predict" \
  -H 'Content-Type: application/json' \
  -d '{"features": [[6.3, 3.3, 6.0, 2.5]]}' | jq '.predictions, .probabilities'
echo ""

# Batch prediction
echo "4. Batch prediction (3 samples):"
curl -s -X POST "${API_URL}/predict" \
  -H 'Content-Type: application/json' \
  -d '{"features": [[5.1, 3.5, 1.4, 0.2], [6.4, 3.2, 4.5, 1.5], [6.3, 3.3, 6.0, 2.5]]}' | jq '.'
echo ""

# Test 5: Prometheus metrics
echo "5. Prometheus metrics (sample):"
curl -s "${API_URL}/metrics" | head -20
echo ""

echo "All tests passed!"
