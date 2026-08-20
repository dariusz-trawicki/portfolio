"""
Drift Simulator - Generates traffic with different distributions to simulate drift
"""
import os
import time
import requests
import numpy as np
from datetime import datetime
from sklearn.datasets import load_iris

# Configuration
MODEL_API_URL = os.getenv("MODEL_API_URL", "http://localhost:8000")
DETECTOR_URL = os.getenv("DETECTOR_URL", "http://localhost:8002")
REQUESTS_PER_SECOND = float(os.getenv("RPS", "1"))

class DriftSimulator:
    """Simulates different data drift scenarios"""
    
    def __init__(self):
        iris = load_iris()
        self.original_data = iris.data
        self.original_mean = np.mean(self.original_data, axis=0)
        self.original_std = np.std(self.original_data, axis=0)
        
    def generate_normal_sample(self) -> list:
        """Generate normal sample (no drift)"""
        idx = np.random.randint(0, len(self.original_data))
        sample = self.original_data[idx].tolist()
        return sample
    
    def generate_shifted_sample(self, shift_factor=1.5) -> list:
        """Generate sample with mean shift (concept drift)"""
        idx = np.random.randint(0, len(self.original_data))
        sample = self.original_data[idx].copy()
        
        # Shift all features
        sample = sample + (shift_factor * self.original_std)
        return sample.tolist()
    
    def generate_scaled_sample(self, scale_factor=2.0) -> list:
        """Generate sample with changed variance"""
        idx = np.random.randint(0, len(self.original_data))
        sample = self.original_data[idx].copy()
        
        # Increase variance
        sample = self.original_mean + (sample - self.original_mean) * scale_factor
        return sample.tolist()
    
    def generate_noise_sample(self, noise_level=0.5) -> list:
        """Generate sample with additional noise"""
        idx = np.random.randint(0, len(self.original_data))
        sample = self.original_data[idx].copy()
        
        # Add random noise
        noise = np.random.normal(0, noise_level, sample.shape)
        sample = sample + noise
        return sample.tolist()
    
    def generate_feature_drift_sample(self, feature_idx=0, drift=2.0) -> list:
        """Generate sample with drift in only one feature"""
        idx = np.random.randint(0, len(self.original_data))
        sample = self.original_data[idx].copy()
        
        # Drift only in selected feature
        sample[feature_idx] = sample[feature_idx] + drift
        return sample.tolist()

def send_prediction_request(sample: list) -> dict:
    """Send request to model"""
    try:
        response = requests.post(
            f"{MODEL_API_URL}/predict",
            json={"features": [sample]},
            timeout=5
        )
        return response.json()
    except Exception as e:
        print(f"Prediction request failed: {e}")
        return None

def notify_detector(sample: list):
    """Notify drift detector about new prediction"""
    try:
        requests.post(
            f"{DETECTOR_URL}/add_sample",
            json={"features": sample},
            timeout=2
        )
    except:
        pass  # Detector may be optional

def run_scenario(simulator: DriftSimulator, scenario: str, duration: int):
    """Run scenario for specified time"""
    print(f"\n{'='*60}")
    print(f"Scenario: {scenario}")
    print(f"Duration: {duration}s")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    requests_sent = 0
    
    while time.time() - start_time < duration:
        # Choose sample type depending on scenario
        if scenario == "normal":
            sample = simulator.generate_normal_sample()
        elif scenario == "shifted":
            sample = simulator.generate_shifted_sample(shift_factor=1.5)
        elif scenario == "scaled":
            sample = simulator.generate_scaled_sample(scale_factor=2.0)
        elif scenario == "noisy":
            sample = simulator.generate_noise_sample(noise_level=1.0)
        elif scenario == "feature_drift":
            sample = simulator.generate_feature_drift_sample(feature_idx=0, drift=2.0)
        elif scenario == "gradual":
            # Gradually increasing drift
            elapsed = time.time() - start_time
            shift = (elapsed / duration) * 2.0
            sample = simulator.generate_shifted_sample(shift_factor=shift)
        else:
            sample = simulator.generate_normal_sample()
        
        # Send prediction
        result = send_prediction_request(sample)
        
        if result:
            requests_sent += 1
            if requests_sent % 10 == 0:
                elapsed = int(time.time() - start_time)
                print(f"[{elapsed:3d}s] Sent: {requests_sent:4d} requests | "
                      f"Last prediction: {result['predictions'][0]}")
        
        # Notify detector
        notify_detector(sample)
        
        # Wait
        time.sleep(1 / REQUESTS_PER_SECOND)
    
    print(f"\nScenario completed: {requests_sent} requests sent\n")

def main():
    print("=" * 60)
    print("Data Drift Simulator")
    print("=" * 60)
    print(f"Model API: {MODEL_API_URL}")
    print(f"Detector API: {DETECTOR_URL}")
    print(f"Request rate: {REQUESTS_PER_SECOND} RPS")
    print("=" * 60)
    
    simulator = DriftSimulator()
    
    scenarios = [
        ("normal", 60, "Normal traffic - no drift"),
        ("shifted", 90, "Mean shift - concept drift"),
        ("normal", 30, "Return to normal"),
        ("scaled", 60, "Increased variance"),
        ("normal", 30, "Return to normal"),
        ("feature_drift", 60, "Drift in one feature"),
        ("normal", 30, "Return to normal"),
        ("gradual", 120, "Gradually increasing drift"),
        ("normal", 60, "Stabilization"),
    ]
    
    print("\nPlanned scenarios:")
    for i, (name, duration, desc) in enumerate(scenarios, 1):
        print(f"  {i}. {name:15s} ({duration:3d}s) - {desc}")
    
    input("\nPress ENTER to start simulation...")
    
    try:
        for scenario_name, duration, description in scenarios:
            run_scenario(simulator, scenario_name, duration)
            
        print("\n" + "="*60)
        print("All scenarios completed!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nSimulation stopped by user")

if __name__ == "__main__":
    main()
