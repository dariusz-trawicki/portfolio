#!/usr/bin/env bash
set -euo pipefail

CLUSTER=iris
REG_NAME=kind-registry
REG_PORT=5001

# --- local image registry ---
if [ "$(docker inspect -f '{{.State.Running}}' "${REG_NAME}" 2>/dev/null || true)" != 'true' ]; then
  docker run -d --restart=always -p "127.0.0.1:${REG_PORT}:5000" \
    --name "${REG_NAME}" registry:2
fi

# --- cluster ---
if ! kind get clusters | grep -qx "${CLUSTER}"; then
  kind create cluster --config "$(dirname "$0")/kind-cluster.yaml"
fi

# --- configure nodes so they can see the registry ---
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${REG_PORT}"
for node in $(kind get nodes --name "${CLUSTER}"); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  echo "[host.\"http://${REG_NAME}:5000\"]" \
    | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
done

docker network connect kind "${REG_NAME}" 2>/dev/null || true

# --- ingress-nginx ---
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl -n ingress-nginx wait --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller --timeout=180s

echo "Cluster ready. Registry: localhost:${REG_PORT}"

echo "==> metrics-server (required by HPA)"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl -n kube-system patch deploy metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
kubectl -n kube-system rollout status deploy/metrics-server --timeout=120s
