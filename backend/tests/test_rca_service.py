import asyncio

from app.services.graph_service import GraphService
from app.services.incident_service import IncidentService
from app.services.insight_service import InsightService
from app.services.rca_service import RcaService


def test_rca_service_ranks_candidates_with_breakdowns() -> None:
    insight_service = InsightService()
    rca_service = RcaService(IncidentService(insight_service), GraphService(insight_service))

    analyses = asyncio.run(rca_service.build_analyses())

    assert analyses
    analysis = analyses[0]
    assert analysis.candidates
    assert analysis.winning_candidate.breakdown.final_score > 0
    assert analysis.winning_candidate.candidate.confidence > 0
    assert analysis.llm_context.incident_id == analysis.incident_id


def test_rca_service_builds_llm_guardrails_and_schema() -> None:
    insight_service = InsightService()
    rca_service = RcaService(IncidentService(insight_service), GraphService(insight_service))

    analysis = asyncio.run(rca_service.build_analyses())[0]

    assert analysis.llm_context.guardrails
    assert "summary" in analysis.llm_context.output_schema
    assert analysis.llm_context.evidence_summary


def test_cascading_latency_rca_prefers_storage_candidate() -> None:
    insight_service = InsightService()
    rca_service = RcaService(IncidentService(insight_service), GraphService(insight_service))

    analyses = asyncio.run(rca_service.build_analyses())
    cascading = next(analysis for analysis in analyses if analysis.llm_context.incident.title == "Cascading Latency Detected")

    assert cascading.winning_candidate.candidate.kind == "pvc_latency"
    assert cascading.winning_candidate.candidate.service == "orders-db"
