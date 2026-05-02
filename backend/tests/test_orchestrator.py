import asyncio

from app.config import Settings
from app.services.causal_engine import CausalEngine
from app.services.incident_service import IncidentService
from app.services.insight_service import InsightService
from app.services.kpi_buffer import KpiBuffer
from app.services.live_graph import LiveGraphBuilder
from app.services.llm_client import LlmClient, build_report, build_runbook
from app.services.orchestrator import Orchestrator


def _build_orchestrator():
    settings = Settings()
    service = InsightService(settings)
    incident_service = IncidentService(service)
    live_graph = LiveGraphBuilder(settings)
    kpi_buffer = KpiBuffer(window_size=10)
    causal_engine = CausalEngine(threshold=0.15)

    # Seed the buffer and graph
    snapshot = asyncio.run(service.build_snapshot())
    kpi_buffer.ingest(snapshot.metrics)
    live_graph.rebuild(snapshot)

    return Orchestrator(
        settings=settings,
        incident_service=incident_service,
        live_graph=live_graph,
        causal_engine=causal_engine,
        kpi_buffer=kpi_buffer,
    )


def test_orchestrator_generates_report_demo_mode() -> None:
    orch = _build_orchestrator()
    incidents = asyncio.run(orch.incident_service.build_incidents())
    assert incidents

    report = asyncio.run(orch.generate_report(incidents[0].id))
    assert report is not None
    assert report.incident_id == incidents[0].id
    assert report.summary
    assert report.root_cause_pod
    assert 0 <= report.confidence <= 1
    assert report.recommendations
    assert report.runbook


def test_orchestrator_caches_reports() -> None:
    orch = _build_orchestrator()
    incidents = asyncio.run(orch.incident_service.build_incidents())
    asyncio.run(orch.generate_report(incidents[0].id))

    # Second call should return cached version
    report = asyncio.run(orch.generate_report(incidents[0].id))
    assert report is not None


def test_orchestrator_returns_none_for_unknown_incident() -> None:
    orch = _build_orchestrator()
    report = asyncio.run(orch.generate_report("nonexistent-id"))
    assert report is None


def test_llm_client_deterministic_mode() -> None:
    client = LlmClient(api_key=None)
    from app.models import AgentFinding, EvidencePacket, RootCauseChainEntry, Severity
    packet = EvidencePacket(
        trigger_pod="test-pod",
        anomaly_type="cpu_saturation",
        anomaly_score=0.85,
        causal_chain=[RootCauseChainEntry(pod="test-pod", score=0.9, lag_seconds=5)],
        agent_findings=[
            AgentFinding(
                agent="test", status=Severity.WARNING, pod="test-pod",
                service="test-svc", signal="cpu_saturation",
                message="High CPU", value=0.9, threshold=0.8,
            )
        ],
        graph_snapshot={},
    )
    result = asyncio.run(client.analyze(packet))
    assert "summary" in result
    assert "root_cause_pod" in result
    assert "recommendations" in result


def test_build_runbook_generates_steps() -> None:
    steps = build_runbook("pvc_latency", "orders-db-0")
    assert len(steps) == 3
    assert all(step.target == "orders-db-0" for step in steps)


def test_build_report_assembles_correctly() -> None:
    llm_response = {
        "summary": "Test summary",
        "root_cause_pod": "test-pod",
        "confidence": 0.8,
        "explanation": "Test explanation",
        "propagation_path": ["pod-a", "pod-b"],
        "recommendations": [{"action": "Scale up", "target": "test-pod", "rationale": "Load is high"}],
    }
    report = build_report("inc_test", llm_response, "cpu_saturation")
    assert report.incident_id == "inc_test"
    assert report.root_cause_pod == "test-pod"
    assert report.runbook
    assert report.recommendations
