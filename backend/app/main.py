from __future__ import annotations

import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.services.causal_engine import CausalEngine
from app.services.graph_service import GraphService
from app.services.incident_service import IncidentService
from app.services.insight_service import InsightService
from app.services.kpi_buffer import KpiBuffer
from app.services.live_graph import LiveGraphBuilder
from app.services.orchestrator import Orchestrator
from app.services.rca_service import RcaService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Service wiring
# ---------------------------------------------------------------------------
settings = get_settings()
service = InsightService(settings)
incident_service = IncidentService(service)
graph_service = GraphService(service)
rca_service = RcaService(incident_service, graph_service)

# M4–M6 services
live_graph = LiveGraphBuilder(settings)
kpi_buffer = KpiBuffer(window_size=settings.causal_window_size)
causal_engine = CausalEngine(threshold=settings.causal_threshold)
orchestrator = Orchestrator(
    settings=settings,
    incident_service=incident_service,
    live_graph=live_graph,
    causal_engine=causal_engine,
    kpi_buffer=kpi_buffer,
)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------
async def _graph_rebuild_loop() -> None:
    """Rebuild the live graph every N seconds."""
    interval = settings.graph_rebuild_interval
    while True:
        try:
            snapshot = await service.build_snapshot()
            # Feed KPI buffer
            kpi_buffer.ingest(snapshot.metrics)
            # Collect flow data
            from app.collectors.flow_collector import MockFlowCollector, HubbleFlowCollector
            if settings.hubble_url:
                flows = await HubbleFlowCollector(settings.hubble_url).collect()
            else:
                flows = await MockFlowCollector().collect()
            # Rebuild graph
            live_graph.rebuild(snapshot, flows)
            logger.debug("Graph rebuilt with %d nodes, %d edges.",
                         live_graph._graph.number_of_nodes(),
                         live_graph._graph.number_of_edges())
        except Exception as exc:
            logger.error("Graph rebuild failed: %s", exc)
        await asyncio.sleep(interval)


async def _causal_retrain_loop() -> None:
    """Retrain the causal engine every N seconds."""
    interval = settings.causal_retrain_interval
    while True:
        await asyncio.sleep(interval)
        try:
            orchestrator.retrain_causal()
        except Exception as exc:
            logger.error("Causal retrain failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on app startup, cancel on shutdown."""
    graph_task = asyncio.create_task(_graph_rebuild_loop())
    causal_task = asyncio.create_task(_causal_retrain_loop())
    logger.info("Background tasks started: graph rebuild (%ds), causal retrain (%ds).",
                settings.graph_rebuild_interval, settings.causal_retrain_interval)
    yield
    graph_task.cancel()
    causal_task.cancel()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Kovalent API",
    description="AI-assisted Kubernetes pod intelligence and root-cause insights.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Existing endpoints (backwards-compatible)
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kovalent-api"}


@app.get("/api/snapshot")
async def snapshot() -> dict:
    snapshot_data = await service.build_snapshot()
    return snapshot_data.model_dump()


@app.get("/api/status")
def api_status() -> dict:
    return {
        "mode": service.settings.mode,
        "prometheus_url": service.settings.prometheus_url,
        "loki_configured": service.settings.loki_url is not None,
        "namespace_regex": service.settings.namespace_regex,
        "query_window": service.settings.query_window,
        "live_fallback_enabled": service.settings.live_fallback_enabled,
        "kubernetes_discovery_mode": service.settings.kubernetes_discovery_mode,
        "kubernetes_event_limit": service.settings.kubernetes_event_limit,
        "live_collector_status": service.live_collector.status,
        "hubble_configured": settings.hubble_url is not None,
        "google_api_configured": settings.google_api_key is not None,
    }


@app.get("/api/insights")
async def insights() -> dict:
    snapshot_data = await service.build_snapshot()
    return {"insights": [insight.model_dump() for insight in snapshot_data.insights]}


@app.get("/api/topology")
async def topology() -> dict:
    snapshot_data = await service.build_snapshot()
    return snapshot_data.topology.model_dump()


@app.get("/api/incidents")
async def incidents() -> dict:
    incident_data = await incident_service.build_incidents()
    return {"incidents": [incident.model_dump() for incident in incident_data]}


@app.get("/api/incidents/{incident_id}")
async def incident_detail(incident_id: str) -> dict:
    incident = await incident_service.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.model_dump()


@app.get("/api/evidence/{incident_id}")
async def incident_evidence(incident_id: str) -> dict:
    evidence = await incident_service.get_evidence(incident_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"evidence": [item.model_dump() for item in evidence]}


@app.get("/api/graph")
async def resource_graph() -> dict:
    graph = await graph_service.build_graph()
    return graph.model_dump()


@app.get("/api/rca")
async def rca_analyses() -> dict:
    analyses = await rca_service.build_analyses()
    return {"analyses": [analysis.model_dump() for analysis in analyses]}


@app.get("/api/rca/{incident_id}")
async def rca_detail(incident_id: str) -> dict:
    analysis = await rca_service.get_analysis(incident_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="RCA analysis not found")
    return analysis.model_dump()


# ---------------------------------------------------------------------------
# M4 — Live Graph endpoints
# ---------------------------------------------------------------------------


@app.get("/api/live-graph")
async def live_graph_endpoint() -> dict:
    """Return the current live NetworkX graph as node-link JSON."""
    return live_graph.to_json()


@app.get("/api/live-graph/neighbors/{pod_id}")
async def live_graph_neighbors(pod_id: str) -> dict:
    """Return the neighbors of a pod in the live graph."""
    neighbors = live_graph.get_neighbors(pod_id)
    return {"pod_id": pod_id, "neighbors": neighbors}


# ---------------------------------------------------------------------------
# M5 — Causal Graph endpoints
# ---------------------------------------------------------------------------


@app.get("/api/causal-graph")
async def causal_graph() -> dict:
    """Return current causal edges with Granger strengths."""
    edges = orchestrator.get_causal_edges()
    return {
        "edges": [edge.model_dump() for edge in edges],
        "buffer_fill": kpi_buffer.filled_fraction(),
        "buffer_ready": kpi_buffer.is_ready(),
    }


@app.get("/api/causal-graph/root-cause/{pod_id}")
async def causal_root_cause(pod_id: str) -> dict:
    """Return ranked root cause chain via random walk with restart."""
    chain = orchestrator.get_root_cause_chain(pod_id)
    return {"pod_id": pod_id, "chain": [entry.model_dump() for entry in chain]}


# ---------------------------------------------------------------------------
# M6 — Orchestrator / LLM endpoints
# ---------------------------------------------------------------------------


@app.get("/api/orchestrator/report/{incident_id}")
async def orchestrator_report(incident_id: str) -> dict:
    """Generate or retrieve an LLM-synthesized incident report."""
    report = await orchestrator.generate_report(incident_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return report.model_dump()


@app.get("/api/orchestrator/reports")
async def orchestrator_reports() -> dict:
    """Return all cached reports (most recent first)."""
    reports = await orchestrator.get_all_reports()
    return {"reports": [r.model_dump() for r in reports]}


@app.post("/api/orchestrator/remediate/{incident_id}")
async def orchestrator_remediate(incident_id: str, step_index: int) -> dict:
    """Trigger a remediation step for an incident.
    
    In this version, we just log the action and return success.
    In production, this would call the K8s API or a workflow engine.
    """
    report = await orchestrator.generate_report(incident_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    if step_index < 0 or step_index >= len(report.runbook):
        raise HTTPException(status_code=400, detail="Invalid step index")
    
    step = report.runbook[step_index]
    logger.info("REMEDIATION TRIGGERED: Incident=%s, Action=%s, Target=%s", 
                incident_id, step.action, step.target)
    
    return {
        "status": "triggered",
        "incident_id": incident_id,
        "action": step.action,
        "target": step.target,
        "message": f"Remediation step '{step.action}' has been initiated."
    }
