# Kubeflow Pipeline for an End-to-End Machine Learning Workflow

## Kubeflow

`Kubeflow` is an `MLOps` platform on `Kubernetes` — it orchestrates the entire ML model lifecycle:
- `Pipelines` (KFP) — DAGs of ML steps (load → preprocess → train → evaluate) — this is the part used here
- `Training Operators` — distributed training (TensorFlow, PyTorch)
- `Model Registry` — model versioning
- `KServe` — model serving (REST/gRPC)
- `Notebooks` — JupyterHub on the cluster

NOTE: The `Kubeflow` docs suggest running local demos via `Docker Desktop > Kubernetes` — BUT in my case it did NOT work: RAM issues. `Minikube` also kept crashing. `KIND` was the stable option.


## Prerequisites

- **Docker** — required by KIND, which runs Kubernetes nodes as containers.
  Give Docker enough resources (RAM/CPU) in its settings — this is the most
  common cause of pods getting stuck in `ContainerCreating`/`CrashLoopBackOff`
  on the platform-agnostic Kubeflow install. 8 GB RAM allocated to Docker is
  a reasonable starting point; increase it if pods keep restarting.
- **kubectl** — the Kubernetes CLI, used to apply manifests and inspect the cluster.
- **KIND** (Kubernetes IN Docker) — creates the local cluster.
- **uv** — used to manage the Python environment and run the `kfp` CLI.
- **Freelens** (optional) — GUI for browsing the cluster (pods, logs, namespaces).

**macOS (Homebrew):**
```bash
brew install docker kubectl kind uv
brew install --cask freelens   # optional

# Verify everything is in place:
docker --version
kubectl version --client
kind --version
uv --version
```



## Example: file `kubeflow_pipeline.py`

This is an `ML pipeline` built with `Kubeflow Pipelines` (KFP) on the `Iris` dataset (flowers). It consists of 4 steps:

**Step 1 – `load_data`**
- Loads the Iris `dataset` from `sklearn`, converts it to a `DataFrame`, and saves it as `CSV` (a Dataset artifact).

**Step 2 – `preprocess_data`**
- Handles missing values (`dropna`)
- Standardizes features (`StandardScaler`)
- Splits into train/test sets (80/20, `random_state=42`)
- Returns 4 artifacts: `X_train`, `X_test`, `y_train`, `y_test`

**Step 3 – `train_model`**
- Loads `X_train` and `y_train`
- Trains a `LogisticRegression` model
- Saves the model via `joblib` as a Model artifact

**Step 4 – `evaluate_model`**
- Loads the test data and the model
- Generates a `classification_report` and confusion matrix
- Saves the metrics to a `.txt` file and the confusion-matrix plot to a `.png` file

Overall structure:
`load_data → preprocess_data → train_model → evaluate_model`

Each component runs in an isolated `python:3.12` container, installing dependencies via `subprocess` (a typical KFP pattern). The pipeline is compiled into a `kubeflow_pipeline.yaml` file.

```bash
# Create a cluster with KIND
kind create cluster --name=kubeflow
kubectl cluster-info

# Optional: K8s monitoring with Freelens
open -a Freelens
# Click the green icon > Clusters > kind-kubeflow >
# > (top bar) Namespace: kubeflow, then e.g. the Pods tab

# Install/deploy Kubeflow Pipelines:
export PIPELINE_VERSION=2.15.0
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=$PIPELINE_VERSION"
kubectl wait --for condition=established --timeout=60s crd/applications.app.k8s.io
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/platform-agnostic?ref=$PIPELINE_VERSION"
# This takes a few minutes to come up...

kubectl get all -n kubeflow   # sanity check -> everything should show READY 1/1

# Port-forward (this blocks the terminal)
kubectl port-forward svc/ml-pipeline-ui 8080:80 -n kubeflow
# Open in your browser: http://127.0.0.1:8080

# Terminal II:
# if you have/clone: pyproject.toml, .python-version, uv.lock
uv sync 
# else:
# uv init .
# uv venv --python 3.11
# uv add kfp==2.7.0 scikit-learn pandas
# uv run kfp --version  # sanity check


# Compile to kubeflow_pipeline.yaml:
uv run python kubeflow_pipeline.py

# Upload the compiled kubeflow_pipeline.yaml to Kubeflow
# and register it as a pipeline named IrisProject:
uv run kfp pipeline create -p IrisProject kubeflow_pipeline.yaml

# Run pipeline:
uv run kfp run create -e Default -r IrisRun -f kubeflow_pipeline.yaml

# ... WAIT FOR IT ...
```

In the browser: http://127.0.0.1:8080
- left menu > Pipelines > IrisRun
- left menu > Runs > IrisRun
- ...after a moment, a green arrow appears next to `load-data`
- click into `load-data` > Logs — if it's red: WAIT and refresh


## Pipeline view

This is the DAG of your pipeline in the Kubeflow UI. There are two node types:
- list icon = a step (a Pod on K8s)
- folder icon = an artifact (a file passed between steps)

Flow:

```
load-data
    │
    └──► output_csv          ← artifact: raw CSV data
              │
              ▼
        preprocess-data
         │    │    │    │
         ▼    ▼    ▼    ▼
   output_  output_  output_  output_
   train    y_train  test     y_test
              │
         ┌────┘
         ▼
    train-model  ◄── output_y_train
         │
         ▼
    model_output             ← artifact: trained model (.pkl)
         │
         ▼
   evaluate-model ◄── output_test + output_y_test
         │
         ▼
   metrics_output            ← artifact: accuracy, report
```

**What each step does:**
- `load-data` — fetches the Iris dataset, saves it as `output_csv`
- `preprocess-data` — runs `train_test_split`, returns 4 artifacts:
  - `output_train` / `output_y_train` → used for training
  - `output_test` / `output_y_test` → used for evaluation
- `train-model` — trains the model on `output_train` + `output_y_train`, saves `model_output`
- `evaluate-model` — takes `model_output` + the test data → produces `metrics_output`


## Versioning changes

If you change something in `kubeflow_pipeline.py`, use this naming convention:

| What      | Name                | Example              |
|-----------|----------------------|-----------------------|
| Pipeline  | topic/project        | `IrisPipeline`        |
| Version   | what changed          | `v2-py312`, `v3-fix-oom`, `v4-add-eval` |
| Run       | version + date        | `IrisRun-v2-0312`      |

Example: bumping the Python version in the `.py` file from 3.11 to 3.12:

```bash
uv run python kubeflow_pipeline.py
uv run kfp pipeline create -p IrisProject-v2-py312 kubeflow_pipeline.yaml
uv run kfp run create -e Default -r IrisRun-v2-0312 -f kubeflow_pipeline.yaml
```

## Cleanup

```bash
# Delete the cluster
kind delete cluster --name kubeflow
```
