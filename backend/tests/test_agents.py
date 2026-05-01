import asyncio

from app.agents.cpu import CpuAgent
from app.agents.storage import StorageAgent
from app.collectors.mock_collector import MockTelemetryCollector


def test_cpu_agent_flags_saturation() -> None:
    metrics = asyncio.run(MockTelemetryCollector().collect())
    findings = CpuAgent().analyze(metrics)

    assert any(finding.service == "checkout-api" for finding in findings)


def test_storage_agent_flags_pvc_latency() -> None:
    metrics = asyncio.run(MockTelemetryCollector().collect())
    findings = StorageAgent().analyze(metrics)

    assert len(findings) == 1
    assert findings[0].service == "orders-db"
    assert findings[0].signal == "pvc_latency"
