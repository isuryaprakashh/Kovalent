# Akhil: Frontend And Dashboard Framework

## Mission

Build the full frontend framework so Kovalent looks and feels like an enterprise observability platform, not a hackathon demo.

The frontend should communicate this product idea clearly:

> Kovalent discovers pod behavior in real time, maps dependencies, detects cross-resource anomalies, and explains root cause with evidence.

## Owned Paths

- `frontend/src/main.jsx`
- `frontend/src/styles.css`
- Future frontend folders:
  - `frontend/src/components/`
  - `frontend/src/views/`
  - `frontend/src/api/`
  - `frontend/src/lib/`

## Core Deliverables

### 1. App Shell

Build a professional operational shell:

- Header with cluster/source status.
- Left navigation or compact tab system.
- Main views:
  - Overview.
  - Topology.
  - Incidents.
  - Workloads.
  - Evidence.
- Responsive desktop-first layout.

### 2. Dashboard Views

Build these views/components:

- Overview summary cards.
- Resource signal table.
- Dependency topology graph.
- Incident list.
- Incident detail drawer.
- Evidence drawer.
- Anomaly and restart timeline.
- Workload details panel.

### 3. Frontend API Layer

Create a single API client layer instead of fetch calls scattered across UI components.

Suggested files:

```text
frontend/src/api/
  client.js
  snapshot.js
  incidents.js
```

The API layer should handle:

- Loading states.
- Error states.
- Backend unavailable fallback.
- Refresh states.
- Shared response parsing.

### 4. Enterprise UX Requirements

- No landing-page style hero sections.
- Dense, useful operational UI.
- Every insight must show evidence, severity, affected services, and timestamp.
- Empty states should be professional and actionable.
- The dashboard must remain useful on demo data and live data.
- Text must not overlap on mobile or desktop.
- Use icons for clear actions where possible.
- Keep cards restrained and purposeful.

## Stable Backend Endpoints To Consume

Start with these existing endpoints:

```text
GET /api/status
GET /api/snapshot
GET /api/insights
GET /api/topology
```

Design UI for these upcoming endpoints:

```text
GET /api/incidents
GET /api/workloads
GET /api/evidence/{incident_id}
GET /api/graph
```

## Suggested Frontend Structure

```text
frontend/src/
  api/
    client.js
    snapshot.js
    incidents.js
  components/
    AppShell.jsx
    StatusPill.jsx
    MetricTile.jsx
    ResourceTable.jsx
    TopologyGraph.jsx
    IncidentList.jsx
    EvidenceDrawer.jsx
    AnomalyTimeline.jsx
    WorkloadDetails.jsx
  views/
    OverviewView.jsx
    TopologyView.jsx
    IncidentsView.jsx
    WorkloadsView.jsx
  lib/
    formatters.js
    severity.js
```

## First Tasks

1. Split `frontend/src/main.jsx` into component and view files.
2. Create `frontend/src/api/client.js`.
3. Keep the current `/api/snapshot` dashboard working.
4. Add an Incidents view that can render from current `snapshot.insights`.
5. Add an Evidence drawer using mock evidence until Yashwanth's `/api/evidence/{incident_id}` is ready.

## Acceptance Criteria

- `npm run build` passes.
- UI works when backend is unavailable by showing demo fallback.
- Topology node click opens useful details.
- Incident view can render from current `snapshot.insights`.
- Dashboard has a serious enterprise-tool feel.
- No text overlap on mobile or desktop.
