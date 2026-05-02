from __future__ import annotations

from datetime import datetime, timezone
import json

from app.agents.cpu import CpuAgent
from app.agents.log_io import LogIoAgent
from app.agents.memory import MemoryAgent
from app.agents.storage import StorageAgent
from app.agents.network import NetworkAgent
from app.agents.restart import RestartAgent
from app.agents.baseline import BaselineAgent
from app.config import Settings, get_settings
from app.collectors.kubernetes_collector import KubernetesCollectorConfig, KubernetesDiscoveryCollector
from app.collectors.mock_collector import MockTelemetryCollector
from app.collectors.prometheus_collector import CollectorConfig, PrometheusTelemetryCollector, TelemetryCollectionError
from app.correlation import MasterCorrelationEngine
from app.collectors.kafka_producer import TelemetryProducer
from app.models import AgentFinding, ClusterSnapshot, PodMetric, Severity, Topology, TopologyEdge, TopologyNode


class InsightService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.producer = TelemetryProducer()
        self.demo_collector = MockTelemetryCollector()
        self.kubernetes_collector = KubernetesDiscoveryCollector(
            KubernetesCollectorConfig(
                discovery_mode=self.settings.kubernetes_discovery_mode,
                namespace_regex=self.settings.namespace_regex,
                timeout_seconds=self.settings.request_timeout_seconds,
                event_limit=self.settings.kubernetes_event_limit,
            )
        )
        self.live_collector = PrometheusTelemetryCollector(
            CollectorConfig(
                prometheus_url=self.settings.prometheus_url,
                loki_url=self.settings.loki_url,
                namespace_regex=self.settings.namespace_regex,
                query_window=self.settings.query_window,
                timeout_seconds=self.settings.request_timeout_seconds,
            ),
            kubernetes_collector=self.kubernetes_collector,
        )
        self.agents = [
            CpuAgent(), 
            MemoryAgent(), 
            StorageAgent(), 
            LogIoAgent(),
            NetworkAgent(),
            RestartAgent(),
            BaselineAgent(),
        ]
        self.engine = MasterCorrelationEngine()
        self.engine.dependency_map = self._dependency_map()

    async def build_snapshot(self) -> ClusterSnapshot:
        metrics, source = await self._collect_metrics()
        
        # Stream metrics to Kafka
        for m in metrics:
            self.producer.produce("metrics.cpu", m.pod, {"pod": m.pod, "value": m.cpu_ratio, "timestamp": m.observed_at})
            self.producer.produce("metrics.memory", m.pod, {"pod": m.pod, "value": m.memory_ratio, "timestamp": m.observed_at})
        self.producer.flush()

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
        from app.services.agent_bus import agent_bus
        for agent in self.agents:
            agent_findings = agent.analyze(metrics)
            for f in agent_findings:
                agent_bus.publish(f)
            findings.extend(agent_findings)
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
