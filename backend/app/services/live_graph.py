from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph

from app.config import Settings
from app.models import ClusterSnapshot, FlowRecord, GraphSnapshot, PodMetric

logger = logging.getLogger(__name__)


class LiveGraphBuilder:
    """Builds and maintains a live NetworkX DiGraph from Kubernetes snapshots.

    Nodes: pods, services, PVCs, namespaces.
    Edges: owns (service→pod), mounts (pod→PVC), calls (service→service),
           co_located (pod↔pod on same node), observed_flow (eBPF).

    The graph is rebuilt from scratch on each cycle (every 5s).
    Timestamped snapshots are stored in Redis when available, otherwise in-memory.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._graph: nx.DiGraph = nx.DiGraph()
        self._history: list[GraphSnapshot] = []
        self._max_history = 120  # 10 minutes at 5s cadence
        self._redis: Any | None = None
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis
            self._redis = redis.Redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            self._redis.ping()
            logger.info("Redis connected for graph storage at %s", self.settings.redis_url)
        except Exception:
            logger.info("Redis unavailable — using in-memory graph storage.")
            self._redis = None

    def rebuild(
        self, 
        snapshot: ClusterSnapshot, 
        flows: list[FlowRecord] | None = None,
        namespace_filter: str | None = None
    ) -> nx.DiGraph:
        """Rebuild the entire graph from the latest snapshot + optional flow data."""
        g = nx.DiGraph()

        # --- Add namespace nodes ---
        namespaces: set[str] = set()
        for metric in snapshot.metrics:
            if namespace_filter and metric.namespace != namespace_filter:
                continue
            namespaces.add(metric.namespace)
        for ns in sorted(namespaces):
            g.add_node(f"ns:{ns}", kind="namespace", label=ns, status="OK")

        # --- Add service, pod, PVC nodes + structural edges ---
        service_pods: dict[str, list[str]] = {}
        for metric in snapshot.metrics:
            if namespace_filter and metric.namespace != namespace_filter:
                continue
            svc_id = f"svc:{metric.service}"
            pod_id = f"pod:{metric.pod}"
            ns_id = f"ns:{metric.namespace}"

            # Service node
            if svc_id not in g:
                g.add_node(svc_id, kind="service", label=metric.service,
                           namespace=metric.namespace, status="OK")
                g.add_edge(ns_id, svc_id, relationship="contains", weight=0.3)

            # Pod node with metric attributes
            g.add_node(pod_id, kind="pod", label=metric.pod,
                       namespace=metric.namespace, service=metric.service,
                       cpu_ratio=metric.cpu_ratio, memory_ratio=metric.memory_ratio,
                       error_rate=metric.error_rate_per_minute,
                       status=self._pod_status(metric))

            # owns: service → pod
            g.add_edge(svc_id, pod_id, relationship="owns",
                       weight=self._ownership_weight(metric))

            service_pods.setdefault(metric.service, []).append(pod_id)

            # mounts: pod → PVC
            if metric.pvc_name:
                pvc_id = f"pvc:{metric.pvc_name}"
                if pvc_id not in g:
                    g.add_node(pvc_id, kind="pvc", label=metric.pvc_name,
                               namespace=metric.namespace, status="OK")
                g.add_edge(pod_id, pvc_id, relationship="mounts",
                           weight=self._pvc_weight(metric))

        # --- calls edges from dependency map (insight service topology) ---
        for edge in snapshot.topology.edges:
            if edge.relationship == "calls" and edge.source in g and edge.target in g:
                g.add_edge(edge.source, edge.target, relationship="calls", weight=0.6)

        # --- co_located edges (pods sharing a namespace as proxy for same node) ---
        pods_by_ns: dict[str, list[str]] = {}
        for metric in snapshot.metrics:
            if namespace_filter and metric.namespace != namespace_filter:
                continue
            pods_by_ns.setdefault(metric.namespace, []).append(f"pod:{metric.pod}")
        for ns_pods in pods_by_ns.values():
            for i, pod_a in enumerate(ns_pods):
                for pod_b in ns_pods[i + 1:]:
                    if not g.has_edge(pod_a, pod_b):
                        g.add_edge(pod_a, pod_b, relationship="co_located", weight=0.2)
                        g.add_edge(pod_b, pod_a, relationship="co_located", weight=0.2)

        # --- Layer eBPF flow data ---
        if flows:
            for flow in flows:
                if namespace_filter and (flow.source_namespace != namespace_filter and flow.dest_namespace != namespace_filter):
                    continue
                src = f"pod:{flow.source_pod}"
                dst = f"pod:{flow.dest_pod}"
                if src in g and dst in g:
                    g.add_edge(src, dst, relationship="observed_flow",
                               weight=min(1.0, flow.bytes_per_sec / 5000),
                               bytes_per_sec=flow.bytes_per_sec,
                               call_frequency=flow.call_count)

        # --- Update finding-based status ---
        for finding in snapshot.findings:
            pod_id = f"pod:{finding.pod}"
            svc_id = f"svc:{finding.service}"
            # Findings don't always have namespace, but if they do we could filter
            if pod_id in g:
                g.nodes[pod_id]["status"] = finding.status.value
            if svc_id in g:
                current = g.nodes[svc_id].get("status", "OK")
                if self._severity_rank(finding.status.value) > self._severity_rank(current):
                    g.nodes[svc_id]["status"] = finding.status.value

        self._graph = g
        self._store_snapshot(g)
        return g

    def get_graph(self, t: float | None = None) -> nx.DiGraph:
        """Return the graph at time t (unix timestamp) or the latest."""
        if t is None:
            return self._graph

        # Try Redis first
        if self._redis:
            try:
                data = self._redis.get(f"kovalent:graph:{int(t)}")
                if data:
                    return json_graph.node_link_graph(json.loads(data))
            except Exception:
                pass

        # Fallback to in-memory history
        if self._history:
            closest = min(self._history, key=lambda s: abs(s.timestamp.timestamp() - t))
            return json_graph.node_link_graph(closest.node_link_data)

        return self._graph

    def get_neighbors(self, pod_id: str) -> list[dict[str, Any]]:
        """Return neighbors of a pod with edge attributes, for agent use."""
        if not pod_id.startswith("pod:"):
            pod_id = f"pod:{pod_id}"
        if pod_id not in self._graph:
            return []

        neighbors: list[dict[str, Any]] = []
        for neighbor in self._graph.successors(pod_id):
            edge_data = self._graph.edges[pod_id, neighbor]
            neighbors.append({
                "node": neighbor,
                "kind": self._graph.nodes[neighbor].get("kind", "unknown"),
                "relationship": edge_data.get("relationship", "unknown"),
                "weight": edge_data.get("weight", 0),
                **{k: v for k, v in edge_data.items() if k not in ("relationship", "weight")},
            })
        for predecessor in self._graph.predecessors(pod_id):
            edge_data = self._graph.edges[predecessor, pod_id]
            neighbors.append({
                "node": predecessor,
                "kind": self._graph.nodes[predecessor].get("kind", "unknown"),
                "relationship": edge_data.get("relationship", "unknown"),
                "weight": edge_data.get("weight", 0),
                "direction": "inbound",
            })
        return neighbors

    def to_json(self) -> dict[str, Any]:
        """Serialize the current graph to JSON-compatible dict (node-link format)."""
        return json_graph.node_link_data(self._graph)

    def _store_snapshot(self, g: nx.DiGraph) -> None:
        now = datetime.now(timezone.utc)
        data = json_graph.node_link_data(g)
        snap = GraphSnapshot(timestamp=now, node_link_data=data)

        # Redis
        if self._redis:
            try:
                key = f"kovalent:graph:{int(now.timestamp())}"
                self._redis.setex(key, 600, json.dumps(data, default=str))
            except Exception:
                pass

        # In-memory ring buffer
        self._history.append(snap)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def _pod_status(self, metric: PodMetric) -> str:
        if metric.cpu_ratio >= 0.95 or metric.memory_ratio >= 0.95:
            return "CRITICAL"
        if metric.cpu_ratio >= 0.8 or metric.memory_ratio >= 0.85 or metric.error_rate_per_minute >= 10:
            return "WARNING"
        return "OK"

    def _ownership_weight(self, metric: PodMetric) -> float:
        pressure = max(metric.cpu_ratio, metric.memory_ratio)
        return min(1.0, 0.4 + pressure * 0.5)

    def _pvc_weight(self, metric: PodMetric) -> float:
        if metric.pvc_latency_ms is not None and metric.pvc_latency_ms > 0:
            return min(1.0, 0.3 + (metric.pvc_latency_ms / 500))
        return 0.3

    def _severity_rank(self, status: str) -> int:
        return {"OK": 0, "INFO": 1, "WARNING": 2, "CRITICAL": 3}.get(status, 0)
