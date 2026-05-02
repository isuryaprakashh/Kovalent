import asyncio

from app.services.incident_service import IncidentService
from app.services.insight_service import InsightService


def test_incident_service_builds_evidence_backed_incidents() -> None:
    service = IncidentService(InsightService())

    incidents = asyncio.run(service.build_incidents())

    assert incidents
    incident = incidents[0]
    assert incident.id.startswith("inc_")
    assert incident.root_cause.confidence > 0
    assert incident.evidence
    assert incident.recommendations
    assert "frontend" in incident.affected_services


def test_cascading_latency_root_cause_prefers_storage_signal() -> None:
    service = IncidentService(InsightService())

    incidents = asyncio.run(service.build_incidents())
    cascading = next(incident for incident in incidents if incident.title == "Cascading Latency Detected")

    assert cascading.root_cause.kind == "pvc_latency"
    assert cascading.root_cause.service == "orders-db"
    assert cascading.root_cause.resource == "orders-data"
