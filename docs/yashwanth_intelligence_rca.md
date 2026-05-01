# Yashwanth: Intelligence Architecture And RCA Engine

## Mission

Own the core intelligence architecture of Kovalent: canonical models, API contracts, multi-agent analysis flow, Resource Influence Graph, root-cause ranking, and LLM-ready evidence generation.

Kovalent should not be only a monitoring dashboard. The backend should become an intelligence engine that answers:

> What changed, what caused it, what was affected, what evidence proves it, and what should the operator do next?

## Owned Paths

- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/services/`
- `backend/app/agents/`
- `backend/app/correlation.py`
- `backend/tests/`

## Core Deliverables

### 1. Canonical Intelligence Models

Add models that support industry-level observability and RCA:

- `WorkloadIdentity`
- `AnalysisContext`
- `Anomaly`
- `EvidenceItem`
- `Incident`
- `Recommendation`
- `DependencyEdge`
- `RootCauseCandidate`

Rules:

- Keep API responses structured and predictable.
- Every finding should include timestamp, service, pod, namespace, signal, severity, value, threshold or baseline, and evidence IDs.
- Every incident should include confidence and evidence.

### 2. Incident API

Add new endpoints while keeping `/api/snapshot` compatible with Akhil's frontend work:

```text
GET /api/incidents
GET /api/incidents/{incident_id}
GET /api/evidence/{incident_id}
```

Initial strategy:

- Convert current `Insight` objects into richer `Incident` objects.
- Generate stable incident IDs from event, affected services, and root cause.
- Attach evidence from current agent findings.

Target incident object:

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

### 3. Resource Influence Graph

Move Kovalent from static dependency display to real influence mapping.

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
- `correlated_with`: signals moved together.
- `temporal_influence`: one anomaly happened before another.

Edge scoring:

- anomaly strength
- time lag
- dependency distance
- severity
- recurrence

### 4. RCA Scoring Engine

Rank root causes instead of only listing threshold findings.

Initial formula:

```text
score =
  anomaly_strength * 0.35
  + dependency_centrality * 0.20
  + temporal_precedence * 0.25
  + blast_radius * 0.10
  + recurrence * 0.10
```

Output should include:

- Root cause candidate.
- Confidence.
- Affected services.
- Evidence.
- Recommendation.

### 5. LLM Insight Interface

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

## Suggested Backend Structure

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

## First Tasks

1. Add `Incident`, `EvidenceItem`, `Recommendation`, and `RootCauseCandidate` models.
2. Add `incident_service.py`.
3. Add `GET /api/incidents`.
4. Convert existing insights into incidents.
5. Add backend tests for incident generation.
6. Add graph model fields needed by Akhil's topology UI.

## Acceptance Criteria

- Current `/api/snapshot` remains compatible.
- New `/api/incidents` returns structured, evidence-backed incidents.
- Each incident has title, severity, root cause candidate, confidence, affected services, evidence, and recommendations.
- RCA logic works on demo data without live Kubernetes.
- Tests pass with `.venv/bin/python -m pytest -q`.
