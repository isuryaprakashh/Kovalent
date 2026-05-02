import asyncio

from app.services.graph_service import GraphService
from app.services.insight_service import InsightService


def test_graph_service_builds_scored_dependency_edges() -> None:
    graph = asyncio.run(GraphService(InsightService()).build_graph())

    assert graph.nodes
    assert graph.edges
    assert all(0 <= edge.score <= 1 for edge in graph.edges)
    assert any(edge.relationship == "mounts" and edge.evidence_ids for edge in graph.edges)


def test_graph_service_adds_correlation_edges() -> None:
    graph = asyncio.run(GraphService(InsightService()).build_graph())

    assert any(edge.relationship == "correlated_with" for edge in graph.edges)
