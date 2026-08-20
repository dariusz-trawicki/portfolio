"""
Drift Detector API - receives samples and monitors drift
"""
import os
import json
import time
from datetime import datetime
from collections import deque
from typing import Dict, List
import numpy as np
from scipy import stats
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
import requests

# Configuration
WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "100"))
DRIFT_THRESHOLD = float(os.getenv("DRIFT_THRESHOLD", "0.05"))
CHECK_FREQUENCY = int(os.getenv("CHECK_FREQUENCY", "20"))  # check every N samples

# Metrics
drift_score = Gauge('model_drift_score', 'KS statistic', ['feature'])
drift_pvalue = Gauge('model_drift_pvalue', 'P-value', ['feature'])
drift_detected_gauge = Gauge('model_drift_detected', 'Drift detected flag')
samples_received = Counter('drift_samples_received', 'Samples received')
drift_checks_performed = Counter('drift_checks_performed', 'Drift checks performed')
retraining_triggered_counter = Counter('drift_retraining_triggered', 'Retraining triggered')

app = FastAPI(title="Drift Detector API")

# Reference data (from training)
from sklearn.datasets import load_iris
iris = load_iris()
reference_data = iris.data

# Current data window
current_window = deque(maxlen=WINDOW_SIZE)
sample_count = 0
last_drift_time = 0
RETRAIN_COOLDOWN = 300  # 5 minutes

class Sample(BaseModel):
    features: List[float]

def check_drift() -> Dict:
    """Check drift using KS test method"""
    if len(current_window) < WINDOW_SIZE // 2:
        return {"drift_detected": False, "reason": "insufficient_data"}
    
    current_data = np.array(list(current_window))
    
    max_ks_stat = 0
    min_pvalue = 1.0
    drift_results = {}
    
    for i in range(current_data.shape[1]):
        ref_feature = reference_data[:, i]
        cur_feature = current_data[:, i]
        
        ks_stat, p_value = stats.ks_2samp(ref_feature, cur_feature)
        
        drift_results[f'feature_{i}'] = {
            'ks_statistic': float(ks_stat),
            'p_value': float(p_value),
            'drift': bool(p_value < DRIFT_THRESHOLD)
        }
        
        drift_score.labels(feature=f'feature_{i}').set(ks_stat)
        drift_pvalue.labels(feature=f'feature_{i}').set(p_value)
        
        max_ks_stat = max(max_ks_stat, ks_stat)
        min_pvalue = min(min_pvalue, p_value)
    
    is_drift = bool(min_pvalue < DRIFT_THRESHOLD)
    drift_detected_gauge.set(1 if is_drift else 0)
    drift_checks_performed.inc()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "drift_detected": is_drift,                 # bool (python)
        "max_ks_statistic": float(max_ks_stat),     # float (python)
        "min_pvalue": float(min_pvalue),            # float (python)
        "features": drift_results,
        "window_size": int(len(current_window))     # int (python)
    }

def trigger_retraining():
    """Trigger Kubernetes Job for retraining"""
    global last_drift_time
    
    print("DRIFT DETECTED - Triggering retraining...")
    
    try:
        import kubernetes
        from kubernetes import client, config
        
        try:
            config.load_incluster_config()
        except:
            config.load_kube_config()
        
        batch_v1 = client.BatchV1Api()
        job_name = f"drift-retrain-{int(time.time())}"
        
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace="mlops",
                labels={"trigger": "drift"}
            ),
            spec=client.V1JobSpec(
                ttl_seconds_after_finished=3600,
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": "training"}),
                    spec=client.V1PodSpec(
                        restart_policy="OnFailure",
                        containers=[
                            client.V1Container(
                                name="trainer",
                                image="mlops-training:latest",
                                image_pull_policy="Never",
                                env=[
                                    client.V1EnvVar(name="MLFLOW_TRACKING_URI", value="http://mlflow:5000"),
                                ],
                                volume_mounts=[
                                    client.V1VolumeMount(name="models", mount_path="/models")
                                ]
                            )
                        ],
                        volumes=[
                            client.V1Volume(
                                name="models",
                                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                    claim_name="models-pvc"
                                )
                            )
                        ]
                    )
                )
            )
        )
        
        batch_v1.create_namespaced_job(namespace="mlops", body=job)
        retraining_triggered_counter.inc()
        last_drift_time = time.time()
        print(f"Retraining job created: {job_name}")
        
    except Exception as e:
        print(f"Failed to trigger retraining: {e}")

@app.post("/add_sample")
async def add_sample(sample: Sample, background_tasks: BackgroundTasks):
    """Add sample for monitoring"""
    global sample_count
    
    current_window.append(sample.features)
    samples_received.inc()
    sample_count += 1
    
    # Check drift every CHECK_FREQUENCY samples
    if sample_count % CHECK_FREQUENCY == 0:
        background_tasks.add_task(check_and_react_to_drift)
    
    return {"status": "ok", "window_size": len(current_window)}

def check_and_react_to_drift():
    """Check drift and react if detected"""
    global last_drift_time
    
    drift_info = check_drift()
    
    if drift_info["drift_detected"]:
        print(f"DRIFT: KS={drift_info['max_ks_statistic']:.4f}, "
              f"p={drift_info['min_pvalue']:.4f}")
        
        # Trigger with cooldown
        current_time = time.time()
        if current_time - last_drift_time > RETRAIN_COOLDOWN:
            trigger_retraining()

@app.get("/drift_status")
async def drift_status():
    """Drift detection status"""
    if len(current_window) < WINDOW_SIZE // 2:
        return {
            "status": "warming_up",
            "window_size": len(current_window),
            "required": WINDOW_SIZE // 2
        }
    
    drift_info = check_drift()
    return drift_info

@app.get("/metrics")
async def metrics():
    """Prometheus metrics"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/health")
async def health():
    return {"status": "healthy", "window_size": len(current_window)}

@app.post("/reset")
async def reset_window():
    """Reset window (for testing)"""
    current_window.clear()
    return {"status": "reset", "window_size": 0}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
