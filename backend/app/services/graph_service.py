from __future__ import annotations

from app.models import AgentFinding, ClusterSnapshot, DependencyEdge, PodMetric, ResourceGraph
from app.services.insight_service import InsightService


class GraphService:
    """Builds an anomaly-aware resource influence graph from the current snapshot."""

    def __init__(self, insight_service: InsightService) -> None:
        self.insight_service = insight_service

    async def build_graph(self) -> ResourceGraph:
        snapshot = await self.insight_service.build_snapshot()
        return self.from_snapshot(snapshot)

    def from_snapshot(self, snapshot: ClusterSnapshot) -> ResourceGraph:
        findings_by_service = self._findings_by_service(snapshot.findings)
        findings_by_pod = self._findings_by_pod(snapshot.findings)
        metrics_by_pod = {metric.pod: metric for metric in snapshot.metrics}

        edges: list[DependencyEdge] = []
        for edge in snapshot.topology.edges:
            evidence_ids = self._edge_evidence(edge.source, edge.target, findings_by_service, findings_by_pod, metrics_by_pod)
            edges.append(
                DependencyEdge(
                    source=edge.source,
                    target=edge.target,
                    relationship=edge.relationship,
                    score=self._edge_score(edge.relationship, evidence_ids),
                    evidence_ids=evidence_ids,
                )
            )

        edges.extend(self._correlation_edges(snapshot, findings_by_service))
        return ResourceGraph(nodes=snapshot.topology.nodes, edges=edges)

    def _correlation_edges(
        self,
        snapshot: ClusterSnapshot,
        findings_by_service: dict[str, list[AgentFinding]],
    ) -> list[DependencyEdge]:
        edges: list[DependencyEdge] = []
        seen: set[tuple[str, str]] = set()
        for insight in snapshot.insights:
            affected = [service for service in insight.affected_services if service in findings_by_service]
            for source, target in zip(affected, affected[1:]):
                key = (source, target)
                if key in seen:
                    continue
                seen.add(key)
                edge_evidence = self._finding_ids(findings_by_service[source] + findings_by_service[target])
                edges.append(
                    DependencyEdge(
                        source=f"svc:{source}",
                        target=f"svc:{target}",
                        relationship="correlated_with",
                        score=min(1.0, 0.55 + len(edge_evidence) * 0.08),
                        evidence_ids=edge_evidence,
                    )
                )
        return edges

    def _edge_evidence(
        self,
        source: str,
        target: str,
        findings_by_service: dict[str, list[AgentFinding]],
        findings_by_pod: dict[str, list[AgentFinding]],
        metrics_by_pod: dict[str, PodMetric],
    ) -> list[str]:
        source_kind, source_id = source.split(":", 1)
        target_kind, target_id = target.split(":", 1)

        findings: list[AgentFinding] = []
        if source_kind == "svc":
            findings.extend(findings_by_service.get(source_id, []))
        if target_kind == "svc":
            findings.extend(findings_by_service.get(target_id, []))
        if source_kind == "pod":
            findings.extend(findings_by_pod.get(source_id, []))
        if target_kind == "pod":
            findings.extend(findings_by_pod.get(target_id, []))
        if target_kind == "pvc":
            for pod, metric in metrics_by_pod.items():
                if metric.pvc_name == target_id:
                    findings.extend(findings_by_pod.get(pod, []))
        return self._finding_ids(findings)

    def _edge_score(self, relationship: str, evidence_ids: list[str]) -> float:
        base = {
            "owns": 0.5,
            "mounts": 0.65,
            "calls": 0.6,
            "co_located": 0.35,
            "correlated_with": 0.7,
            "temporal_influence": 0.75,
        }.get(relationship, 0.5)
        return min(1.0, base + len(evidence_ids) * 0.08)

    def _findings_by_service(self, findings: list[AgentFinding]) -> dict[str, list[AgentFinding]]:
        grouped: dict[str, list[AgentFinding]] = {}
        for finding in findings:
            grouped.setdefault(finding.service, []).append(finding)
        return grouped

    def _findings_by_pod(self, findings: list[AgentFinding]) -> dict[str, list[AgentFinding]]:
        grouped: dict[str, list[AgentFinding]] = {}
        for finding in findings:
            grouped.setdefault(finding.pod, []).append(finding)
        return grouped

    def _finding_ids(self, findings: list[AgentFinding]) -> list[str]:
        ids: list[str] = []
        for finding in findings:
            item = f"{finding.service}:{finding.pod}:{finding.signal}"
            if item not in ids:
                ids.append(item)
        return ids
