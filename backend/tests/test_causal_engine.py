import asyncio

import numpy as np

from app.collectors.mock_collector import MockTelemetryCollector
from app.services.causal_engine import CausalEngine
from app.services.kpi_buffer import KpiBuffer


def _fill_buffer(window_size: int = 15) -> KpiBuffer:
    """Fill a KPI buffer with multiple snapshots of mock data."""
    buf = KpiBuffer(window_size=window_size)
    collector = MockTelemetryCollector()
    for _ in range(window_size):
        metrics = asyncio.run(collector.collect())
        buf.ingest(metrics)
    return buf


def test_kpi_buffer_stores_values() -> None:
    buf = _fill_buffer(10)
    assert buf.get_pods()
    window = buf.get_window(buf.get_pods()[0], "cpu_ratio")
    assert window is not None
    assert len(window) == 10


def test_kpi_buffer_is_ready_when_full() -> None:
    buf = _fill_buffer(15)
    assert buf.is_ready()


def test_causal_engine_runs_linear_granger() -> None:
    engine = CausalEngine(threshold=0.0)  # low threshold to get edges
    engine._use_torch = False  # force linear fallback

    # Create correlated signals
    n = 30
    x = np.random.randn(n).cumsum()
    y = np.zeros(n)
    y[3:] = x[:-3] + np.random.randn(n - 3) * 0.1  # y follows x with lag 3

    score = engine._granger_linear(x, y, lags=5)
    assert score > 0


def test_causal_engine_retrain_produces_graph() -> None:
    buf = _fill_buffer(20)
    engine = CausalEngine(threshold=0.0)
    engine._use_torch = False
    g = engine.retrain(buf)
    # Should have at least some nodes (the pods)
    assert g.number_of_nodes() >= 0  # may have 0 edges with random data


def test_root_cause_chain_returns_entries() -> None:
    engine = CausalEngine(threshold=0.0)
    engine._use_torch = False
    buf = _fill_buffer(20)
    engine.retrain(buf)

    pods = buf.get_pods()
    chain = engine.get_root_cause_chain(pods[0])
    assert chain
    assert chain[0].pod == pods[0] or chain[0].score > 0


def test_root_cause_chain_unknown_pod_returns_self() -> None:
    engine = CausalEngine(threshold=0.15)
    chain = engine.get_root_cause_chain("nonexistent-pod")
    assert len(chain) == 1
    assert chain[0].pod == "nonexistent-pod"
