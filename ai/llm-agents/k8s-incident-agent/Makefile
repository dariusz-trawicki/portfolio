# Requirements: docker (min. 8 GB RAM), kind, kubectl, helm, python 3.11+
CLUSTER   ?= incident-lab
NS        ?= otel-demo
RELEASE   ?= otel-demo
CHART_VER ?= 0.42.1
AGENT_NS    ?= incident-agent
AGENT_IMAGE ?= incident-agent:dev
# Step 5e (GitOps): ArgoCD applies the values file of a separate repository; rollbacks are PRs against it.
# (No trailing comments on the assignments below: make would keep the spaces before them in the value.)
# ARGOCD_MANIFEST: core-install.yaml has no UI/dex (lighter); install.yaml adds the web UI (~+0.7 GB).
# GITOPS_DIR: local clone of the GitOps repository. GITOPS_REPO: owner/name on GitHub, e.g. dartit/k8s-gitops-demo.
ARGOCD_VER      ?= v3.5.3
ARGOCD_MANIFEST ?= core-install.yaml
GITOPS_DIR      ?= ../k8s-gitops-demo
GITOPS_REPO     ?=
# Alertmanager sends alerts to the in-cluster agent while this marker file exists
# (make agent-up / agent-route create it, make agent-down / agent-route-host remove it).
AM_OVERLAY   = $(if $(wildcard .data/agent-in-cluster),-f infra/alertmanager-to-cluster-agent.yaml)

.PHONY: probes eval apply-values doctor up cluster demo wait port-forward stop-pf down install test graph alerts reset serve serve-dry serve-fake fire-test incidents \
	agent-image agent-secrets agent-deploy agent-route agent-route-host _am-upgrade agent-up agent-pf agent-token agent-incidents agent-logs agent-doctor agent-restart agent-down agent-purge \
	gitops-argocd gitops-bootstrap gitops-app gitops-up gitops-break gitops-down agent-gitops agent-kubectl-rollback

up: cluster demo wait   ## the whole lab from scratch: cluster + demo + wait for all deployments to be ready

cluster:
	kind create cluster --config infra/kind-config.yaml

demo:
	helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts >/dev/null 2>&1 || true
	helm repo update open-telemetry
	helm install $(RELEASE) open-telemetry/opentelemetry-demo --version $(CHART_VER) \
		-n $(NS) --create-namespace -f infra/otel-demo-values.yaml
	$(MAKE) probes

# Apply changes from infra/otel-demo-values.yaml to the running cluster (same chart version).
# Prometheus has configmap-reload disabled, so we restart it by hand
# (no PV — metric history starts from zero).
apply-values:
	@test ! -f .data/gitops-managed || { echo "ArgoCD manages the release now: change values through Git (see README step 5e), or run make gitops-down"; exit 1; }
	helm upgrade $(RELEASE) open-telemetry/opentelemetry-demo --version $(CHART_VER) \
		-n $(NS) -f infra/otel-demo-values.yaml $(AM_OVERLAY)
	kubectl -n $(NS) rollout restart deployment/prometheus
	kubectl -n $(NS) rollout status deployment/prometheus --timeout=5m
	kubectl -n $(NS) rollout restart statefulset/alertmanager
	kubectl -n $(NS) rollout status statefulset/alertmanager --timeout=5m
	$(MAKE) probes

# A probe the chart cannot express (see the comment in the patch file).
probes:
	kubectl -n $(NS) patch deployment cart --patch-file infra/cart-readiness-probe.yaml
	kubectl -n $(NS) rollout status deployment/cart --timeout=5m

wait:
	kubectl -n $(NS) wait --for=condition=Available deployment --all --timeout=15m

# Ports: 8080 shop/Grafana/Jaeger/flagd-ui, 9090 Prometheus, 9093 Alertmanager, 9200 OpenSearch, 8016 flagd OFREP
port-forward:
	mkdir -p .data
	kubectl -n $(NS) port-forward svc/frontend-proxy 8080:8080 > .data/pf-frontend.log 2>&1 &
	kubectl -n $(NS) port-forward svc/prometheus 9090:9090 > .data/pf-prom.log 2>&1 &
	kubectl -n $(NS) port-forward svc/alertmanager 9093:9093 > .data/pf-am.log 2>&1 &
	kubectl -n $(NS) port-forward svc/opensearch 9200:9200 > .data/pf-os.log 2>&1 &
	kubectl -n $(NS) port-forward svc/flagd 8016:8016 > .data/pf-flagd.log 2>&1 &
	@echo "Shop: http://localhost:8080  Grafana: http://localhost:8080/grafana  Prometheus: http://localhost:9090/alerts  Alertmanager: http://localhost:9093"

stop-pf:
	-pkill -f "kubectl -n $(NS) port-forward"

down: stop-pf
	kind delete cluster --name $(CLUSTER)

install:
	python -m venv .venv && .venv/bin/pip install -e ".[dev,tracing,postgres]"

test:
	pytest -q

graph:
	incident-agent graph

alerts:
	incident-agent alerts

reset:
	incident-agent chaos reset

doctor:
	incident-agent doctor

eval:
	incident-agent eval run $(ARGS)

# --- step 3: webhook (Alertmanager -> agent) ---
# Do not run `serve` together with `eval run`: both would investigate the same alerts (double LLM cost).
serve:                               ## webhook with the real agent (cluster + LLM)
	incident-agent serve $(ARGS)

serve-dry:                           ## webhook without LLM or cluster (checks the plumbing only)
	incident-agent serve --dry-run $(ARGS)

serve-fake:                          ## webhook with a recording instead of the cluster (LLM still billed)
	incident-agent serve --backend fake --fixture tests/fixtures/payment-unreachable-deploy.json $(ARGS)

# Sends a sample Alertmanager payload (2 alerts: checkout + its neighbour payment). A second call = duplicates.
fire-test:
	curl -sS -X POST http://localhost:8787/alertmanager -H 'Content-Type: application/json' \
		$(if $(WEBHOOK_TOKEN),-H "Authorization: Bearer $(WEBHOOK_TOKEN)") \
		--data @tests/fixtures/alertmanager-firing.json | python3 -m json.tool

incidents:
	curl -sS $(if $(WEBHOOK_TOKEN),-H "Authorization: Bearer $(WEBHOOK_TOKEN)") http://localhost:8787/incidents | python3 -m json.tool

# --- step 5d: the agent in the cluster (Postgres state, narrow RBAC, metrics in Grafana) ---
# Do not run `make serve` at the same time: both would receive the same alerts.
agent-image:                         ## build the image and load it into kind (no registry needed)
	docker build -t $(AGENT_IMAGE) .
	kind load docker-image $(AGENT_IMAGE) --name $(CLUSTER)

# Secrets never go to git. The webhook token and the Postgres password are generated once and reused;
# ANTHROPIC_API_KEY, AGENT_MODEL and AGENT_LANGUAGE come from your shell (set -a; source .env; set +a).
agent-secrets:
	@test -n "$$ANTHROPIC_API_KEY" || { echo "ANTHROPIC_API_KEY is empty - run: set -a; source .env; set +a"; exit 1; }
	kubectl apply -f deploy/k8s/00-namespace.yaml
	@TOKEN=$$(kubectl -n $(AGENT_NS) get secret incident-agent-env -o jsonpath='{.data.WEBHOOK_TOKEN}' 2>/dev/null | base64 --decode 2>/dev/null); \
	[ -n "$$TOKEN" ] || TOKEN=$$(openssl rand -hex 24); \
	kubectl -n $(AGENT_NS) create secret generic incident-agent-env \
		--from-literal=ANTHROPIC_API_KEY="$$ANTHROPIC_API_KEY" \
		--from-literal=WEBHOOK_TOKEN="$$TOKEN" \
		--from-literal=AGENT_MODEL="$${AGENT_MODEL:-anthropic:claude-sonnet-5}" \
		--from-literal=AGENT_LANGUAGE="$${AGENT_LANGUAGE:-en}" \
		--dry-run=client -o yaml | kubectl apply -f - && \
	kubectl -n $(NS) create secret generic incident-agent-webhook --from-literal=token="$$TOKEN" \
		--dry-run=client -o yaml | kubectl apply -f -
	@kubectl -n $(AGENT_NS) get secret postgres >/dev/null 2>&1 || \
		kubectl -n $(AGENT_NS) create secret generic postgres --from-literal=password=$$(openssl rand -hex 16)

agent-deploy:                        ## Postgres + RBAC + agent + Grafana dashboard
	kubectl apply -f deploy/k8s/
	kubectl -n $(NS) create configmap grafana-dashboard-incident-agent \
		--from-file=incident-agent.json=deploy/grafana/incident-agent.json --dry-run=client -o yaml \
		| kubectl label --local -f - grafana_dashboard=1 -o yaml | kubectl apply -f -
	kubectl -n $(AGENT_NS) rollout status statefulset/postgres --timeout=5m
	kubectl -n $(AGENT_NS) rollout restart deployment/incident-agent   # picks up a freshly loaded image
	kubectl -n $(AGENT_NS) rollout status deployment/incident-agent --timeout=5m

agent-route:                         ## Alertmanager -> the in-cluster agent (restarts Alertmanager only)
	mkdir -p .data && touch .data/agent-in-cluster
	$(MAKE) _am-upgrade

agent-route-host:                    ## Alertmanager -> `make serve` on your laptop again
	rm -f .data/agent-in-cluster
	$(MAKE) _am-upgrade

# Same values as apply-values, but Prometheus is not restarted (its config does not change),
# so the metric history stays.
_am-upgrade:
	@test ! -f .data/gitops-managed || { echo "ArgoCD manages the release now: change values through Git (see README step 5e), or run make gitops-down"; exit 1; }
	helm upgrade $(RELEASE) open-telemetry/opentelemetry-demo --version $(CHART_VER) \
		-n $(NS) -f infra/otel-demo-values.yaml $(AM_OVERLAY)
	kubectl -n $(NS) rollout restart statefulset/alertmanager
	kubectl -n $(NS) rollout status statefulset/alertmanager --timeout=5m
	$(MAKE) probes

agent-up: agent-image agent-secrets agent-deploy agent-route   ## all of the above, in order
	@echo "Agent running in namespace $(AGENT_NS). Approval page: make agent-pf -> http://localhost:8787/ (token: make agent-token)"

agent-pf:                            ## approval page + API of the in-cluster agent on http://localhost:8787
	kubectl -n $(AGENT_NS) port-forward svc/incident-agent 8787:8787

agent-token:                         ## the webhook token (paste it into the approval page)
	@kubectl -n $(AGENT_NS) get secret incident-agent-env -o jsonpath='{.data.WEBHOOK_TOKEN}' | base64 --decode; echo

agent-incidents:                     ## like `make incidents`, for the in-cluster agent (needs make agent-pf)
	curl -sS -H "Authorization: Bearer $$($(MAKE) -s --no-print-directory agent-token)" http://localhost:8787/incidents | python3 -m json.tool

agent-logs:
	kubectl -n $(AGENT_NS) logs deploy/incident-agent -f

agent-doctor:                        ## data sources, Postgres and RBAC, checked from inside the pod
	kubectl -n $(AGENT_NS) exec deploy/incident-agent -- incident-agent doctor

agent-restart:                       ## kill the agent pod: incidents must survive (step 5c demo)
	kubectl -n $(AGENT_NS) delete pod -l app.kubernetes.io/name=incident-agent
	kubectl -n $(AGENT_NS) rollout status deployment/incident-agent --timeout=5m

agent-down:                          ## stop the agent, keep its data (Postgres + PVC); alerts go to `make serve` again
	-kubectl -n $(AGENT_NS) delete deployment incident-agent
	$(MAKE) agent-route-host

agent-purge: agent-down              ## remove everything incl. the incident history (PVC)
	-kubectl delete namespace $(AGENT_NS)
	-kubectl -n $(NS) delete role,rolebinding incident-agent-read incident-agent-rollback
	-kubectl -n $(NS) delete secret incident-agent-webhook
	-kubectl -n $(NS) delete configmap grafana-dashboard-incident-agent

# --- step 5e: GitOps rollback (ArgoCD + a values repository; the agent opens PRs, a human merges) ---
# One-time: create an EMPTY public GitHub repo (e.g. k8s-gitops-demo), clone it to $(GITOPS_DIR), then
#   make gitops-bootstrap GITOPS_REPO=<owner>/k8s-gitops-demo   -> writes values + ArgoCD Application
#   (commit + push, protect `main`: require a pull request)
#   make gitops-up                                               -> ArgoCD takes over the otel-demo release
#   GITOPS_TOKEN=<fine-grained PAT> make agent-gitops GITOPS_REPO=<owner>/k8s-gitops-demo
gitops-argocd:                       ## install ArgoCD (checks Git every 30 s instead of 3 min)
	kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -n argocd --server-side --force-conflicts \
		-f https://raw.githubusercontent.com/argoproj/argo-cd/$(ARGOCD_VER)/manifests/$(ARGOCD_MANIFEST)
	kubectl wait --for condition=established --timeout=60s crd/appprojects.argoproj.io crd/applications.argoproj.io
	kubectl apply -f deploy/gitops/default-project.yaml     # core install has no server that would create it
	kubectl -n argocd patch configmap argocd-cm --type merge -p '{"data":{"timeout.reconciliation":"30s"}}'
	kubectl -n argocd rollout restart statefulset/argocd-application-controller deployment/argocd-repo-server
	kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=5m
	kubectl -n argocd rollout status deployment/argocd-repo-server --timeout=5m

gitops-bootstrap:                    ## write values/, argocd/application.yaml, README into $(GITOPS_DIR)
	@test -n "$(GITOPS_REPO)" || { echo "pass GITOPS_REPO=<owner>/<name>"; exit 1; }
	incident-agent gitops-bootstrap --out $(GITOPS_DIR) --repo-url https://github.com/$(GITOPS_REPO) --chart-version $(CHART_VER)

gitops-app:                          ## hand the otel-demo release to ArgoCD (it adopts the running objects)
	kubectl apply -f $(GITOPS_DIR)/argocd/application.yaml
	mkdir -p .data && touch .data/gitops-managed
	@echo "watch it: kubectl -n argocd get applications.argoproj.io otel-demo -w"

gitops-up: gitops-argocd gitops-app

# The GitOps twin of the payment-unreachable-deploy scenario: a bad PAYMENT_ADDR merged through a PR.
# Needs the GitHub CLI (gh) logged in; merges with --admin because `main` requires a pull request.
gitops-break:
	cd $(GITOPS_DIR) && git checkout -q main && git pull -q --ff-only && git checkout -q -B demo/bad-checkout
	incident-agent gitops-break --dir $(GITOPS_DIR)
	cd $(GITOPS_DIR) && git commit -qam "checkout: point PAYMENT_ADDR at payment-v2" && git push -qf -u origin demo/bad-checkout \
		&& gh pr create --fill --base main --head demo/bad-checkout \
		&& gh pr merge demo/bad-checkout --squash --admin && git checkout -q main && git pull -q --ff-only
	@echo "ArgoCD deploys it within ~30 s; the alert follows in ~5 min -> approval page -> the agent opens a revert PR"

agent-gitops:                        ## the in-cluster agent opens rollback PRs instead of running kubectl rollout undo
	@test -n "$$GITOPS_TOKEN" -a -n "$(GITOPS_REPO)" || { echo "needs GITOPS_TOKEN=<fine-grained PAT: Contents + Pull requests, this repo only> and GITOPS_REPO=<owner>/<name>"; exit 1; }
	kubectl -n $(AGENT_NS) create secret generic incident-agent-gitops --from-literal=GITOPS_TOKEN="$$GITOPS_TOKEN" \
		--dry-run=client -o yaml | kubectl apply -f -
	kubectl -n $(AGENT_NS) create configmap incident-agent-gitops --from-literal=ROLLBACK_MODE=gitops \
		--from-literal=GITOPS_REPO=$(GITOPS_REPO) --dry-run=client -o yaml | kubectl apply -f -
	kubectl -n $(AGENT_NS) rollout restart deployment/incident-agent
	kubectl -n $(AGENT_NS) rollout status deployment/incident-agent --timeout=5m
	kubectl -n $(AGENT_NS) exec deploy/incident-agent -- incident-agent doctor | grep -i gitops

agent-kubectl-rollback:              ## back to `kubectl rollout undo` (also what the eval harness uses)
	-kubectl -n $(AGENT_NS) delete configmap,secret incident-agent-gitops
	kubectl -n $(AGENT_NS) rollout restart deployment/incident-agent

gitops-down:                         ## give the release back to helm (objects stay; the Application has no finalizer)
	-kubectl -n argocd delete applications.argoproj.io otel-demo
	-kubectl delete namespace argocd
	rm -f .data/gitops-managed
