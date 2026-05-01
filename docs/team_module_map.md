# Kovalent Team Module Map

## Product North Star

Kovalent is not a basic Kubernetes monitoring dashboard. It is an AI-native pod intelligence system for single-node and edge Kubernetes environments.

Core promise:

> Discover pod behavior in real time, map dependencies, detect cross-resource anomalies, and explain root cause with evidence.

The project should be built as modular layers so each teammate can work independently while sharing stable contracts.

## System Modules

```text
Kubernetes / K3s / MicroK8s / Minikube
        |
        v
Collectors
Prometheus, Loki, Kubernetes API, future OpenTelemetry
        |
        v
Signal Normalizer
canonical pod, service, PVC, namespace, node, log, event records
        |
        v
Agent Engine
CPU, Memory, Storage/PVC, Network, Restart/Event, Log/IO
        |
        v
Resource Influence Graph
pod/service/PVC dependency graph with anomaly-aware edge weights
        |
        v
RCA + LLM Insight Layer
ranked root cause, evidence, confidence, recommended actions
        |
        v
Enterprise Dashboard
topology, timeline, evidence drawer, workload table, incident view
```

## Ownership

### Akhil: Frontend And Dashboard Framework

Primary goal:

Build the full frontend framework so the product looks and feels like an enterprise observability platform, not a hackathon demo.

Owned paths:

- `frontend/src/main.jsx`
- `frontend/src/styles.css`
- future frontend component folders:
  - `frontend/src/components/`
  - `frontend/src/views/`
  - `frontend/src/api/`
  - `frontend/src/lib/`

Deliverables:

1. App shell
   - Header with cluster/source status.
   - Left navigation or compact tab system.
   - Main views: Overview, Topology, Incidents, Workloads, Evidence.
   - Responsive desktop-first layout.

2. Dashboard views
   - Overview summary cards.
   - Resource signal table.
   - Dependency topology graph.
   - Incident detail drawer.
   - Timeline for anomalies and restarts.

3. Frontend API layer
   - Create a single API client module instead of fetch calls scattered in components.
   - Handle loading, error, fallback, and refresh states consistently.

4. Enterprise UX requirements
   - No landing-page style hero sections.
   - Dense, useful operational UI.
   - Every insight must show evidence, severity, affected services, and timestamp.
   - Empty states should be professional and actionable.
   - The dashboard must remain useful on demo data and live data.

Stable backend endpoints to consume:

- `GET /api/status`
- `GET /api/snapshot`
- `GET /api/insights`
- `GET /api/topology`

Future endpoints Akhil should design UI for:

- `GET /api/incidents`
- `GET /api/workloads`
- `GET /api/evidence/{incident_id}`
- `GET /api/graph`

Suggested frontend structure:

```text
frontend/src/
  api/
    client.js
    snapshot.js
  components/
    AppShell.jsx
    StatusPill.jsx
    MetricTile.jsx
    ResourceTable.jsx
    TopologyGraph.jsx
    IncidentList.jsx
    EvidenceDrawer.jsx
    AnomalyTimeline.jsx
  views/
    OverviewView.jsx
    TopologyView.jsx
    IncidentsView.jsx
    WorkloadsView.jsx
  lib/
    formatters.js
    severity.js
```

Acceptance criteria:

- `npm run build` passes.
- UI works when backend is unavailable by showing demo fallback.
- Topology node click opens useful details.
- Incident view can render from current `snapshot.insights`.
- No text overlap on mobile or desktop.

### Yashwanth: Intelligence Architecture And RCA Engine

Primary goal:

Own the core intelligence architecture: canonical models, API contracts, multi-agent analysis flow, Resource Influence Graph, root-cause ranking, and LLM-ready evidence generation.

Owned paths:

- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/services/`
- `backend/app/agents/`
- `backend/app/correlation.py`
- `backend/tests/`

Deliverables:

1. Canonical intelligence models
   - `AnalysisContext`
   - `Anomaly`
   - `EvidenceItem`
   - `Incident`
   - `Recommendation`
   - `DependencyEdge`
   - `WorkloadIdentity`

2. Incident API
   - `GET /api/incidents`
   - `GET /api/incidents/{incident_id}`
   - `GET /api/evidence/{incident_id}`
   - Convert current `Insight` objects into richer incident objects.

3. Resource Influence Graph
   - Build graph nodes for services, pods, PVCs, namespaces, and node.
   - Build graph edges for `owns`, `mounts`, `calls`, `co_located`, `correlated_with`, and `temporal_influence`.
   - Add score fields on edges so the UI can explain why two workloads are related.

4. RCA scoring engine
   - Rank root-cause candidates instead of only listing threshold findings.
   - Use anomaly strength, dependency centrality, temporal precedence, blast radius, and recurrence.
   - Every incident should include a confidence score.

5. LLM insight interface
   - Create an LLM-ready structured JSON payload.
   - Keep the actual detection deterministic.
   - Let the LLM explain, summarize, and recommend.
   - Never allow automatic destructive remediation.

6. Backend tests
   - Tests for incident conversion.
   - Tests for graph generation.
   - Tests for RCA scoring.
   - Tests for LLM prompt payload shape.

Suggested backend structure for Yashwanth:

```text
backend/app/
  services/
    insight_service.py
    incident_service.py
    graph_service.py
    llm_insight_service.py
  agents/
    cpu.py
    memory.py
    storage.py
    log_io.py
    network.py
    restart.py
    baseline.py
  correlation.py
  models.py
```

Acceptance criteria:

- Current `/api/snapshot` remains compatible with Akhil's UI.
- New `/api/incidents` returns structured, evidence-backed incidents.
- Each incident has title, severity, root cause candidate, confidence, affected services, evidence, and recommendations.
- RCA logic works on demo data without live Kubernetes.
- Backend tests pass with `.venv/bin/python -m pytest -q`.

### Surya: Live Discovery And Collector Engine

Primary goal:

Own the live data plane: Kubernetes API discovery, Prometheus/Loki query expansion, collector reliability, and demo fault scenarios that prove Kovalent can understand real pod behavior.

Owned paths:

- `backend/app/collectors/`
- `backend/app/config.py`
- `backend/tests/test_live_collector.py`
- future collector tests:
  - `backend/tests/test_kubernetes_collector.py`
  - `backend/tests/test_log_patterns.py`
  - `backend/tests/test_prometheus_queries.py`
- demo manifests or scripts:
  - `demo/`
  - `k8s/`
  - `scripts/`

Deliverables:

1. Kubernetes API collector
   - Discover pods across all namespaces.
   - Discover namespaces.
   - Discover pod owners: Deployment, ReplicaSet, StatefulSet, DaemonSet, Job.
   - Discover node placement.
   - Discover PVC mounts per pod.
   - Discover Kubernetes events.
   - Extract restart reason, last termination reason, waiting reason, and OOMKilled signals.

2. Prometheus collector expansion
   - CPU usage.
   - CPU limits and requests.
   - CPU throttling if available.
   - Memory working set.
   - Memory limits and requests.
   - Network RX/TX.
   - Network packet drops if available.
   - PVC read/write throughput.
   - PVC latency.
   - PVC IOPS.
   - Restart counts.

3. Loki collector expansion
   - Error count per pod.
   - Top repeated error signatures.
   - First-seen and last-seen timestamps.
   - Log pattern grouping for stack traces and repeated messages.

4. Collector reliability
   - Every optional source should fail gracefully.
   - If Kubernetes API is unavailable, Prometheus/Loki collection should still work.
   - If Loki is unavailable, metrics collection should still work.
   - If Prometheus is unavailable in live mode, fallback behavior should be clear.

5. Demo fault scenarios
   - CPU spike pod.
   - Memory leak pod.
   - PVC write stress pod.
   - CrashLoop/restart pod.
   - Noisy log/error pod.
   - Multi-service cascading failure scenario.

6. Collector tests
   - Unit tests for Kubernetes payload parsing.
   - Unit tests for Prometheus vector mapping.
   - Unit tests for Loki log signature extraction.
   - Tests for graceful failure and fallback.

Suggested backend structure for Surya:

```text
backend/app/collectors/
  mock_collector.py
  prometheus_collector.py
  kubernetes_collector.py
  log_pattern_collector.py
  collector_types.py

demo/
  cpu-spike.yaml
  memory-leak.yaml
  pvc-stress.yaml
  crashloop.yaml
  noisy-errors.yaml
```

Acceptance criteria:

- Live mode can discover pods across namespaces on Minikube/K3s/MicroK8s.
- Collector failures do not crash the whole API unless fallback is disabled.
- Demo fault workloads generate visible signals in Kovalent.
- Tests pass with `.venv/bin/python -m pytest -q`.

## Backend Module Plan

### Module 1: Canonical Data Models

Goal:

Create models that can support industry-level observability, not only current demo fields.

Models to add over time:

- `WorkloadIdentity`
- `ResourceSample`
- `LogSignal`
- `KubernetesEvent`
- `DependencyEdge`
- `Anomaly`
- `EvidenceItem`
- `Incident`
- `Recommendation`

Rules:

- Keep API responses structured and predictable.
- Every finding should include timestamp, service, pod, namespace, signal, severity, value, threshold or baseline, and evidence IDs.
- Every insight should include confidence and evidence.

### Module 2: Collectors

Current:

- Mock collector.
- Prometheus/Loki collector.

Next collectors:

1. Kubernetes API collector
   - Pods.
   - Namespaces.
   - Owners.
   - Events.
   - PVC mounts.
   - Container restart reasons.

2. Prometheus expansion
   - CPU throttling.
   - Memory working set.
   - OOM indicators.
   - Network packet drops if available.
   - PVC read/write throughput.
   - PVC latency and IOPS.

3. Loki expansion
   - Error pattern extraction.
   - Top repeated log signatures.
   - First-seen and last-seen timestamps.

Future:

- OpenTelemetry traces via Tempo or Jaeger.
- Optional eBPF flow data.

### Module 3: Agent Engine

Current agents:

- CPU.
- Memory.
- Storage/PVC.
- Log/IO.

New agents:

- Network Agent.
- Restart/Event Agent.
- Dependency Agent.
- Baseline Anomaly Agent.
- Forecast Agent.

Agent contract:

```python
class Agent:
    name: str

    def analyze(self, context: AnalysisContext) -> list[AgentFinding]:
        ...
```

`AnalysisContext` should eventually contain:

- metrics
- logs
- kubernetes events
- dependencies
- historical windows

### Module 4: Resource Influence Graph

Goal:

Move from static dependency mapping to dynamic relationship discovery.

Graph nodes:

- Service.
- Pod.
- PVC.
- Namespace.
- Node.
- Incident.

Graph edges:

- `owns`: service to pod.
- `mounts`: pod to PVC.
- `calls`: service to service.
- `co_located`: pod to node.
- `temporal_influence`: anomaly happened before another anomaly.
- `correlated_with`: similar movement in the same window.

Scoring:

- anomaly strength
- time lag
- dependency distance
- severity
- recurrence

### Module 5: RCA Engine

Goal:

Rank root causes, not just list symptoms.

Inputs:

- Agent findings.
- Dependency graph.
- Time window.
- Evidence items.

Outputs:

- Root cause candidate.
- Confidence.
- Affected services.
- Evidence.
- Recommendation.

Initial ranking formula:

```text
score =
  anomaly_strength * 0.35
  + dependency_centrality * 0.20
  + temporal_precedence * 0.25
  + blast_radius * 0.10
  + recurrence * 0.10
```

### Module 6: LLM Insight Layer

Goal:

Use the LLM to explain and recommend, not to replace detection.

LLM input:

- Structured incident JSON.
- Top evidence.
- Log signatures.
- Related metrics.
- Dependency path.

LLM output:

- Human summary.
- Likely root cause.
- Why this happened.
- Recommended actions.
- Risk notes.
- Confidence explanation.

Safety rule:

The LLM must never execute cluster-changing actions automatically. It can suggest commands, but remediation must require human approval.

## API Contract Direction

Keep `/api/snapshot` working for the current frontend.

Add these next:

```text
GET /api/workloads
GET /api/incidents
GET /api/incidents/{incident_id}
GET /api/evidence/{incident_id}
GET /api/graph
GET /api/timeline
```

Recommended incident object:

```json
{
  "id": "inc_20260501_frontend_orders_db_latency",
  "status": "WARNING",
  "title": "Cascading latency from orders-db PVC",
  "summary": "Frontend errors increased after orders-db storage latency spiked.",
  "root_cause": {
    "kind": "pvc_latency",
    "service": "orders-db",
    "pod": "orders-db-0",
    "resource": "orders-data",
    "confidence": 0.82
  },
  "affected_services": ["frontend", "checkout-api", "orders-db"],
  "evidence": [],
  "recommendations": []
}
```

## Merge Order

1. Stabilize current app.
   - Tests pass.
   - Build passes.
   - Current snapshot API stays compatible.

2. Akhil creates frontend framework folders and component split.
   - No backend API breaking changes required.

3. Surya adds Kubernetes API collector behind feature-safe service methods.
   - If unavailable, fallback gracefully.

4. You add expanded models and incident API.
   - Keep old snapshot endpoint for compatibility.

5. Akhil adds Incidents and Evidence views.

6. You and Surya add Resource Influence Graph and RCA scoring.

7. Add LLM explanation layer.

## Weekly Execution Plan

### Day 1

- Akhil: split frontend into components and views.
- You: define new backend models for incidents/evidence/anomalies.
- Surya: design Kubernetes API collector and required dependencies.

### Day 2

- Akhil: build Incidents view and Evidence drawer from mock data.
- You: add `/api/incidents` using existing insights.
- Surya: implement pod/event/PVC discovery collector.

### Day 3

- Akhil: improve topology view and node details.
- You: create Resource Influence Graph model.
- Surya: add collector tests and demo event fixtures.

### Day 4

- Akhil: anomaly timeline UI.
- You: RCA scoring engine.
- Surya: Prometheus/Loki query improvements.

### Day 5

- Akhil: final dashboard polish.
- You: LLM insight service interface and prompt schema.
- Surya: live Minikube/K3s validation.

## Definition Of Done

The project is demo-ready when:

- It runs in demo mode without Kubernetes.
- It runs in live mode on Minikube/K3s/MicroK8s.
- It discovers pods across namespaces.
- It maps service-to-pod and pod-to-PVC dependencies.
- It detects CPU, memory, PVC, log, restart, and network anomalies.
- It shows a ranked root cause with evidence.
- It provides recommendations.
- It has a dashboard that looks operationally credible.
- Tests pass.
- The technical report explains architecture, methodology, and research basis.
