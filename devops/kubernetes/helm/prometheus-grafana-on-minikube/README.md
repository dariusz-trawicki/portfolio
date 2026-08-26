# Setup Prometheus Monitoring on Kubernetes using Helm and Prometheus Operator

## RUN

### Minikube

```bash
minikube start --cpus 4 --memory 8192 --driver=docker
```

### Prometheus and Grafana

In diffrent terminal, run:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add stable https://charts.helm.sh/stable
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack
```

Test:

```bash
kubectl get pods -l "release=prometheus"
```

## Retrieve the Grafana password

```bash
kubectl get secret prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo
# *** output: *** 
# admin user, password (e.g.: "prom-operator")
```

## Access Grafana locally

Port-forward the Grafana pod:

```bash
export POD_NAME=$(kubectl get pod -l "app.kubernetes.io/name=grafana,app.kubernetes.io/instance=prometheus" -o name)
kubectl port-forward $POD_NAME 3000
```

Open your browser at: http://localhost:3000.

Login:
- Username: `admin`
- Password: (the one you just retrieved — for example: `prom-operator`)

## What can you find in Grafana?

Preconfigured Kubernetes dashboards, such as:

#### `Home > Dashboards > Prometheus / Overview`

  A dashboard that monitors Prometheus itself.

#### `Home > Dashboards > Kubernetes / API server`

  Displays detailed metrics for the Kubernetes API server, one of the core components of the cluster.

#### `Home > Dashboards > Kubernetes / Kubelet`

  Shows metrics for the kubelet component — the agent running on each Kubernetes node that:
- Manages pods
- Monitors container status
- Communicates with the API server
- Collects local system stats

#### `Home > Dashboards > Node Exporter / Nodes`

  Displays `node-level metrics` collected by `node-exporter`, including:
- `CPU` – usage per core, average, system/user
- `Memory` – total, free, cached, buffers
- `Disk` – IOPS, read/write usage, available space
- `Network` – inbound and outbound traffic per interface
- `Load` – load average (1m, 5m, 15m)
- `System Info` – architecture, OS, kernel, uptime

## Cleaning up

```bash
minikube delete
```
