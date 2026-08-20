# Smart Manufacturing Machines Efficiency Prediction

End-to-end MLOps project: a classifier predicting `Efficiency_Status` (High / Medium / Low)
for industrial machines, served from a private GKE cluster and deployed through GitOps.

Dataset: *Intelligent Manufacturing Dataset* (Kaggle) — sensor, network and production
telemetry.

---

## The point of this project

**The CI service account holds exactly one permission: `artifactregistry.writer`,
granted on a single Artifact Registry repository — not on the project.**

No `container.*` roles. No kubeconfig in GitHub secrets. CI never talks to the cluster.

That is not a detail; it is what the whole architecture is arranged around. Because
GitHub-hosted runners never need to reach the Kubernetes API, the control plane can be
closed off with `master_authorized_networks` — something that is impossible in a push-based
pipeline, where runners have dynamic IPs that can never be allow-listed.

The cluster pulls its own desired state from Git. Nothing pushes into it.

---

## Architecture

```
machines-efficiency-code          machines-efficiency-k8s-manifests
(application + CI)                (config repo)
        │                                   │
        │ build image                       │ ArgoCD polls every 3 min
        ▼                                   ▼
 Artifact Registry ◄──────────────── GKE (private cluster)
        │                                   ▲
        └── CI commits new tag ─────────────┘
```

1. Push to `main` triggers GitHub Actions.
2. The workflow authenticates to GCP via **Workload Identity Federation** (no static keys),
   builds the image and pushes it to Artifact Registry tagged with the commit SHA.
3. The workflow then checks out the config repo and rewrites the image tag in
   `k8s/deployment.yaml` with `yq`, committing the change.
4. **ArgoCD** notices the new commit and reconciles the cluster. With `selfHeal` enabled,
   manual `kubectl` edits are reverted automatically.

Rollback is `git revert` in the config repo.

---

## Repositories

| Repo | Contents | Written by |
|---|---|---|
| `machines-efficiency-tf` | `terraform/`, `terraform-argocd/` | human |
| `machines-efficiency-code` | training, app, Dockerfile, workflows | human |
| `machines-efficiency-k8s-manifests` | `k8s/deployment.yaml`, `k8s/service.yaml` | human + CI |

The config repo is separate so that the tag-bump commit does not retrigger the workflow
that produced it.

---

## Infrastructure

Two Terraform root modules with separate state. The split is not stylistic: the Helm
provider needs a cluster endpoint, and Terraform cannot configure a provider from an
attribute of a resource created in the same apply. `terraform-argocd/` reads the cluster
through a data source.

`terraform/` provisions:

- API enablement with a `time_sleep` for propagation
- a custom VPC, subnet with secondary ranges (`10.0.0.0/18` primary, `10.48.0.0/14` pods,
  `10.52.0.0/20` services)
- Cloud Router and NAT with a static egress IP
- firewall allowing SSH only via IAP (`35.235.240.0/20`, scoped by `target_tags`)
- a private VPC-native GKE cluster, two node pools (general `e2-medium`, spot with a taint)
- Artifact Registry with cleanup policies
- the CI service account and Workload Identity Federation

Apply order:

```bash
cd terraform && terraform init && terraform apply
cd ../terraform-argocd && terraform init && terraform apply
```

If `terraform plan` fails on a missing `Application` CRD, apply ArgoCD first:
`terraform apply -target=helm_release.argocd`, then apply in full. `kubernetes_manifest`
validates CRDs at plan time.

### Secrets

Three, all in the application repo:

| Secret | Source |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Terraform output |
| `GCP_SERVICE_ACCOUNT` | Terraform output |
| `CONFIG_REPO_PAT` | fine-grained PAT, `contents: write`, scoped to the config repo |

Only the last is genuinely secret. The other two are identifiers — access is granted by the
`attribute_condition` pinned to a specific repository, not by knowing the string.

The PAT is required because `GITHUB_TOKEN` is scoped to the repo running the workflow and
cannot write to another one. ArgoCD reads the private config repo through a read-only
deploy key, stored as a Kubernetes secret.

---

## Machine learning

Preprocessing and the classifier live in a single `Pipeline`, serialised as one `model.pkl`.
This is deliberate:

- `fit` runs on the training split only, so **leakage is structurally impossible** rather
  than merely avoided by convention
- column order cannot drift between training and serving
- `Operation_Mode` goes through `OneHotEncoder`, not `LabelEncoder` — logistic regression
  would otherwise read `Active=0, Idle=1, Maintenance=2` as an ordinal scale
- `LabelEncoder` is used on the target only, and is persisted, so predictions map back to
  readable labels instead of a hand-written dictionary

Training refuses to save a model below an accuracy threshold, and writes `metrics.json`
alongside it. `classification_report` is included because `average="weighted"` hides a
neglected minority class.

```bash
uv sync
uv run pytest -q
uv run python -m pipeline.training_pipeline
```

---

## Application

Flask with gunicorn, listening on port 5000, with `/health` for probes. The image contains
only what serving needs: templates, static files, the model artefacts and `application.py`.
Training code stays in the repo but not in the image.

The pod runs as a non-root user with a read-only root filesystem and all capabilities
dropped, with a writable `emptyDir` mounted at `/tmp` for gunicorn's worker heartbeat.

```bash
uv run python application.py    # http://127.0.0.1:5000
```

---

## Running this yourself

Prerequisites: a GCP project with billing enabled, `gcloud`, `terraform`, `uv`,
and three GitHub repositories of your own (this one, a config repo, and one for Terraform).

### 1. Terraform variables

Copy the examples and fill in your own values:

    cp terraform/terraform.tfvars.example terraform/terraform.tfvars
    cp terraform-argocd/terraform.tfvars.example terraform-argocd/terraform.tfvars

`terraform/terraform.tfvars`:

    project_id        = "your-gcp-project"
    region            = "europe-central2"
    zone              = "europe-central2-a"
    zone2             = "europe-central2-b"   # null for a single-zone cluster
    github_repository = "your-user/your-app-repo"

`github_repository` is not cosmetic: it becomes the `attribute_condition` on the WIF
provider, so only workflows in that exact repository can authenticate to GCP.

`terraform-argocd/terraform.tfvars`:

    project_id      = "your-gcp-project"
    cluster_name    = "your-gcp-project-gke"
    zone            = "europe-central2-a"
    config_repo_url = "git@github.com:your-user/your-config-repo.git"

`cluster_name` and `zone` must match the first module — the two states are independent and
nothing cross-checks them.

### 2. Deploy key for the config repo

ArgoCD needs read access. Generate a key, keep the private half out of any repository:

```bash
    ssh-keygen -t ed25519 -N "" -C "argocd" -f ~/.ssh/argocd_config_repo
```

Add `~/.ssh/argocd_config_repo.pub` to the config repo under
*Settings → Deploy keys*, **without** write access. Terraform reads the private key via
`config_repo_ssh_key_path` and stores it as a Kubernetes secret.

If your config repo is public, skip this and use an `https://` URL instead.

### 3. Apply, then wire up GitHub

```bash
    cd terraform && terraform init && terraform apply
    cd ../terraform-argocd && terraform init && terraform apply
```

Take `github_wif_provider` and `github_actions_sa_email` from the first module's outputs and
add them to the application repo as `GCP_WORKLOAD_IDENTITY_PROVIDER` and
`GCP_SERVICE_ACCOUNT`. Generate a fine-grained PAT scoped to the config repo with
`contents: write` and add it as `CONFIG_REPO_PAT`.

### 4. Adjust the workflow and manifests

In `.github/workflows/cicd.yaml`, set `IMAGE` and `CONFIG_REPO` to your own paths. The
image path follows the `artifact_registry_url` output plus your image name.

In the config repo, place `k8s/deployment.yaml` and `k8s/service.yaml`, with the image
field set to the same path and any placeholder tag — CI overwrites it on the first run.

### 5. Train a model before the first push

The image bakes in `artifacts/models/`, so the artefacts must exist and be committed:

```bash
    uv sync
    uv run python -m pipeline.training_pipeline
```

Training will refuse to write a model that falls below the accuracy threshold, so an empty
`artifacts/models/` after a run means the model was rejected — check the report it printed.

### 6. Tear down when finished

```bash
    cd terraform-argocd && terraform destroy
    cd ../terraform && terraform destroy
```

In that order — the second module reads the cluster created by the first.

## Notes for anyone rebuilding this

**`node_count` is per zone.** With `node_locations` set, the real node count is double what
the variable says.

**A spot pool with a `NoSchedule` taint and `min=0` is inert** until some pod carries a
matching toleration — the autoscaler will not scale up for a pod that cannot land there.

**`e2-medium` is tight on CPU, not memory.** GKE's per-node overhead (kube-proxy,
metadata-server, fluentbit, node-local-dns) is roughly 350m, and `kube-dns` reserves another
270m per replica. On a two-node cluster running ArgoCD, roughly 90% of allocatable CPU is
spoken for before any workload starts.

**WIF pools survive `terraform destroy`** as soft-deleted resources for 30 days, holding
their names. Rebuilding in the same project returns `409 already exists`; the fix is
`gcloud iam workload-identity-pools undelete` followed by `terraform import`.

**`readOnlyRootFilesystem: true` surfaces every write path.** Worth the initial friction —
afterwards you know exactly what the container touches.
