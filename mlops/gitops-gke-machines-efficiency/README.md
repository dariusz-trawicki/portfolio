# Smart Manufacturing Machines Efficiency Prediction

End-to-end MLOps project: a classifier predicting `Efficiency_Status` (High / Medium / Low)
for industrial machines, served from a private GKE cluster, deployed through GitOps and
observed with Prometheus and Grafana.

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
   builds the image, scans it with Trivy and pushes it to Artifact Registry tagged with the
   commit SHA.
3. The workflow then checks out the config repo and rewrites the image tag and the `GIT_SHA`
   environment variable in `k8s/deployment.yaml` with `yq`, committing the change.
4. **ArgoCD** notices the new commit and reconciles the cluster. With `selfHeal` enabled,
   manual `kubectl` edits are reverted automatically.

Rollback is `git revert` in the config repo.

### app-of-apps

Terraform stops at ArgoCD. It creates the cluster, installs ArgoCD, and creates a single
root `Application` pointing at `apps/` in the config repo. Everything above that line is
described by Git:

```
Terraform  →  Application "root"
                    ↓ reads apps/
              apps/monitoring.yaml      → kube-prometheus-stack (Helm repo)
              apps/machines.yaml   → k8s/ (config repo)
                    ↓
              pods
```

Adding a component to the cluster is a commit, not a `terraform apply`. The root
Application describes no component of its own — it names a directory and nothing else.

A bootstrap point always has to exist outside the loop: ArgoCD cannot install itself into
an empty cluster. The only question is how early to put the seam, and here it is as early
as it can be. The alternative — a second `helm_release` per component — would leave the
cluster with two sources of truth and two procedures for changing it.

Monitoring is deployed the same way, as an Application rather than from Terraform, for the
same reason. Google Managed Prometheus was the alternative: it removes the Prometheus and
Alertmanager pods, the PVC and the node-sizing problem entirely, but it moves retention,
ServiceMonitors and alert rules outside Git — and enabling it is a change to the cluster
resource, which is a Terraform change. GMP is the better choice when a cluster must run
unattended or metrics must outlive it. Neither applies here.

---

## Repositories

| Repo | Contents | Written by |
|---|---|---|
| `machines-efficiency-tf` | `terraform/`, `terraform-argocd/` | human |
| `machines-efficiency-code` | training, app, Dockerfile, workflows | human |
| `machines-efficiency-k8s-manifests` | `apps/` (Applications), `k8s/` (manifests) | human + CI |

The config repo is separate so that the tag-bump commit does not retrigger the workflow
that produced it.

`apps/` and `k8s/` are separate directories, and that is load-bearing rather than tidy: the
root Application deploys everything under the path it is given. With the manifests under
`apps/`, the root would apply the Deployment directly while the child Application applied
it too — two owners, one resource, a conflict on every sync.

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
- a private VPC-native GKE cluster, two node pools (general `e2-standard-2`, spot with a taint)
- Artifact Registry with cleanup policies
- the CI service account and Workload Identity Federation

`terraform-argocd/` holds three resources and nothing more: the ArgoCD release, the root
Application, and the Kubernetes secret carrying the config-repo deploy key.

The root Application is created through the `argocd-apps` Helm chart rather than
`kubernetes_manifest`, because `kubernetes_manifest` validates CRDs at *plan* time — and
the `Application` CRD does not exist until the ArgoCD release is applied. Helm renders at
apply time, so a single `terraform apply` works.

Apply order:

```bash
cd terraform && terraform init && terraform apply
cd ../terraform-argocd && terraform init && terraform apply
```

Push the application repo between the two, so that an image exists before ArgoCD looks for
one. See *Running this yourself* below.

### Chart versions

Both charts are pinned in `variables.tf`. Check them against the cluster before applying —
a chart several majors behind the Kubernetes version fails in ways that point at the wrong
thing (see *Notes for anyone rebuilding this*).

```bash
helm search repo argo/argo-cd --versions | head -3
helm search repo prometheus-community/kube-prometheus-stack --versions | head -3
```

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

The single-artefact form also means there is nothing to lose on the way out. A model saved
without its scaler still loads, still predicts, and still returns a plausible-looking class
— from inputs on a scale it never trained on. That failure is silent by construction, which
is why the transformers are not separate files.

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

Flask with gunicorn, listening on port 5000, with `/health` for probes and `/metrics` for
Prometheus. The image contains only what serving needs: templates, static files, the model
artefacts and `application.py`. Training code stays in the repo but not in the image.

The pod runs as a non-root user with a read-only root filesystem and all capabilities
dropped, with a writable `emptyDir` mounted at `/tmp` for gunicorn's worker heartbeat.

**gunicorn runs with a single worker.** Each worker process keeps its own metrics registry,
so `/metrics` would answer from whichever process happened to take the request — counters
appear to move backwards and `rate()` returns nonsense. Concurrency comes from threads, and
scale from Deployment replicas: Prometheus scrapes each pod separately and sums them.

**`Service.type: LoadBalancer` provisions a real cloud load balancer, billed hourly
regardless of traffic.** It is used here only because the app needs a browser-facing
demo; if the goal were purely to let in-cluster Prometheus scrape `/metrics`, `ClusterIP`
would be the correct default — cheaper and with no unauthenticated `/metrics` endpoint
sitting on the public internet. An `Ingress` would be the middle ground for multiple
HTTP services behind one address, but is unnecessary for a single app with no other
services to route.

```bash
uv run python application.py    # http://127.0.0.1:5000
```

---

## Monitoring

Three layers, in increasing order of how much work they take and how much they say about
*this* project rather than about Kubernetes in general.

### 1. Infrastructure — free with the chart

CPU and memory per pod, restarts, node state, `kube-state-metrics`. Nothing to configure.

On GKE the `kube-scheduler`, `kube-controller-manager` and `etcd` targets stay `DOWN`: the
control plane is managed by Google and does not expose those ports. The bundled "Control
Plane" dashboards are partly empty as a result. Not fixable, not a problem.

### 2. ArgoCD — two flags

Enabled in `terraform-argocd/main.tf`, because ArgoCD does not manage itself. This is the
one piece of monitoring that stays in Terraform, and it stays there for the same reason the
bootstrap does:

```hcl
metrics = { enabled = true, serviceMonitor = { enabled = true } }
```

on `controller`, `server` and `repoServer`. The controller is the interesting one: sync
status per Application, reconciliation time, OutOfSync count, failed syncs.

`metrics.enabled` creates the Service that exposes the port. `serviceMonitor.enabled`
creates the instruction telling Prometheus to scrape it. Either one alone does nothing,
which is a common source of confusion.

Community dashboard: Grafana ID **14584**.

### 3. The application — what makes this more than a deployment

`prometheus-client` in the Flask app:

| Metric | Type | Reads as |
|---|---|---|
| `predictions_total{predicted_class}` | Counter | Class mix. If the model suddenly predicts one class only, this is where it shows first. |
| `prediction_latency_seconds` | Histogram | Inference time, wrapped around `model.predict()` only — not request handling. |
| `prediction_errors_total{reason}` | Counter | `invalid_input` is a user typo, `internal` is a real failure. Sharing one series would make neither actionable. |
| `model_info{version, git_sha}` | Gauge = 1 | Ties every other metric to the build that produced it. `git_sha` is written into the Deployment by CI. |
| `prediction_input_value{feature}` | Histogram | Data drift proxy — the input distribution moving away from training data is visible here while nothing else reports an error. |

Dashboard: import `grafana-dashboards/dashboard_01.json`. The counter panels are
plotted cumulatively rather than through `rate()`, because hand-driven demo traffic is too
sparse for a rate window to show anything.

Prometheus storage is `emptyDir` with 6h retention. A persistent disk on GKE bills whether
or not the cluster runs, and there is nothing here worth keeping across a pod restart.

### Access

Everything is `ClusterIP` and reached by port-forward. Nothing is exposed except the
application itself.

```bash
# ArgoCD
kubectl port-forward svc/argocd-server -n argocd 8080:80
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d

# Grafana  (credentials set in apps/monitoring.yaml)
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80

# Prometheus
kubectl port-forward -n monitoring \
  svc/monitoring-kube-prometheus-prometheus 9090:9090
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

`config_repo_url` must match the deploy-key secret character for character. ArgoCD matches
credentials to repositories by string prefix, so `git@github.com:…` and
`https://github.com/…` are two different repositories as far as it is concerned, and a
missing `.git` suffix produces an authentication error against a repository that is
perfectly accessible.

### 2. Deploy key for the config repo

ArgoCD needs read access. Generate a key, keep the private half out of any repository:

```bash
    ssh-keygen -t ed25519 -N "" -C "argocd" -f ~/.ssh/argocd_config_repo
```

Add `~/.ssh/argocd_config_repo.pub` to the config repo under
*Settings → Deploy keys*, **without** write access. Terraform reads the private key via
`config_repo_ssh_key_path` and stores it as a Kubernetes secret.

If your config repo is public, skip this and use an `https://` URL instead.

### 3. Apply the infrastructure, then wire up GitHub

```bash
    cd terraform && terraform init && terraform apply
```

Take `github_wif_provider` and `github_actions_sa_email` from the outputs and add them to
the application repo as `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`.
Generate a fine-grained PAT scoped to the config repo with `contents: write` and add it as
`CONFIG_REPO_PAT`.

### 4. Fill the config repo

In `apps/`, place `machines.yaml` and `monitoring.yaml` — the two Applications the
root will pick up. In `k8s/`, place `deployment.yaml`, `service.yaml` and
`servicemonitor.yaml`, with the image field set to your Artifact Registry path and any
placeholder tag; CI overwrites it on the first run.

`deployment.yaml` must already contain an `env` entry named `GIT_SHA`. The `yq` expression
in the workflow updates an existing entry and silently matches nothing if the key is
absent — the image tag would be bumped while the metric kept reporting `unknown`.

`service.yaml` must carry `app:` labels in its **`metadata`**, not only in its pod
selector. A ServiceMonitor selects Services by their metadata labels; a Service without
them matches nothing and reports no error.

### 5. Train a model, then push the application repo

The image bakes in `artifacts/models/`, so the artefacts must exist and be committed:

```bash
    uv sync
    uv run python -m pipeline.training_pipeline
```

Training will refuse to write a model that falls below the accuracy threshold, so an empty
`artifacts/models/` after a run means the model was rejected — check the report it printed.

Push. The workflow builds the first image and bumps the config repo. Do this **before**
applying the second module: a sync against an empty Artifact Registry leaves the first
deployment in `ImagePullBackOff`, which is harmless but clutters the first run with an
error unrelated to the configuration.

### 6. Apply ArgoCD

```bash
    cd terraform-argocd && terraform init && terraform apply
    kubectl get applications -n argocd -w
```

Expect the chain: `root` syncs, creates `monitoring` and `machines-efficiency`, and
those pull the chart and the manifests. The stack takes a few minutes on first install.

Sync waves order the *creation* of the child Applications, not their completion — each then
runs its own reconciliation loop, so the lighter one finishes first regardless of wave. If
the `ServiceMonitor` or the `Prometheus` CR is missing after a green sync, the CRDs did not
exist when the manifest was validated; hard-refresh once they do:

```bash
    kubectl annotate application machines-efficiency -n argocd \
      argocd.argoproj.io/refresh=hard --overwrite
```

Confirm the app is actually reachable through the Service:
```bash
kubectl get svc machines-efficiency -n mlops
curl http://<EXTERNAL-IP>/health
open http://<EXTERNAL-IP>/
```

### 7. Tear down when finished

```bash
    cd terraform-argocd && terraform destroy
    cd ../terraform && terraform destroy
```

In that order — the second module reads the cluster created by the first.

---

## Notes for anyone rebuilding this

**Pin chart versions, then check them against the cluster.** ArgoCD v2.14 against
Kubernetes 1.35 fails every server-side diff with
`.status.terminatingReplicas: field not declared in schema` — its bundled schema predates
the field. The Application sits at `Unknown` while reporting `Healthy`, because health
describes the resources it manages and there are none; only the sync status tells the
truth. A chart pinned a year ago is the first thing to check when a cluster rebuild starts
failing in unfamiliar ways.

**Large CRDs need `ServerSideApply=true`.** `kube-prometheus-stack` ships CRDs past the
262 kB annotation limit that client-side apply relies on. The failure names the annotation
and says nothing about the cause.

**ArgoCD's own `ServiceMonitor`s hit the same CRD race, but the fix is different.**
`helm_release.argocd` renders its templates — including the `ServiceMonitor` for
`controller`/`server`/`repoServer` — at Terraform apply time, before the monitoring stack
has installed the CRD. The condition is false, the resource is silently skipped, and
`terraform apply` reports no drift on a second run because nothing in the release actually
changed. Unlike the machines-efficiency Application above, this is not an `Application` object,
so `kubectl annotate ... refresh=hard` does nothing here. Once the CRD exists:

    terraform apply -replace="helm_release.argocd"

forces Helm to re-render with the condition now true. A full `destroy`/`apply` reproduces
the same race rather than fixing it.

**`serviceMonitorSelectorNilUsesHelmValues: false` is not optional.** By default Prometheus
only scrapes ServiceMonitors carrying its own release label. Anything created elsewhere —
the application's, ArgoCD's — is ignored with no error and an empty target list.

**A ServiceMonitor selects a *Service*, by the labels in its `metadata`.** Not pods.

**`node_count` is per zone.** With `node_locations` set, the real node count is double what
the variable says.

**Node size is a per-node limit, not a sum.** A third small node does not help a pod that
does not fit on any single one. `e2-medium` is tight on CPU rather than memory: GKE's
per-node overhead (kube-proxy, metadata-server, fluentbit, node-local-dns) is roughly 350m,
and `kube-dns` reserves another 270m per replica, so on a two-node cluster running ArgoCD
roughly 90% of allocatable CPU is spoken for before any workload starts. Adding Prometheus
on top requires `e2-standard-2` (~6 GB allocatable per node). Changing the machine type
recreates the node pool, so decide before installing anything.

**A spot pool with a `NoSchedule` taint and `min=0` is inert** until some pod carries a
matching toleration — the autoscaler will not scale up for a pod that cannot land there.

**WIF pools survive `terraform destroy`** as soft-deleted resources for 30 days, holding
their names. Service accounts behave the same way. Rebuilding in the same project returns
`409 already exists` against an empty state, which reads as a contradiction; the fix is
`gcloud iam workload-identity-pools undelete` followed by `terraform import`, or a new ID.

**`readOnlyRootFilesystem: true` surfaces every write path.** Worth the initial friction —
afterwards you know exactly what the container touches.

**Flask binding.** `127.0.0.1` works locally *and* through `kubectl port-forward`, and
fails through a Service: port-forward tunnels to the container's own loopback, so it
exercises the one path that hides the problem. The container binds `0.0.0.0` in gunicorn's
`CMD`, which is what actually runs — the `__main__` block is local-development only.

**Terraform state is local here.** `terraform.tfstate` contains the config-repo SSH key in
the clear, so `*.tfstate*` belongs in `.gitignore`. A lost state file can be rebuilt by
import; a leaked key cannot be unleaked.
