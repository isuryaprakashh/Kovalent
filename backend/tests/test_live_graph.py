import asyncio

from app.collectors.flow_collector import MockFlowCollector
from app.config import Settings
from app.services.insight_service import InsightService
from app.services.live_graph import LiveGraphBuilder


def _build_graph():
    settings = Settings()
    service = InsightService(settings)
    snapshot = asyncio.run(service.build_snapshot())
    flows = asyncio.run(MockFlowCollector().collect())
    builder = LiveGraphBuilder(settings)
    g = builder.rebuild(snapshot, flows)
    return builder, g


def test_live_graph_has_pod_service_pvc_nodes() -> None:
    builder, g = _build_graph()
    kinds = {data.get("kind") for _, data in g.nodes(data=True)}
    assert "pod" in kinds
    assert "service" in kinds
    assert "pvc" in kinds
    assert "namespace" in kinds


def test_live_graph_has_owns_mounts_edges() -> None:
    _, g = _build_graph()
    relationships = {data.get("relationship") for _, _, data in g.edges(data=True)}
    assert "owns" in relationships
    assert "mounts" in relationships


def test_live_graph_has_flow_edges() -> None:
    _, g = _build_graph()
    flow_edges = [
        (u, v, d) for u, v, d in g.edges(data=True) if d.get("relationship") == "observed_flow"
    ]
    assert flow_edges
    assert all(d.get("bytes_per_sec", 0) > 0 for _, _, d in flow_edges)


def test_live_graph_get_neighbors() -> None:
    builder, _ = _build_graph()
    neighbors = builder.get_neighbors("orders-db-0")
    assert neighbors
    assert any(n["relationship"] == "mounts" for n in neighbors)


def test_live_graph_serializes_to_json() -> None:
    builder, _ = _build_graph()
    data = builder.to_json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0


def test_live_graph_get_graph_returns_latest() -> None:
    builder, g = _build_graph()
    retrieved = builder.get_graph()
    assert retrieved.number_of_nodes() == g.number_of_nodes()
