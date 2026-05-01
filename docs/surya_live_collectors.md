# Surya: Live Discovery And Collector Engine

## Mission

Own the live data plane of Kovalent: Kubernetes API discovery, Prometheus/Loki query expansion, collector reliability, and demo fault scenarios that prove Kovalent can understand real pod behavior.

The goal is to make Kovalent work on Minikube, K3s, MicroK8s, and other single-node Kubernetes environments with graceful fallbacks.

## Owned Paths

- `backend/app/collectors/`
- `backend/app/config.py`
- `backend/tests/test_live_collector.py`
- Future collector tests:
  - `backend/tests/test_kubernetes_collector.py`
  - `backend/tests/test_log_patterns.py`
  - `backend/tests/test_prometheus_queries.py`
- Demo manifests or scripts:
  - `demo/`
  - `k8s/`
  - `scripts/`

## Core Deliverables

### 1. Kubernetes API Collector

Build a collector that discovers:

- Pods across all namespaces.
- Namespaces.
- Pod owners:
  - Deployment.
  - ReplicaSet.
  - StatefulSet.
  - DaemonSet.
  - Job.
- Node placement.
- PVC mounts per pod.
- Kubernetes events.
- Restart count.
- Restart reason.
- Last termination reason.
- Waiting reason.
- OOMKilled signals.

The collector should work inside a cluster and from local kubeconfig when possible.

### 2. Prometheus Collector Expansion

Expand live metrics for:

- CPU usage.
- CPU limits and requests.
- CPU throttling if available.
- Memory working set.
- Memory limits and requests.
- Network RX/TX.
- Network packet drops if available.
- PVC read throughput.
- PVC write throughput.
- PVC latency.
- PVC IOPS.
- Restart counts.

### 3. Loki Collector Expansion

Improve log intelligence:

- Error count per pod.
- Top repeated error signatures.
- First-seen timestamp.
- Last-seen timestamp.
- Stack trace grouping.
- Repeated message grouping.

Suggested error keywords:

```text
error
exception
panic
failed
timeout
oom
out of memory
connection refused
5xx
```

### 4. Collector Reliability

Every optional source should fail gracefully.

Required behavior:

- If Kubernetes API is unavailable, Prometheus/Loki collection should still work.
- If Loki is unavailable, metrics collection should still work.
- If optional Prometheus queries fail, required metrics should still work.
- If Prometheus is unavailable in live mode, fallback behavior should be clear.
- All collector errors should be converted into useful status information, not silent failure.

### 5. Demo Fault Scenarios

Create demo workloads that generate signals:

- CPU spike pod.
- Memory leak pod.
- PVC write stress pod.
- CrashLoop/restart pod.
- Noisy log/error pod.
- Multi-service cascading failure scenario.

Suggested files:

```text
demo/
  cpu-spike.yaml
  memory-leak.yaml
  pvc-stress.yaml
  crashloop.yaml
  noisy-errors.yaml
  cascading-failure.yaml
```

### 6. Collector Tests

Add tests for:

- Kubernetes payload parsing.
- Prometheus vector mapping.
- Loki log signature extraction.
- Graceful failure behavior.
- Fallback behavior.

## Suggested Backend Structure

```text
backend/app/collectors/
  mock_collector.py
  prometheus_collector.py
  kubernetes_collector.py
  log_pattern_collector.py
  collector_types.py
```

## First Tasks

1. Create `backend/app/collectors/kubernetes_collector.py`.
2. Add config for Kubernetes discovery mode.
3. Implement pod, namespace, owner, PVC, node, and event discovery.
4. Add `backend/tests/test_kubernetes_collector.py`.
5. Add demo YAML for CPU spike and crashloop.
6. Expand Prometheus query coverage for CPU throttling and PVC throughput.

## Acceptance Criteria

- Live mode can discover pods across namespaces on Minikube/K3s/MicroK8s.
- Collector failures do not crash the whole API unless fallback is disabled.
- Demo fault workloads generate visible signals in Kovalent.
- Tests pass with `.venv/bin/python -m pytest -q`.
