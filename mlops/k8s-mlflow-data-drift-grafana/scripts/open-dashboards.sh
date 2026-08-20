#!/bin/bash

URL="localhost"

echo "MLOps Dashboards"
echo "================"
echo ""
echo "Available dashboards:"
echo ""
echo "1. MLflow Tracking UI"
echo "   URL: http://${URL}:5000"
echo "   Description: Experiment tracking, models, metrics"
echo ""
echo "2. Prometheus"
echo "   URL: http://${URL}:9090"
echo "   Description: Metrics and monitoring"
echo ""
echo "3. Grafana"
echo "   URL: http://${URL}:3000"
echo "   Login: admin / admin"
echo "   Description: Visualizations and dashboards"
echo ""
echo "5. Kubernetes Dashboard"
echo "   Run: minikube dashboard"
echo ""

# Ask whether to open dashboards in the browser
read -p "Open dashboards in the browser? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Opening dashboards..."
    
    # Check operating system
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        open "http://${URL}:5000" &
        open "http://${URL}:9090" &
        open "http://${URL}:3000" &
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        xdg-open "http://${URL}:5000" &
        xdg-open "http://${URL}:9090" &
        xdg-open "http://${URL}:3000" &
    else
        echo "Copy the URL manually into the browser"
    fi
    
    echo "Dashboards opened!"
fi
