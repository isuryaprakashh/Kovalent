from __future__ import annotations

import logging
from itertools import product

import networkx as nx
import numpy as np

from app.models import CausalEdge, RootCauseChainEntry
from app.services.kpi_buffer import KPIS, KpiBuffer

logger = logging.getLogger(__name__)


def _has_torch() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


class CausalEngine:
    """Lightweight Granger causal engine.

    Primary: cMLP (PyTorch) per KPI pair.
    Fallback: linear Granger test (OLS) when PyTorch is unavailable.

    Maintains a CausalGraph (NetworkX DiGraph) updated every retrain cycle.
    """

    def __init__(self, threshold: float = 0.15, cadence_seconds: float = 5.0) -> None:
        self.threshold = threshold
        self.cadence_seconds = cadence_seconds
        self.causal_graph: nx.DiGraph = nx.DiGraph()
        self._use_torch = _has_torch()
        if self._use_torch:
            logger.info("CausalEngine: using PyTorch cMLP backend.")
        else:
            logger.info("CausalEngine: PyTorch unavailable, using linear Granger fallback.")

    def retrain(self, kpi_buffer: KpiBuffer) -> nx.DiGraph:
        """Retrain causal edges from the current KPI buffer."""
        pods = kpi_buffer.get_pods()
        edges: list[CausalEdge] = []

        for (pod_a, kpi_a), (pod_b, kpi_b) in product(
            [(p, k) for p in pods for k in KPIS],
            [(p, k) for p in pods for k in KPIS],
        ):
            if pod_a == pod_b and kpi_a == kpi_b:
                continue

            x = kpi_buffer.get_window(pod_a, kpi_a)
            y = kpi_buffer.get_window(pod_b, kpi_b)
            if x is None or y is None:
                continue

            min_len = min(len(x), len(y))
            if min_len < 10:
                continue
            x, y = x[-min_len:], y[-min_len:]

            if self._use_torch:
                score = self._granger_cmlp(x, y)
            else:
                score = self._granger_linear(x, y)

            if score >= self.threshold:
                lag = self._estimate_lag(x, y)
                edges.append(CausalEdge(
                    source_pod=pod_a, source_kpi=kpi_a,
                    target_pod=pod_b, target_kpi=kpi_b,
                    causal_strength=round(min(1.0, score), 3),
                    lag_seconds=round(lag * self.cadence_seconds, 1),
                ))

        # Rebuild the causal graph
        g = nx.DiGraph()
        for edge in edges:
            g.add_edge(
                edge.source_pod, edge.target_pod,
                causal_strength=edge.causal_strength,
                lag_seconds=edge.lag_seconds,
                source_kpi=edge.source_kpi,
                target_kpi=edge.target_kpi,
            )
        self.causal_graph = g
        logger.info("CausalEngine: retrained with %d edges across %d pods.", len(edges), len(pods))
        return g

    def get_causal_edges(self) -> list[CausalEdge]:
        """Return all current causal edges."""
        edges: list[CausalEdge] = []
        for src, dst, data in self.causal_graph.edges(data=True):
            edges.append(CausalEdge(
                source_pod=src, target_pod=dst,
                source_kpi=data.get("source_kpi", ""),
                target_kpi=data.get("target_kpi", ""),
                causal_strength=data.get("causal_strength", 0),
                lag_seconds=data.get("lag_seconds", 0),
            ))
        return edges

    def get_root_cause_chain(self, anomaly_pod: str, top_k: int = 5) -> list[RootCauseChainEntry]:
        """Random walk with restart from anomaly_pod. Returns ranked list of
        (pod, score, lag_seconds)."""
        g = self.causal_graph
        if anomaly_pod not in g:
            return [RootCauseChainEntry(pod=anomaly_pod, score=1.0, lag_seconds=0)]

        # Personalized PageRank (random walk with restart)
        alpha = 0.15  # restart probability
        personalization = {node: 0.0 for node in g.nodes}
        personalization[anomaly_pod] = 1.0

        try:
            scores = self._pagerank(g, alpha=alpha, personalization=personalization)
        except Exception:
            scores = {anomaly_pod: 1.0}

        # Build ranked chain with lag info
        chain: list[RootCauseChainEntry] = []
        for pod, score in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]:
            # Aggregate lag from edges leading to this pod
            in_edges = list(g.in_edges(pod, data=True))
            avg_lag = (
                sum(d.get("lag_seconds", 0) for _, _, d in in_edges) / len(in_edges)
                if in_edges else 0.0
            )
            chain.append(RootCauseChainEntry(
                pod=pod, score=round(min(1.0, score * 5), 3),  # scale PageRank scores
                lag_seconds=round(avg_lag, 1),
            ))

        return chain

    # -------------------------------------------------------------------
    # Granger scoring backends
    # -------------------------------------------------------------------

    def _granger_cmlp(self, x: np.ndarray, y: np.ndarray, lags: int = 3, steps: int = 20) -> float:
        """Component-wise MLP Granger test using PyTorch."""
        import torch
        import torch.nn as nn

        n = len(y) - lags
        if n < 5:
            return 0.0

        # Build lagged dataset
        Y = torch.tensor(y[lags:], dtype=torch.float32).unsqueeze(1)
        X_self = torch.zeros(n, lags, dtype=torch.float32)
        X_other = torch.zeros(n, lags, dtype=torch.float32)
        for lag in range(lags):
            X_self[:, lag] = torch.tensor(y[lags - lag - 1: n + lags - lag - 1], dtype=torch.float32)
            X_other[:, lag] = torch.tensor(x[lags - lag - 1: n + lags - lag - 1], dtype=torch.float32)

        # Model: predict Y from lagged Y only (restricted)
        restricted = nn.Sequential(nn.Linear(lags, 16), nn.ReLU(), nn.Linear(16, 1))
        opt_r = torch.optim.Adam(restricted.parameters(), lr=0.01)
        for _ in range(steps):
            loss = nn.functional.mse_loss(restricted(X_self), Y)
            opt_r.zero_grad()
            loss.backward()
            opt_r.step()
        mse_restricted = nn.functional.mse_loss(restricted(X_self), Y).item()

        # Model: predict Y from lagged Y + lagged X (unrestricted)
        X_full = torch.cat([X_self, X_other], dim=1)
        unrestricted = nn.Sequential(nn.Linear(lags * 2, 16), nn.ReLU(), nn.Linear(16, 1))
        opt_u = torch.optim.Adam(unrestricted.parameters(), lr=0.01)
        for _ in range(steps):
            loss = nn.functional.mse_loss(unrestricted(X_full), Y)
            opt_u.zero_grad()
            loss.backward()
            opt_u.step()
        mse_unrestricted = nn.functional.mse_loss(unrestricted(X_full), Y).item()

        if mse_restricted < 1e-10:
            return 0.0
        return max(0.0, (mse_restricted - mse_unrestricted) / mse_restricted)

    def _granger_linear(self, x: np.ndarray, y: np.ndarray, lags: int = 3) -> float:
        """Linear Granger test via OLS (no external dependencies)."""
        n = len(y) - lags
        if n < 5:
            return 0.0

        # Build lagged matrices
        Y = y[lags:]
        X_self = np.column_stack([y[lags - lag - 1: n + lags - lag - 1] for lag in range(lags)])
        X_other = np.column_stack([x[lags - lag - 1: n + lags - lag - 1] for lag in range(lags)])

        # Restricted: Y ~ lagged Y
        X_r = np.column_stack([np.ones(n), X_self])
        try:
            beta_r = np.linalg.lstsq(X_r, Y, rcond=None)[0]
            mse_r = np.mean((Y - X_r @ beta_r) ** 2)
        except np.linalg.LinAlgError:
            return 0.0

        # Unrestricted: Y ~ lagged Y + lagged X
        X_u = np.column_stack([np.ones(n), X_self, X_other])
        try:
            beta_u = np.linalg.lstsq(X_u, Y, rcond=None)[0]
            mse_u = np.mean((Y - X_u @ beta_u) ** 2)
        except np.linalg.LinAlgError:
            return 0.0

        if mse_r < 1e-10:
            return 0.0
        return max(0.0, (mse_r - mse_u) / mse_r)

    def _estimate_lag(self, x: np.ndarray, y: np.ndarray, max_lag: int = 10) -> float:
        """Estimate the dominant lag via cross-correlation."""
        max_lag = min(max_lag, len(x) // 3)
        if max_lag < 1:
            return 0.0

        x_norm = x - np.mean(x)
        y_norm = y - np.mean(y)
        best_lag, best_corr = 0, 0.0

        for lag in range(1, max_lag + 1):
            if len(x_norm) - lag < 2:
                break
            corr = np.abs(np.corrcoef(x_norm[:-lag], y_norm[lag:])[0, 1])
            if not np.isnan(corr) and corr > best_corr:
                best_corr = corr
                best_lag = lag

        return float(best_lag)

    def _pagerank(
        self,
        g: nx.DiGraph,
        alpha: float = 0.15,
        personalization: dict[str, float] | None = None,
        max_iter: int = 100,
        tol: float = 1e-6,
    ) -> dict[str, float]:
        """Manual power-iteration PageRank (no scipy required)."""
        nodes = list(g.nodes)
        n = len(nodes)
        if n == 0:
            return {}

        idx = {node: i for i, node in enumerate(nodes)}

        # Build transition matrix
        M = np.zeros((n, n), dtype=np.float64)
        for src, dst, data in g.edges(data=True):
            M[idx[dst], idx[src]] = data.get("causal_strength", 1.0)

        # Normalize columns
        col_sums = M.sum(axis=0)
        dangling = col_sums == 0
        col_sums[dangling] = 1.0
        M /= col_sums

        # Personalization vector
        if personalization:
            p = np.array([personalization.get(node, 0.0) for node in nodes], dtype=np.float64)
        else:
            p = np.ones(n, dtype=np.float64)
        p_sum = p.sum()
        if p_sum > 0:
            p /= p_sum

        # Power iteration
        x = p.copy()
        for _ in range(max_iter):
            x_new = (1 - alpha) * M @ x + alpha * p
            # Handle dangling nodes
            dangling_weight = (1 - alpha) * x[dangling].sum()
            x_new += dangling_weight * p
            # Normalize
            x_sum = x_new.sum()
            if x_sum > 0:
                x_new /= x_sum
            if np.linalg.norm(x_new - x, 1) < tol:
                break
            x = x_new

        return {node: float(x[i]) for i, node in enumerate(nodes)}

