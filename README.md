# Kovalent

> Transforming Kubernetes observability into intelligent decision-making.

Kovalent is an **Agentic AI Kubernetes Observability Platform**. It reads real pod telemetry from Prometheus and Loki, streams anomalies via Kafka (Redpanda), and uses a Google Gemini-powered orchestrator to automatically generate root-cause analyses and interactive remediation runbooks.

The project supports two modes:

- `demo`: uses built-in mock telemetry so the UI works without Kubernetes.
- `live`: reads real Kubernetes metrics from Prometheus and real logs from Loki.

## What Works Now

- FastAPI backend & React/D3 frontend.
- **Agentic Telemetry:** Live Prometheus/Loki collectors that stream raw resource data (CPU, memory, PVC, IO, network) to specialized analytical Python agents.
- **Causal Intelligence:** Built-in **Granger Causality Engine** that automatically ranks root-cause candidates and visualizes propagation chains across the cluster topology.
- **AI-Powered Chat:** Real-time conversational interface that uses **RAG (Retrieval-Augmented Generation)** to combine live cluster state with historical incident data for deep-dive analysis.
- **LLM Orchestration:** Google Gemini 2.0/1.5 integration that synthesizes agent findings into high-level executive reports and automated CLI runbooks.
- **RAG Memory:** A local vector database (NumPy + Gemini Embeddings) that historically validates incidents and provides context for AI chat.
- **Dynamic Cluster Analytics:** Real-time aggregate telemetry (Aggregate CPU, Throughput, Anomaly Rate) derived from live data streams.
- **Interactive Remediation:** Execute `kubectl` CLI runbooks directly from the UI to auto-resolve incidents.

## Project Structure

```text
backend/
  app/
    agents/                    Resource-specific analysis agents
    collectors/
      mock_collector.py         Demo telemetry
      prometheus_collector.py   Live Prometheus/Loki collector
      kafka_producer.py         Event streaming publisher
    services/
      insight_service.py        Snapshot orchestration
      orchestrator.py           Central AI workflow engine
      llm_client.py             Google Gemini AI integration
      memory_service.py         Vector DB for RAG
      live_graph.py             NetworkX dependency mapping
    config.py                   Environment configuration
    correlation.py              Root-cause correlation engine
    main.py                     FastAPI app and routes
  tests/
frontend/
  src/
    main.jsx                    Dashboard
    styles.css                  Dashboard styling
docker-compose.yml
```

## Requirements

For demo mode:

- Python 3.11+
- Node.js 20+
- npm

For live Kubernetes mode:

- Docker Desktop
- kubectl
- Minikube
- Helm
- Prometheus stack installed in the cluster
- Loki + Promtail installed in the cluster

## Install Tools

### Windows

Run PowerShell as Administrator.

Install Chocolatey if you do not already have it:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

Install required tools:

```powershell
choco install python nodejs-lts docker-desktop kubernetes-cli minikube kubernetes-helm -y
```

Close and reopen PowerShell, then verify:

```powershell
python --version
node --version
npm --version
docker --version
kubectl version --client
minikube version
helm version
```

Start Docker Desktop before running Minikube.

### macOS

Install Homebrew if needed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Install required tools:

```bash
brew install python node kubectl minikube helm
brew install --cask docker
```

Open Docker Desktop once, then verify:

```bash
python3 --version
node --version
npm --version
docker --version
kubectl version --client
minikube version
helm version
```

## Run In Demo Mode

Use this first if you only want to verify the app.

### 1. Backend

Windows PowerShell:

```powershell
cd D:\Kovalent\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

macOS/Linux:

```bash
cd /path/to/Kovalent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

Check:

```text
http://127.0.0.1:8000/api/status
http://127.0.0.1:8000/api/snapshot
```

In demo mode, `/api/snapshot` should show:

```json
"source": "demo"
```

### 2. Frontend

Windows/macOS:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

```text
http://127.0.0.1:5173
```

If the backend is not reachable, the frontend uses built-in browser demo data.

## Run In Live Kubernetes Mode

These steps create a local Minikube cluster, install Prometheus and Loki, then point Kovalent at real telemetry.

### 1. Start Minikube

Windows/macOS:

```bash
minikube start
kubectl get nodes
```

Expected:

```text
minikube   Ready
```

If `kubectl` has a version warning, this is usually fine for local testing. You can also use:

```bash
minikube kubectl -- get pods -A
```

### 2. Install Prometheus Stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace monitoring
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack --namespace monitoring
```

Wait until Prometheus and kube-state-metrics are running:

```bash
kubectl get pods -n monitoring
```

Important pods:

```text
prometheus-kube-prometheus-stack-prometheus-0
kube-prometheus-stack-kube-state-metrics-...
kube-prometheus-stack-operator-...
kube-prometheus-stack-prometheus-node-exporter-...
```

The Grafana pod may crash if Loki chart provisioning also marks a datasource as default. Kovalent does not require Grafana, so Prometheus and Loki being ready is enough.

### 3. Install Loki + Promtail

```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install loki grafana/loki-stack --namespace monitoring --set promtail.enabled=true
```

Wait:

```bash
kubectl get pods -n monitoring
```

Important pods:

```text
loki-0
loki-promtail-...
```

### 4. Port-Forward Prometheus and Loki

Keep these commands running in separate terminals.

Prometheus:

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090
```

Loki:

```bash
kubectl -n monitoring port-forward svc/loki 3100:3100
```

Verify Prometheus:

```text
http://127.0.0.1:9090/-/ready
```

Verify Loki:

```text
http://127.0.0.1:3100/ready
```

Prometheus should say ready. Loki should return `ready`.

### 5. Confirm Prometheus Has Pod Metrics

Open Prometheus:

```text
http://127.0.0.1:9090
```

Try these queries:

```promql
container_cpu_usage_seconds_total
container_memory_working_set_bytes
kube_pod_info
kube_pod_container_resource_limits
kube_pod_container_resource_requests
```

At least `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`, and `kube_pod_info` should return results with `namespace` and `pod` labels.

### 6. Start Backend In Live Mode

Stop any old backend process first. This matters because an old demo-mode backend on port `8000` will keep serving mock data.

Windows PowerShell:

```powershell
$pid8000 = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -First 1
if ($pid8000) { Stop-Process -Id $pid8000 -Force }
```

macOS/Linux:

```bash
lsof -ti tcp:8000 | xargs kill -9
```

Start live backend.

Windows PowerShell:

```powershell
cd D:\Kovalent\backend
.\.venv\Scripts\Activate.ps1

$env:KOVALENT_MODE="live"
$env:PROMETHEUS_URL="http://127.0.0.1:9090"
$env:LOKI_URL="http://127.0.0.1:3100"
$env:KOVALENT_NAMESPACE_REGEX=".+"
$env:KOVALENT_LIVE_FALLBACK="false"

uvicorn app.main:app --reload
```

macOS/Linux:

```bash
cd /path/to/Kovalent/backend
source .venv/bin/activate

export KOVALENT_MODE=live
export PROMETHEUS_URL=http://127.0.0.1:9090
export LOKI_URL=http://127.0.0.1:3100
export KOVALENT_NAMESPACE_REGEX=.+
export KOVALENT_LIVE_FALLBACK=false

uvicorn app.main:app --reload
```

Verify:

```text
http://127.0.0.1:8000/api/status
```

Expected:

```json
{
  "mode": "live",
  "prometheus_url": "http://127.0.0.1:9090",
  "loki_configured": true,
  "namespace_regex": ".+",
  "live_fallback_enabled": false
}
```

Then open:

```text
http://127.0.0.1:8000/api/snapshot
```

Expected:

```json
"source": "live"
```

You should see real pods such as `coredns`, `kube-apiserver-minikube`, `loki`, `prometheus`, or workloads you deploy.

### 7. Start Frontend

Windows/macOS:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The status pill should show:

```text
Live telemetry
```

If it shows demo pods such as `checkout-api-7d9f`, `orders-db-0`, or `frontend-5c6b`, refresh the browser and confirm the backend was restarted in live mode.

## Generate Real Test Workload

The monitoring stack itself produces real pod data, but you can deploy a test app to make the dashboard easier to read.

```bash
kubectl create namespace kovalent-demo
kubectl create deployment nginx-demo --image=nginx --replicas=2 -n kovalent-demo
kubectl expose deployment nginx-demo --port=80 --target-port=80 -n kovalent-demo
```

Generate traffic:

```bash
kubectl run load-generator --image=busybox -n kovalent-demo --restart=Never -- /bin/sh -c "while true; do wget -q -O- http://nginx-demo.kovalent-demo.svc.cluster.local; sleep 0.2; done"
```

Restrict Kovalent to that namespace.

Windows PowerShell:

```powershell
$env:KOVALENT_NAMESPACE_REGEX="kovalent-demo"
uvicorn app.main:app --reload
```

macOS/Linux:

```bash
export KOVALENT_NAMESPACE_REGEX=kovalent-demo
uvicorn app.main:app --reload
```

## Optional Dependency Mapping

Kovalent can draw service-to-service edges if you provide a JSON dependency map.

Windows PowerShell:

```powershell
$env:KOVALENT_DEPENDENCIES='{"frontend":["checkout-api","auth-api"],"checkout-api":["orders-db"]}'
```

macOS/Linux:

```bash
export KOVALENT_DEPENDENCIES='{"frontend":["checkout-api","auth-api"],"checkout-api":["orders-db"]}'
```

If not provided, Kovalent still shows service-to-pod and pod-to-PVC relationships.

## API Endpoints

```text
GET /health
GET /api/status
GET /api/snapshot
GET /api/insights
GET /api/topology
```

`/api/snapshot` includes:

- `source`: `demo`, `live`, or `live-fallback`
- `metrics`: pod resource telemetry
- `findings`: agent-level findings
- `insights`: correlated root-cause insights
- `topology`: graph nodes and edges

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `KOVALENT_MODE` | `demo` | Use `demo` or `live`. |
| `PROMETHEUS_URL` | `http://localhost:9090` | Prometheus HTTP API base URL. |
| `LOKI_URL` | empty | Loki HTTP API base URL. |
| `KOVALENT_NAMESPACE_REGEX` | `.+` | Namespace regex used in Prometheus/Loki queries. |
| `KOVALENT_LIVE_FALLBACK` | `true` | If `true`, failed live collection returns demo data. |
| `GOOGLE_API_KEY` | empty | Gemini API key for LLM orchestration and embeddings. |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL for fast report caching. |
| `KAFKA_BOOTSTRAP_SERVERS`| `localhost:19092` | Redpanda broker for event streaming. |

## Docker Compose

Docker Compose runs the Kovalent backend, frontend, Redis cache, and Redpanda Kafka broker.

```bash
docker compose up --build
```

Backend:

```text
http://127.0.0.1:8000
```

Frontend:

```text
http://127.0.0.1:5173
```

For live mode with Compose, ensure Prometheus/Loki are reachable from the backend container. On Docker Desktop, use `host.docker.internal`:

```yaml
environment:
  KOVALENT_MODE: live
  PROMETHEUS_URL: http://host.docker.internal:9090
  LOKI_URL: http://host.docker.internal:3100
  KOVALENT_LIVE_FALLBACK: "false"
```

## Testing

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm run build
```

## Troubleshooting

### Dashboard Says Live Telemetry But Shows Demo Pods

Demo pod names include:

```text
checkout-api-7d9f
orders-db-0
frontend-5c6b
auth-api-86b4
```

Fix:

1. Stop the old backend process on port `8000`.
2. Restart backend with `KOVALENT_MODE=live`.
3. Set `KOVALENT_LIVE_FALLBACK=false`.
4. Refresh the browser.
5. Check `/api/snapshot` and confirm `"source": "live"`.

### `/api/status` Returns 404

You are running an old backend process. Stop the process on port `8000` and restart from the current repository.

### Port-Forward Fails With Pod Not Running

Wait until Prometheus is ready:

```bash
kubectl get pods -n monitoring
```

Then retry:

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090
```

### Loki Returns 503

Loki can take a minute to become ready. Check:

```bash
kubectl get pods -n monitoring
kubectl logs loki-0 -n monitoring --tail=50
```

### Grafana CrashLoopBackOff

Kovalent does not need Grafana. If Prometheus and Loki are running, you can continue.

### No PVC Latency

PVC latency depends on filesystem metrics being exposed with pod labels. CPU, memory, network, and restart data should appear first. PVC data may be `0 ms` or `none` on simple workloads.

## Current Limitations

- Service-to-service dependencies currently rely primarily on explicit configuration or basic Kubernetes ownership (Pods -> PVCs). Deep eBPF-level dependency mapping is not yet implemented.
- PVC latency is inferred from cAdvisor filesystem counters and depends on metric availability.
- Executing remediation commands requires the backend Docker container to have native `kubectl` access to the host cluster.
- Grafana is not required or integrated into the Kovalent UI.

