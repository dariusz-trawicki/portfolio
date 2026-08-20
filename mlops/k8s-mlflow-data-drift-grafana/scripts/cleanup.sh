#!/bin/bash

echo "Cleaning MLOps Demo"
echo "===================="
echo ""

read -p "Are you sure you want to delete all resources? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Cancelled"
    exit 0
fi

echo "Deleting resources..."

# Delete mlops namespace (removes all resources)
echo "Deleting mlops namespace..."
kubectl delete namespace mlops --ignore-not-found=true

# Delete PersistentVolume (not namespaced)
echo "Deleting PersistentVolume..."
kubectl delete pv models-pv --ignore-not-found=true

# Optionally stop Minikube
read -p "Stop Minikube? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Stopping Minikube..."
    minikube stop
fi

# Optionally delete Minikube completely
read -p "Delete Minikube cluster completely? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo "Deleting Minikube..."
    minikube delete
fi

echo ""
echo "Cleanup completed successfully"
