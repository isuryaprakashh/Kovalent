from __future__ import annotations

from datetime import datetime, timezone
import json

from app.agents.cpu import CpuAgent
from app.agents.log_io import LogIoAgent
from app.agents.memory import MemoryAgent
from app.agents.storage import StorageAgent
from app.config import Settings, get_settings
from app.collectors.mock_collector import MockTelemetryCollector
from app.collectors.prometheus_collector import CollectorConfig, PrometheusTelemetryCollector, TelemetryCollectionError
from app.correlation import MasterCorrelationEngine
from app.models import AgentFinding, ClusterSnapshot, PodMetric, Severity, Topology, TopologyEdge, TopologyNode


class InsightService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.demo_collector = MockTelemetryCollector()
        self.live_collector = PrometheusTelemetryCollector(
            CollectorConfig(
                prometheus_url=self.settings.prometheus_url,
                loki_url=self.settings.loki_url,
                namespace_regex=self.settings.namespace_regex,
                query_window=self.settings.query_window,
                timeout_seconds=self.settings.request_timeout_seconds,
            )
        )
        self.agents = [CpuAgent(), MemoryAgent(), StorageAgent(), LogIoAgent()]
        self.engine = MasterCorrelationEngine()
        self.engine.dependency_map = self._dependency_map()

    async def build_snapshot(self) -> ClusterSnapshot:
        metrics, source = await self._collect_metrics()
        findings = self._run_agents(metrics)
        insights = self.engine.correlate(findings)
        return ClusterSnapshot(
            generated_at=datetime.now(timezone.utc),
            source=source,
            metrics=metrics,
            findings=findings,
            insights=insights,
            topology=self._build_topology(metrics, findings),
        )

    async def _collect_metrics(self) -> tuple[list[PodMetric], str]:
        if self.settings.mode == "live":
            try:
                return await self.live_collector.collect(), "live"
            except TelemetryCollectionError:
                if not self.settings.live_fallback_enabled:
                    raise
                return await self.demo_collector.collect(), "live-fallback"
        return await self.demo_collector.collect(), "demo"

    def _run_agents(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for agent in self.agents:
            findings.extend(agent.analyze(metrics))
        return findings

    def _build_topology(self, metrics: list[PodMetric], findings: list[AgentFinding]) -> Topology:
        service_status = self._service_status(findings)
        nodes: dict[str, TopologyNode] = {}
        edges: list[TopologyEdge] = []

        for metric in metrics:
            service_id = f"svc:{metric.service}"
            pod_id = f"pod:{metric.pod}"
            nodes.setdefault(
                service_id,
                TopologyNode(
                    id=service_id,
                    label=metric.service,
                    namespace=metric.namespace,
                    kind="service",
                    status=service_status.get(metric.service, Severity.OK),
                ),
            )
            nodes[pod_id] = TopologyNode(
                id=pod_id,
                label=metric.pod,
                namespace=metric.namespace,
                kind="pod",
                status=service_status.get(metric.service, Severity.OK),
            )
            edges.append(TopologyEdge(source=service_id, target=pod_id, relationship="owns"))
            if metric.pvc_name:
                pvc_id = f"pvc:{metric.pvc_name}"
                nodes[pvc_id] = TopologyNode(
                    id=pvc_id,
                    label=metric.pvc_name,
                    namespace=metric.namespace,
                    kind="pvc",
                    status=service_status.get(metric.service, Severity.OK),
                )
                edges.append(TopologyEdge(source=pod_id, target=pvc_id, relationship="mounts"))

        for source, targets in self.engine.dependency_map.items():
            for target in targets:
                if f"svc:{source}" in nodes and f"svc:{target}" in nodes:
                    edges.append(TopologyEdge(source=f"svc:{source}", target=f"svc:{target}", relationship="calls"))

        return Topology(nodes=list(nodes.values()), edges=edges)

    def _service_status(self, findings: list[AgentFinding]) -> dict[str, Severity]:
        rank = {Severity.OK: 0, Severity.INFO: 1, Severity.WARNING: 2, Severity.CRITICAL: 3}
        statuses: dict[str, Severity] = {}
        for finding in findings:
            current = statuses.get(finding.service, Severity.OK)
            statuses[finding.service] = max(current, finding.status, key=lambda status: rank[status])
        return statuses

    def _dependency_map(self) -> dict[str, list[str]]:
        raw = {service: list(targets) for service, targets in self.engine.dependency_map.items()}
        configured = self._configured_dependencies()
        if configured:
            raw.update(configured)
        return raw

    def _configured_dependencies(self) -> dict[str, list[str]]:
        if not self.settings.dependencies_json:
            return {}
        parsed = json.loads(self.settings.dependencies_json)
        if not isinstance(parsed, dict):
            raise ValueError("KOVALENT_DEPENDENCIES must be a JSON object.")
        dependencies: dict[str, list[str]] = {}
        for service, targets in parsed.items():
            if isinstance(service, str) and isinstance(targets, list):
                dependencies[service] = [target for target in targets if isinstance(target, str)]
        return dependencies
