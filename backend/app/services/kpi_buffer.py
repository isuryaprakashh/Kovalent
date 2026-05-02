from __future__ import annotations

from collections import deque

import numpy as np

from app.models import PodMetric


_KPI_EXTRACTORS: dict[str, callable] = {
    "cpu_ratio": lambda m: m.cpu_ratio,
    "memory_ratio": lambda m: m.memory_ratio,
    "error_rate": lambda m: m.error_rate_per_minute,
    "network_throughput": lambda m: m.network_rx_kbps + m.network_tx_kbps,
    "pvc_latency": lambda m: m.pvc_latency_ms if m.pvc_latency_ms is not None else 0.0,
}

KPIS = list(_KPI_EXTRACTORS.keys())


class KpiBuffer:
    """Rolling per-pod KPI time-series buffer for the causal engine.

    Stores the last `window_size` observations (default 60 = 5 min at 5s cadence).
    """

    def __init__(self, window_size: int = 60) -> None:
        self.window_size = window_size
        self._buffers: dict[str, dict[str, deque[float]]] = {}

    def ingest(self, metrics: list[PodMetric]) -> None:
        """Push the latest metric snapshot into the buffer."""
        for metric in metrics:
            pod = metric.pod
            if pod not in self._buffers:
                self._buffers[pod] = {kpi: deque(maxlen=self.window_size) for kpi in KPIS}
            for kpi, extractor in _KPI_EXTRACTORS.items():
                try:
                    value = float(extractor(metric))
                except (TypeError, ValueError):
                    value = 0.0
                self._buffers[pod][kpi].append(value)

    def get_window(self, pod: str, kpi: str) -> np.ndarray | None:
        """Return the buffered time-series for a (pod, kpi) pair as a numpy array."""
        buf = self._buffers.get(pod, {}).get(kpi)
        if buf is None or len(buf) < 2:
            return None
        return np.array(buf, dtype=np.float64)

    def get_pods(self) -> list[str]:
        """Return all pods currently tracked."""
        return list(self._buffers.keys())

    def is_ready(self) -> bool:
        """True when at least one pod has a full window."""
        for pod_buffers in self._buffers.values():
            for buf in pod_buffers.values():
                if len(buf) >= self.window_size:
                    return True
        return False

    def filled_fraction(self) -> float:
        """Return the max fill fraction across all pods."""
        if not self._buffers:
            return 0.0
        max_fill = 0.0
        for pod_buffers in self._buffers.values():
            for buf in pod_buffers.values():
                max_fill = max(max_fill, len(buf) / self.window_size)
        return max_fill

    def get_history(self, pod: str) -> dict[str, list[float]]:
        """Return all historical KPI points for a specific pod."""
        pod_data = self._buffers.get(pod, {})
        return {kpi: list(buf) for kpi, buf in pod_data.items()}
