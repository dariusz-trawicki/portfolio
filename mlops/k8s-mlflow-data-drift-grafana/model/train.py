"""
Model training script with MLflow tracking
"""
import os
import pickle
import json
from datetime import datetime
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
import mlflow
import mlflow.sklearn
import numpy as np

# Configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = "iris-classifier"
MODEL_PATH = "/models"

def load_data():
    """Load Iris dataset"""
    print("Loading Iris dataset...")
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.2, random_state=42
    )
    return X_train, X_test, y_train, y_test, iris.target_names

def train_model(X_train, y_train, n_estimators=100, max_depth=5):
    """Train Random Forest model"""
    print(f"Training model (n_estimators={n_estimators}, max_depth={max_depth})...")
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=42
    )
    model.fit(X_train, y_train)
    return model

def evaluate_model(model, X_test, y_test):
    """Evaluate model"""
    print("Evaluating model...")
    y_pred = model.predict(X_test)
    
    metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "f1_score": f1_score(y_test, y_pred, average='weighted'),
        "precision": precision_score(y_test, y_pred, average='weighted'),
        "recall": recall_score(y_test, y_pred, average='weighted')
    }
    
    print(f"  Accuracy: {metrics['accuracy']:.4f}")
    print(f"  F1 Score: {metrics['f1_score']:.4f}")
    print(f"  Precision: {metrics['precision']:.4f}")
    print(f"  Recall: {metrics['recall']:.4f}")
    
    return metrics

def save_model_locally(model, metrics, target_names):
    """Save model locally (for serving via mounted volume)"""
    os.makedirs(MODEL_PATH, exist_ok=True)
    
    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_dir = f"{MODEL_PATH}/{version}"
    os.makedirs(model_dir, exist_ok=True)
    
    # Save model
    model_file = f"{model_dir}/model.pkl"
    with open(model_file, 'wb') as f:
        pickle.dump(model, f)
    
    # Save metadata
    metadata = {
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "metrics": metrics,
        "target_names": target_names.tolist(),
        "model_type": "RandomForestClassifier"
    }
    
    with open(f"{model_dir}/metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)
    
    # Create symlink to latest
    latest_link = f"{MODEL_PATH}/latest"
    if os.path.exists(latest_link):
        os.remove(latest_link)
    os.symlink(model_dir, latest_link)
    
    print(f"Model saved to: {model_dir}")
    print(f"Latest symlink: {latest_link}")
    
    return version

def main():
    """Main training function"""
    print("=" * 60)
    print("MLOps Demo - Model Training")
    print("=" * 60)
    
    # MLflow configuration
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("iris-classification")
    
    # Load data
    X_train, X_test, y_train, y_test, target_names = load_data()
    
    # Hyperparameters (can be passed via environment variables)
    n_estimators = int(os.getenv("N_ESTIMATORS", "100"))
    max_depth = int(os.getenv("MAX_DEPTH", "5"))
    
    # Start MLflow run
    with mlflow.start_run(
        run_name=f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ):
        
        # Log parameters
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_param("max_depth", max_depth)
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("test_size", len(X_test))
        
        # Train model
        model = train_model(X_train, y_train, n_estimators, max_depth)
        
        # Evaluate model
        metrics = evaluate_model(model, X_test, y_test)
        
        # Log metrics to MLflow
        for metric_name, metric_value in metrics.items():
            mlflow.log_metric(metric_name, metric_value)
        
        # Log model to MLflow
        mlflow.sklearn.log_model(
            model,
            "model",
            registered_model_name=MODEL_NAME
        )
        
        # Save model locally (for serving)
        version = save_model_locally(model, metrics, target_names)
        mlflow.log_param("local_version", version)
        
        print("\nTraining completed successfully")
        print(f"Accuracy: {metrics['accuracy']:.4f}")
        print(f"Model version: {version}")

if __name__ == "__main__":
    main()
