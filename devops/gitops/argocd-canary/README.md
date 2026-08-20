# argocd-canary

A demo of progressive delivery (canary) on Kubernetes with automatic rollback driven by metrics.

Stack: **kind + Argo CD + Argo Rollouts**. The manifests in this repository are the single source of truth — both deployment and rollback happen through a commit.

## What it demonstrates

A plain `Deployment` with `RollingUpdate` protects you against a version that **fails to start** — if the new pods never become `Ready`, the rollout stalls and the old pods keep serving traffic.

It does not protect you against a version that **starts correctly but behaves badly**: the readiness probe is green, the rolling update completes without a hitch, and all traffic lands on the broken version.

This demo reproduces exactly that scenario and shows how a canary with metric analysis detects the problem and aborts the rollout with no human involved.

The application is nginx with its configuration injected from a ConfigMap:

| Version | `/healthz` | `/` | Outcome |
|---|---|---|---|
| v1 | 200 | 200 `version 1` | starting state |
| v2 | 200 | 200 `version 2` | canary succeeds |
| v3 | **200** | **500** | canary aborted automatically |

The v3 row is the important one: the pod is `Ready` because `/healthz` responds correctly. A rolling update would happily roll it out in full.

## Prerequisites

- `docker` (running, with at least 2 GB of memory available)
- `kubectl`
- `kind` (or `minikube` — only section 0 changes)
- `git` and a GitHub account (`gh` optional)

Time to walk through: roughly 30 minutes.

> **Check your context before every command block.** If your kubeconfig holds production clusters, `kubectl apply -f install.yaml` will not ask whether you meant to install Argo CD there.
>
> ```bash
> kubectl config current-context
> ```
>
> Consider `kubectx` or a shell prompt plugin such as `kube-ps1` — with a long cluster list this is a safety measure, not a convenience.

## 0. Environment setup

### Cluster

```bash
kind create cluster --name canary-demo
kubectl config current-context     # expect: kind-canary-demo
kubectl get nodes                  # expect: canary-demo-control-plane Ready
```

Do not continue until the node is `Ready` — every later `kubectl` command will otherwise fail against `localhost:8080`, which is the fallback address used when no context is set.

### Argo CD

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server
```

Warnings about `unrecognized format "int64"` are harmless — `kubectl` commenting on CRD schemas, not an error.

UI access — leave this running in a separate terminal:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Initial password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d; echo
```

Open `https://localhost:8080`, user `admin`. The certificate warning is expected — Argo CD generates a self-signed one. In Chrome, if there is no "proceed anyway" link, click the page and type `thisisunsafe`.

## 1. Install Argo Rollouts

The controller:

```bash
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts \
  -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
kubectl -n argo-rollouts rollout status deploy/argo-rollouts
```

The `kubectl` plugin — makes watching the rollout far easier:

```bash
# macOS
brew install argoproj/tap/kubectl-argo-rollouts

# Linux
curl -sSL -o kubectl-argo-rollouts \
  https://github.com/argoproj/argo-rollouts/releases/latest/download/kubectl-argo-rollouts-linux-amd64
chmod +x kubectl-argo-rollouts
sudo mv kubectl-argo-rollouts /usr/local/bin/

kubectl argo rollouts version
```

Verify the CRDs landed:

```bash
kubectl get crd | grep argoproj
```

You should see `rollouts.argoproj.io`, `analysistemplates.argoproj.io` and `analysisruns.argoproj.io` next to Argo CD's `applications.argoproj.io`.

Argo CD and Argo Rollouts are installed once, imperatively. They are cluster infrastructure, not an application managed from this repo.

## 2. Repository

Target layout:

```
argocd-canary-demo/
├── README.md
├── bootstrap/
│   └── application.yaml          # applied by hand, outside the watched path
└── manifests/                    # this is what Argo CD syncs
    ├── analysis-template.yaml
    ├── config-v1.yaml
    ├── config-v2.yaml
    ├── config-v3-broken.yaml
    ├── rollout.yaml
    └── service.yaml
```

`bootstrap/` deliberately sits outside `manifests/`. If the `Application` lived inside the synced directory, the app would start managing itself — and with `prune: true` that gets messy fast.

```bash
mkdir argocd-canary-demo && cd argocd-canary-demo
git init -b main
mkdir manifests bootstrap
```

### Application configs

The version suffix in the ConfigMap name is intentional. Changing the **name** modifies the Rollout's `spec.template`, which is the only trigger for a new rollout — editing the contents under the same name would change nothing.

```bash
cat > manifests/config-v1.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config-v1
data:
  default.conf: |
    server {
      listen 80;
      location /healthz { return 200 'ok\n'; }
      location / { return 200 'version 1\n'; }
    }
EOF
```

```bash
cat > manifests/config-v2.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config-v2
data:
  default.conf: |
    server {
      listen 80;
      location /healthz { return 200 'ok\n'; }
      location / { return 200 'version 2\n'; }
    }
EOF
```

```bash
cat > manifests/config-v3-broken.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config-v3
data:
  default.conf: |
    server {
      listen 80;
      location /healthz { return 200 'ok\n'; }
      location / { return 500 'boom\n'; }
    }
EOF
```

### Services

A canary without traffic routing needs two services whose selectors the controller rewrites itself, appending a version hash. The third one (`web`) stands in for real user traffic — it hits both stable and canary pods.

```bash
cat > manifests/service.yaml <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web-stable
spec:
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web-canary
spec:
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 80
EOF
```

### AnalysisTemplate — the abort condition

The `job` provider instead of Prometheus: deterministic and dependency-free. The job fires 20 requests at the canary service and exits non-zero if more than one returns something other than 200.

```bash
cat > manifests/analysis-template.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: http-error-rate
spec:
  args:
    - name: service-name
  metrics:
    - name: error-rate
      interval: 15s
      count: 2
      failureLimit: 0
      provider:
        job:
          spec:
            backoffLimit: 0
            template:
              spec:
                restartPolicy: Never
                containers:
                  - name: check
                    image: curlimages/curl:8.8.0
                    command: [sh, -c]
                    args:
                      - |
                        fail=0
                        for i in $(seq 1 20); do
                          code=$(curl -s -o /dev/null -w '%{http_code}' \
                            http://{{args.service-name}}/)
                          [ "$code" = "200" ] || fail=$((fail+1))
                        done
                        echo "failed responses: $fail/20"
                        [ "$fail" -le 1 ]
EOF
```

`failureLimit: 0` means the first failed measurement aborts the rollout — the second job from `count: 2` never runs. `count: 2` at `interval: 15s` makes a passing analysis take about 30 seconds.

### Rollout

Pauses are set to 90 seconds so there is time to switch terminals and show the traffic split. Shorten them once you know the flow, or replace them with an indefinite gate — see section 7.

```bash
cat > manifests/rollout.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: web
spec:
  replicas: 4
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: web
  strategy:
    canary:
      canaryService: web-canary
      stableService: web-stable
      steps:
        - setWeight: 25
        - pause: {duration: 90s}
        - analysis:
            templates:
              - templateName: http-error-rate
            args:
              - name: service-name
                value: web-canary
        - setWeight: 50
        - pause: {duration: 90s}
        - setWeight: 100
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: nginx
          image: nginx:1.27-alpine
          ports:
            - containerPort: 80
          volumeMounts:
            - name: conf
              mountPath: /etc/nginx/conf.d
          readinessProbe:
            httpGet:
              path: /healthz
              port: 80
            initialDelaySeconds: 3
            periodSeconds: 5
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
      volumes:
        - name: conf
          configMap:
            name: web-config-v1
EOF
```

Note that `spec.template` is identical to what a plain `Deployment` would carry. Migrating comes down to changing `kind` and adding `strategy.canary`.

### Validate and publish

```bash
kubectl apply --dry-run=client -f manifests/ >/dev/null && echo "YAML OK"
git add .
git commit -m "Canary demo manifests"
gh repo create argocd-canary-demo --public --source=. --remote=origin --push
```

`--dry-run=client` catches YAML indentation mistakes from the heredocs before they reach the repo.

Without `gh`: create an empty repo at `https://github.com/new` (Public, no README), then `git remote add origin ...` and `git push -u origin main`.

## 3. Register the application in Argo CD

```bash
cat > bootstrap/application.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: canary-demo
  namespace: argocd
spec:
  project: default
  source:
    repoURL: $(gh repo view --json url -q .url).git
    targetRevision: main
    path: manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: demo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
EOF

git add bootstrap/ && git commit -m "Add Application manifest" && git push
```

This heredoc has **no** quotes around `EOF` so that `$(...)` is evaluated. The earlier blocks used `'EOF'` on purpose — that YAML had to land in the file verbatim.

The bootstrap — the only imperative command in the whole flow:

```bash
kubectl apply -f bootstrap/application.yaml
```

Verify:

```bash
kubectl get application canary-demo -n argocd
kubectl argo rollouts get rollout web -n demo
```

The very first rollout shows `Step: 6/6` immediately — it skips every canary step because there is no stable version to compare against yet. All four pods come up at once. Subsequent deployments take the full path.

## Helper: sending requests

Used throughout the demos. Running `kubectl exec` against an existing pod is much faster than spawning a `curl` pod per request, and it avoids the `kubectl run` output pitfalls described in troubleshooting.

```bash
POD=$(kubectl get pod -n demo -l app=web -o jsonpath='{.items[0].metadata.name}')

# 20 requests through the user-facing service
kubectl exec -n demo "$POD" -- sh -c 'for i in $(seq 1 20); do wget -qO- http://web/; done'
```

The pod is only the starting point — traffic still goes through the `web` Service, which spreads it across all pods. That is why you see a mix of versions even though you always ask from the same place.

Note that busybox `wget` prints nothing on a 500. Append `|| echo ERROR` when you expect failures:

```bash
kubectl exec -n demo "$POD" -- sh -c 'for i in $(seq 1 20); do wget -qO- http://web/ || echo ERROR; done'
```

## 4. Demo A — a canary that passes

Watch it in a separate terminal:

```bash
kubectl argo rollouts get rollout web -n demo --watch
```

Deploy:

```bash
perl -pi -e 's/web-config-v1/web-config-v2/' manifests/rollout.yaml
grep web-config manifests/rollout.yaml
git commit -am "Deploy v2" && git push
kubectl annotate application canary-demo -n argocd \
  argocd.argoproj.io/refresh=normal --overwrite
```

`perl -pi -e` behaves identically on macOS and Linux. GNU `sed -i` and BSD `sed -i ''` do not — the BSD version treats the filename as a backup suffix and fails with `invalid command code m`.

Argo CD polls the repo roughly every 3 minutes; the annotation forces a refresh immediately.

What happens:

1. A new ReplicaSet appears with **one** canary pod (25% of 4 replicas); the stable set scales down to 3.
2. A 90-second pause — use it to run the request loop below.
3. The `AnalysisRun` starts and two Jobs run 15 seconds apart. Metric status: `Running` → `Successful`.
4. `setWeight: 50` — two canary pods, two stable.
5. Another pause, then `setWeight: 100` and full cutover.

During the first pause, from a third terminal:

```bash
POD=$(kubectl get pod -n demo -l app=web -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n demo "$POD" -- sh -c 'for i in $(seq 1 20); do wget -qO- http://web/; done'
```

A mix of `version 1` and `version 2` in roughly a 3:1 ratio — the split is done by pod count, with no service mesh involved.

Comparing the three services makes the mechanism explicit:

```bash
kubectl exec -n demo "$POD" -- sh -c 'for i in $(seq 1 5); do wget -qO- http://web-canary/; done'
kubectl exec -n demo "$POD" -- sh -c 'for i in $(seq 1 5); do wget -qO- http://web-stable/; done'
```

The first returns only the new version, the second only the old one. This is where the analysis gets its data — it queries the pure canary, not the mix.

Inspect the analysis afterwards:

```bash
kubectl get analysisrun -n demo
kubectl logs -n demo job/$(kubectl get job -n demo -o jsonpath='{.items[-1:].metadata.name}')
```

Expect `failed responses: 0/20`.

## 5. Demo B — automatic abort

This is the point of the whole demo.

```bash
perl -pi -e 's/web-config-v2/web-config-v3/' manifests/rollout.yaml
grep web-config manifests/rollout.yaml
git commit -am "Deploy v3 (broken)" && git push
kubectl annotate application canary-demo -n argocd \
  argocd.argoproj.io/refresh=normal --overwrite
```

No need to rush here — the rollout freezes in the aborted state, so nothing is missed.

What happens:

1. The canary pod starts and reaches **`Ready`** — `/healthz` returns 200. A rolling update would have considered the deployment finished at this point.
2. The pause. During it, roughly 25% of user traffic gets a 500. That is the price of a canary: not zero errors, but errors confined to a slice of traffic and time.
3. The analysis hits `web-canary`, counts 20 failures out of 20, and the Job exits with code 1.
4. The metric goes `Failed`, and so does the `AnalysisRun`. Only one Job appears, not two — `failureLimit: 0` stops at the first bad measurement.
5. The Rollout moves to `Degraded` with reason `RolloutAborted`. The canary pod is removed and the stable ReplicaSet returns to 4 replicas.

```bash
kubectl argo rollouts get rollout web -n demo
kubectl get analysisrun -n demo
kubectl logs -n demo job/$(kubectl get job -n demo -o jsonpath='{.items[-1:].metadata.name}')
kubectl describe rollout web -n demo | tail -20
```

Expect `failed responses: 20/20`.

Confirm users are being served correctly again:

```bash
kubectl exec -n demo "$POD" -- sh -c 'wget -qO- http://web/'
```

Nobody clicked a button. The metrics made the call.

## 6. Abort versus GitOps

After the abort, Argo CD reports the application as `Synced` (the cluster holds exactly what the repo describes — a Rollout pointing at `web-config-v3`) and `Degraded` at the same time (the application is not healthy). These are two independent statuses: `Synced` answers "does the cluster match the repo", `Healthy/Degraded` answers "does the application work". Argo CD owns the first, Kubernetes and Rollouts own the second.

The Rollout stays frozen and will not retry until `spec.template` changes — deliberately, since repeating a bad deployment helps nobody.

Two ways out. Show both in this order; the contrast is the most memorable part of the demo.

### The imperative path

```bash
kubectl argo rollouts undo web -n demo
kubectl get application canary-demo -n argocd -w
```

`undo` copies `spec.template` from the previous revision into the live object, so the Rollout unfreezes and deploys the good version. But the repo still holds v3, so Argo CD sees drift and — with `selfHeal: true` — restores it. You will watch `Synced` → `OutOfSync` → `Synced`, the Rollout return to v3, and abort a second time.

That is "the repo is the single source of truth" made tangible: a manual change is not so much forbidden as temporary.

### The GitOps path

```bash
git revert --no-edit HEAD
git push
kubectl annotate application canary-demo -n argocd \
  argocd.argoproj.io/refresh=normal --overwrite
```

The repo returns to v2, Argo CD syncs, the Rollout deploys through the canary path, the analysis passes, and the application ends up `Healthy` and `Synced` at once. `git log` records both the deployment and its rollback.

`undo` is not useless — it is the right tool when production is burning and the revert commit follows a minute later. Teams with strict GitOps often disable `selfHeal` precisely so that an emergency intervention is not immediately undone by the controller.

## 7. Manual promotion variant

Replacing the timed pause with an empty one gives you a canary with a human in the loop:

```yaml
      steps:
        - setWeight: 25
        - pause: {}          # waits indefinitely for a decision
        - analysis:
        ...
```

`pause: {}` is valid YAML — an empty map, meaning "a pause with no duration". The Rollout enters `Paused` and stays there indefinitely; there is no timeout.

```bash
perl -pi -e 's/- pause: \{duration: 90s\}/- pause: {}/' manifests/rollout.yaml
grep -n pause manifests/rollout.yaml
git commit -am "Switch to manual promotion" && git push
```

The pattern occurs twice — before and after the analysis — and the substitution replaces both. Edit the file by hand if you want only one gate.

**This commit alone deploys nothing.** It changes `spec.strategy`, and only a change to `spec.template` triggers a rollout. A second commit is needed:

```bash
perl -pi -e 's/web-config-v2/web-config-v1/' manifests/rollout.yaml
git commit -am "Deploy v1 with manual gate" && git push
kubectl annotate application canary-demo -n argocd \
  argocd.argoproj.io/refresh=normal --overwrite
```

Now the Rollout stops at `Status: ॥ Paused`, `Message: CanaryPauseStep`, `Step: 1/6`, `ActualWeight: 25` — and waits. Take as long as you need with the request loop, then:

```bash
kubectl argo rollouts promote web -n demo         # advance one step
kubectl argo rollouts promote web -n demo --full  # skip all remaining steps, including analysis
kubectl argo rollouts abort web -n demo           # roll back to stable
```

Prefer plain `promote` in a demo so the analysis actually runs.

This variant is worth showing as a contrast: without trustworthy metrics, a canary degenerates into "wait, then click", which buys little over a rolling update — the human has to be present, know what to look at, and react faster than users complain.

## 8. Dashboard (optional)

```bash
kubectl argo rollouts dashboard -n demo
```

Opens `localhost:3100` with a visualisation of steps, weights and analysis results. Handy when presenting.

## 9. What this demo does not show

**The traffic split is approximate.** Without traffic routing, `setWeight: 25` means "a quarter of the pods", not "a quarter of the requests". With `replicas: 4` and `setWeight: 10` you still get 25%. Production setups add `trafficRouting` (NGINX Ingress, Istio, ALB, Gateway API), where the weight is enforced per request.

**Analysis should read production metrics, not generate its own.** A Job polling the service is synthetic. The real version queries what actual users experience:

```yaml
  metrics:
    - name: success-rate
      interval: 1m
      count: 5
      successCondition: result[0] >= 0.99
      failureLimit: 1
      provider:
        prometheus:
          address: http://prometheus.monitoring.svc:9090
          query: |
            sum(rate(http_requests_total{service="web",status!~"5.."}[2m]))
            /
            sum(rate(http_requests_total{service="web"}[2m]))
```

Without exposed application metrics and a Prometheus to scrape them, this block has nothing to compute from. Progressive delivery is a layer on top of observability, not a substitute for it.

**The steps are still too fast.** Even 90 seconds is a demo figure. In production the first step usually runs for ten minutes or more, so that metrics have time to become statistically meaningful.

## 10. Cleanup

```bash
kind delete cluster --name canary-demo
```

The repo alone, without the cluster:

```bash
gh repo delete argocd-canary-demo --yes
```
