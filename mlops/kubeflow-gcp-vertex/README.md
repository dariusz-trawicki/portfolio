# Vertex AI Pipelines — KFP Demo

A three-step Kubeflow Pipelines (KFP v2) workflow running on Google Cloud Vertex AI: prepare data, train a classifier, evaluate it. Small enough to read in one sitting, complete enough to show how artifacts, metadata, and lineage actually work.

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


## CI/CD (GitLab)

`.gitlab-ci.yml` defines two stages:

- **`compile-pipeline`** — compiles `pipeline.py` to `iris_pipeline.yaml` on every push to `main`. Cheap, fast, no cloud side effects.
- **`submit-pipeline`** — manual gate (`when: manual`) that submits the compiled pipeline to Vertex AI, authenticated via Workload Identity Federation (no service account keys stored in GitLab).

### One-time GCP setup for WIF

```bash
PROJECT_ID="your-project-id"
PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')"

gcloud iam workload-identity-pools create "gitlab-pool" \
  --project="$PROJECT_ID" --location="global" --display-name="GitLab CI"

gcloud iam workload-identity-pools providers create-oidc "gitlab-provider" \
  --project="$PROJECT_ID" --location="global" \
  --workload-identity-pool="gitlab-pool" \
  --issuer-uri="https://gitlab.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.project_path=assertion.project_path,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.project_path=='your-namespace/your-repo'"
```

### Permissions: bind to the `principal://` subject, not `principalSet`

`principalSet://.../attribute.project_path/...` (binding by mapped attribute) is the documented pattern, but in this project it did not reliably authorize Storage or Vertex AI calls, even with `iam.workloadIdentityUser` correctly granted and the STS token exchange succeeding. Binding directly to the `principal://` subject string — the exact identity `gcloud auth login` prints — worked immediately:

```bash
SUBJECT="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/gitlab-pool/subject/project_path:your-namespace/your-repo:ref_type:branch:ref:main"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="$SUBJECT" --role="roles/aiplatform.user"

gcloud storage buckets add-iam-policy-binding $BUCKET \
  --member="$SUBJECT" --role="roles/storage.objectAdmin"

gcloud storage buckets add-iam-policy-binding $BUCKET \
  --member="$SUBJECT" --role="roles/storage.legacyBucketReader"  # storage.buckets.get isn't in objectAdmin

gcloud iam service-accounts add-iam-policy-binding $SA \
  --member="$SUBJECT" --role="roles/iam.serviceAccountUser"  # needed for job.submit(service_account=SA)
```

Skipping the last binding fails late, at `job.submit()`, with `You do not have permission to act as service_account: ... (or it may not exist)` — easy to mistake for a missing `aiplatform.user` grant, but it's a distinct permission.

### `id_tokens` audience must be the full provider path

```yaml
id_tokens:
  GITLAB_OIDC_TOKEN:
    aud: https://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/gitlab-pool/providers/gitlab-provider
```

Just `https://iam.googleapis.com` compiles and authenticates the CLI, but fails downstream with `invalid_grant: The audience in ID Token ... does not match the expected audience` the moment a library call actually refreshes the token.

### `google/cloud-sdk:slim` needs `--break-system-packages`

Recent Debian-based images enforce PEP 668. `pip install uv` alone fails with `externally-managed-environment`; add the flag.


## Cost + clean up

Vertex AI Pipelines leaves nothing running after a run completes. Charges are per step-second on the smallest default machines — this pipeline costs a fraction of a cent per run. The only recurring cost is bucket storage.

Set a budget alert (Billing → Budgets & alerts) before experimenting with GPUs or model endpoints; endpoints bill for uptime, not requests.

Clean up artifacts:

```bash
gcloud storage rm -r ${BUCKET}/pipeline-root
gcloud storage rm -r ${BUCKET}
```

## Project layout

```
.
├── pipeline.py         # component + pipeline definitions
├── submit.py           # compile and submit to Vertex AI
├── .gitlab-ci.yml      # CI: compile on push, manual WIF-authenticated submit
├── pyproject.toml
├── uv.lock
└── README.md
```
