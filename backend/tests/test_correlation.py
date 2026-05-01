from app.agents.cpu import CpuAgent
from app.agents.log_io import LogIoAgent
from app.agents.memory import MemoryAgent
from app.agents.storage import StorageAgent
from app.collectors.mock_collector import MockTelemetryCollector
from app.correlation import MasterCorrelationEngine


def test_correlation_detects_cascading_latency() -> None:
    metrics = MockTelemetryCollector().collect()
    findings = []
    for agent in [CpuAgent(), MemoryAgent(), StorageAgent(), LogIoAgent()]:
        findings.extend(agent.analyze(metrics))

    insights = MasterCorrelationEngine().correlate(findings)

    assert insights[0].event == "Cascading Latency Detected"
    assert "frontend" in insights[0].affected_services
    assert "orders-db" in insights[0].affected_services

