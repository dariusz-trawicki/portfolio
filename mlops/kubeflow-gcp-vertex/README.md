# Vertex AI Pipelines — KFP Demo

A three-step Kubeflow Pipelines (KFP v2) workflow running on Google Cloud Vertex AI: prepare data, train a classifier, evaluate it.

Built as a learning exercise for MLOps fundamentals — the same pipeline definition runs locally, on a `kind` cluster, or on Vertex AI without code changes.

## What it does

```
prepare-data ──train_set──> train-model ──model──> evaluate
     │                                                 ▲
     └──────────────── test_set ───────────────────────┘
```

Each step runs as a separate container. Execution order is derived from data dependencies, not from the order of statements — `test_set` flows straight to `evaluate`, bypassing training.

| Step | Output artifact | Type |
|---|---|---|
| `prepare-data` | `train_set`, `test_set` | `system.Dataset` |
| `train-model` | `model` | `system.Model` |
| `evaluate` | `metrics` | `system.Metrics` |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- A Google Cloud project with billing enabled

## Setup

### 1. Environment variables

```bash
export PROJECT_ID=your-project-id
export REGION=europe-central2
export BUCKET=gs://${PROJECT_ID}-kfp
export SA=kfp-runner@${PROJECT_ID}.iam.gserviceaccount.com

gcloud config set project $PROJECT_ID
gcloud config set ai/region $REGION
```

### 2. Enable APIs

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com
```

### 3. Artifact bucket

```bash
gcloud storage buckets create $BUCKET \
  --location=$REGION \
  --uniform-bucket-level-access
```

Keep the bucket in the same region as the pipeline. Cross-region works but adds egress cost and latency.

### 4. Service account

The pipeline runs *as* this identity. Don't use the default Compute Engine service account — it carries project-wide Editor.

```bash
gcloud iam service-accounts create kfp-runner \
  --display-name="KFP pipeline runner"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SA}" \
  --role="roles/aiplatform.user"

gcloud storage buckets add-iam-policy-binding $BUCKET \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectAdmin"

# lets *you* submit jobs that run as kfp-runner
gcloud iam service-accounts add-iam-policy-binding $SA \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/iam.serviceAccountUser"
```

Skipping the last binding produces `Permission 'iam.serviceAccounts.actAs' denied` at submit time.

### 5. Credentials

`gcloud auth login` authenticates the CLI. Python client libraries use a separate mechanism:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project $PROJECT_ID
```

### 6. Python dependencies

```bash
uv sync
```

## Running

```bash
uv run python submit.py
```

The script compiles `pipeline.py` to `iris_pipeline.yaml`, submits it, and prints a console link. Expect 1–3 minutes before the first step starts (Vertex provisions machines) and 6–12 minutes total — most of it spent installing packages, since each step gets a fresh container.

### Checking status

```bash
JOB=iris-demo-20260827122116

curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/pipelineJobs/${JOB}" \
  | jq -r --arg job "$JOB" '(.jobDetail.taskDetails // [])[]
      | select(.taskName != $job)
      | [.taskName, .state] | @tsv'
```

### Inspecting outputs

Artifacts land in the bucket, one directory per run and per step:

```bash
gcloud storage ls -r ${BUCKET}/pipeline-root/
```

Metrics are **not** written to disk — `log_metric()` records them in Vertex ML Metadata. Read them from the API:

```bash
curl -s -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/pipelineJobs/${JOB}" \
  | jq '(.jobDetail.taskDetails // [])[] | select(.taskName=="evaluate") | .outputs'
```

### Using the trained model

```bash
gcloud storage cp ${BUCKET}/pipeline-root/*/${JOB}/train-model_*/model /tmp/model.pkl

uv run python -c "
import pickle, pandas as pd
clf = pickle.load(open('/tmp/model.pkl','rb'))
X = pd.DataFrame([[5.1,3.5,1.4,0.2],[6.7,3.0,5.2,2.3]], columns=clf.feature_names_in_)
print(clf.predict(X))
print(clf.predict_proba(X).round(3))
"
```

Pass a `DataFrame` with named columns, not a bare list. Scikit-learn validates feature names when they're present — with a plain list it silently accepts any column order.

## Cost + clean up

Vertex AI Pipelines leaves nothing running after a run completes. Charges are per step-second on the smallest default machines — this pipeline costs a fraction of a cent per run. The only recurring cost is bucket storage.

Set a budget alert (Billing → Budgets & alerts) before experimenting with GPUs or model endpoints; endpoints bill for uptime, not requests.

Clean up artifacts:

```bash
gcloud storage rm -r ${BUCKET}/pipeline-root
```

## Project layout

```
.
├── pipeline.py       # component + pipeline definitions
├── submit.py         # compile and submit to Vertex AI
├── pyproject.toml
├── uv.lock
└── README.md
```
