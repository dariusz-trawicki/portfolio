# Secrets on EKS: Secrets Manager → External Secrets Operator → Pod

Terraform lab delivering a secret from AWS Secrets Manager into a Kubernetes
pod. No static credentials in the repo, the image, or the application.

---

## Architecture

```
AWS Secrets Manager
       │  GetSecretValue, every refreshInterval
       │  authenticated by an IAM role via EKS Pod Identity
       ▼
ESO controller  (pod on an EKS node)
       │  creates / updates
       ▼
Secret "orders-api-secret"  (native Kubernetes object)
       │  envFrom — read once, at process start
       ▼
orders-api pod
```

| Boundary | Crossed by | Authenticated by |
|---|---|---|
| AWS → cluster | ESO controller | IAM role, via Pod Identity |
| Secret object → pod | kubelet | namespace RBAC |
| Change in AWS → running process | nobody | — see [The rotation gap](#the-rotation-gap) |

---

## Layout

```
.
├── terraform/
│   ├── 01-cluster/     VPC, EKS, IAM role, Pod Identity association, secret
│   └── 02-apps/        ESO via Helm, SecretStore, ExternalSecret
└── app/
    └── test-app.yaml   demo workload consuming the synced Secret
```

**Two terraform states.** Provider configuration is resolved during plan. 
In a single-state layout the helm, kubernetes and kubectl providers would 
be configured before the cluster exists.

Side effect worth having: the Pod Identity association is created in stage 01,
before ESO exists. Credentials are injected at pod creation, so an association
made after a pod starts has no effect on it — splitting the stages gets the
ordering right without a `rollout restart`.

---

## Prerequisites

- Terraform ≥ 1.5, AWS CLI, `kubectl`
- IAM permissions for VPC, EKS, IAM, Secrets Manager

---

## Run

### Stage 1

```bash
cd terraform/01-cluster
terraform init
terraform apply -auto-approve      # ~15-20 min
```

```bash
aws eks update-kubeconfig --name eso-lab --region eu-central-1

kubectl get nodes                                     # 2 × Ready
kubectl get pods -n kube-system | grep pod-identity   # 2 agents, DaemonSet
```

### Stage 2

```bash
cd ../02-apps
terraform init
terraform apply -auto-approve
```

### Verify

In order — each check depends on the previous one passing.

```bash
kubectl get pods -n external-secrets
# controller, cert-controller, webhook — all Running

kubectl get secretstore aws
# STATUS: Valid

kubectl get externalsecret orders-api
# STATUS: SecretSynced, READY: True

kubectl get secret orders-api-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d; echo
```

`SecretStore: Valid` is the real assertion. It means the ESO pod reached AWS
with no static access key: agent injected credentials, trust policy accepted
them, inline policy allowed the read. Stage 01 verified in one word.

### Demo workload

```bash
kubectl apply -f ../../app/test-app.yaml
kubectl wait --for=condition=ready pod -l app=orders-api --timeout=60s
kubectl logs -f deploy/orders-api
```

---

## The rotation gap

Keep the log tailing in one terminal, run this in another.

```bash
aws secretsmanager put-secret-value \
  --secret-id eso-lab/orders-api/db \
  --secret-string '{"username":"orders_app","password":"rotated-456"}' \
  --region eu-central-1

kubectl annotate externalsecret orders-api \
  reconcile.external-secrets.io/requested-at="$(date +%s)" --overwrite
```

Any mutation of the object emits a watch event and triggers a reconcile; the
annotation value must differ from the previous one or no event is emitted.

```bash
kubectl get secret orders-api-secret -o jsonpath='{.data.DB_PASSWORD}' | base64 -d; echo
# rotated-456

kubectl logs deploy/orders-api --tail=3
# still the old value
```

Both are true simultaneously. Environment variables are set once at `exec` —
Unix semantics, not a Kubernetes quirk. ESO reconciled the Secret object with
its source and stopped there, correctly: its contract ends at etcd, not inside
consuming pods.

Nothing closes the loop unless you add something that will:

```bash
kubectl rollout restart deploy/orders-api
```

In production that job belongs to [Reloader](https://github.com/stakater/Reloader)
(watches Secrets, restarts referencing workloads), or disappears entirely with
Vault dynamic secrets, where credentials carry a short TTL and the application
is built to refresh them.

---

## Teardown

Reverse order, so no Kubernetes-created AWS resources block the VPC deletion.

```bash
cd terraform/02-apps && terraform destroy -auto-approve
cd ../01-cluster     && terraform destroy -auto-approve
```

```bash
aws eks list-clusters --region eu-central-1
aws ec2 describe-nat-gateways --region eu-central-1 --filter Name=state,Values=available
```
