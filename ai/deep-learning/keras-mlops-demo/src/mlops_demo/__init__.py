"""End-to-end MLOps mini-project on Keras 3: customer churn, from data to monitoring."""
import os

# Keras 3 is multi-backend: the same code runs on "jax", "tensorflow" and "torch".
# The variable must be set BEFORE the first `import keras`, which is why it lives here.
os.environ.setdefault("KERAS_BACKEND", "jax")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

__version__ = "0.1.0"
