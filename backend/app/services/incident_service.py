from __future__ import annotations

import hashlib
import re

from app.models import (
    AgentFinding,
    ClusterSnapshot,
    EvidenceItem,
    Incident,
    PodMetric,
    Recommendation,
    RootCauseCandidate,
    Severity,
)
from app.services.insight_service import InsightService


class IncidentService:
    """Converts deterministic findings and insights into evidence-backed incidents."""

    def __init__(self, insight_service: InsightService) -> None:
        self.insight_service = insight_service

    async def build_incidents(self) -> list[Incident]:
        snapshot = await self.insight_service.build_snapshot()
        return self.from_snapshot(snapshot)

    async def get_incident(self, incident_id: str) -> Incident | None:
        incidents = await self.build_incidents()
        return next((incident for incident in incidents if incident.id == incident_id), None)

    async def get_evidence(self, incident_id: str) -> list[EvidenceItem] | None:
        incident = await self.get_incident(incident_id)
        if incident is None:
            return None
        return incident.evidence

    def from_snapshot(self, snapshot: ClusterSnapshot) -> list[Incident]:
        metrics_by_pod = {metric.pod: metric for metric in snapshot.metrics}
        incidents: list[Incident] = []
        for insight in snapshot.insights:
            incident_id = self._incident_id(insight.event, insight.affected_services, insight.root_cause)
            evidence = self._evidence_items(incident_id, insight.evidence, metrics_by_pod, snapshot)
            root_cause = self._root_cause(insight.evidence, metrics_by_pod, insight.affected_services)
            incidents.append(
                Incident(
                    id=incident_id,
                    status=insight.status,
                    title=insight.event,
                    summary=f"{insight.root_cause} {insight.correlation}",
                    root_cause=root_cause,
                    affected_services=insight.affected_services,
                    evidence=evidence,
                    recommendations=[
                        Recommendation(
                            action=insight.recommendation,
                            rationale="Recommendation generated from deterministic agent correlation.",
                            priority=self._priority(insight.status),
                        )
                    ],
                    started_at=min((item.observed_at for item in evidence), default=snapshot.generated_at),
                    updated_at=snapshot.generated_at,
                )
            )
        return incidents

    def _evidence_items(
        self,
        incident_id: str,
        findings: list[AgentFinding],
        metrics_by_pod: dict[str, PodMetric],
        snapshot: ClusterSnapshot,
    ) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for index, finding in enumerate(findings, start=1):
            metric = metrics_by_pod.get(finding.pod)
            evidence.append(
                EvidenceItem(
                    id=f"{incident_id}_ev_{index}",
                    kind=self._evidence_kind(finding.signal),
                    title=f"{finding.agent}: {finding.signal.replace('_', ' ').title()}",
                    message=finding.message,
                    service=finding.service,
                    namespace=metric.namespace if metric else None,
                    pod=finding.pod,
                    signal=finding.signal,
                    value=finding.value,
                    threshold=finding.threshold,
                    observed_at=metric.observed_at if metric else snapshot.generated_at,
                )
            )
        return evidence

    def _root_cause(
        self,
        findings: list[AgentFinding],
        metrics_by_pod: dict[str, PodMetric],
        affected_services: list[str],
    ) -> RootCauseCandidate:
        ranked = sorted(findings, key=lambda finding: (self._signal_priority(finding.signal), self._finding_score(finding)), reverse=True)
        top = ranked[0] if ranked else None
        if top is None:
            service = affected_services[0] if affected_services else "unknown"
            return RootCauseCandidate(kind="unknown", service=service, confidence=0.35, score=0.35)

        metric = metrics_by_pod.get(top.pod)
        score = self._finding_score(top)
        confidence = min(0.95, max(0.45, 0.45 + score * 0.4 + min(len(affected_services), 4) * 0.025))
        return RootCauseCandidate(
            kind=top.signal,
            service=top.service,
            pod=top.pod,
            resource=metric.pvc_name if metric and top.signal == "pvc_latency" else None,
            confidence=round(confidence, 2),
            score=round(score, 2),
        )

    def _finding_score(self, finding: AgentFinding) -> float:
        severity_weight = {
            Severity.OK: 0.1,
            Severity.INFO: 0.25,
            Severity.WARNING: 0.65,
            Severity.CRITICAL: 0.9,
        }[finding.status]
        pressure = min(finding.value / finding.threshold, 2.0) / 2.0 if finding.threshold > 0 else 0.5
        signal_weight = {
            "pvc_latency": 0.15,
            "memory_pressure": 0.12,
            "cpu_saturation": 0.1,
            "application_errors": 0.08,
        }.get(finding.signal, 0.05)
        return min(1.0, severity_weight + pressure * 0.25 + signal_weight)

    def _signal_priority(self, signal: str) -> int:
        return {
            "pvc_latency": 4,
            "memory_pressure": 3,
            "cpu_saturation": 2,
            "application_errors": 1,
        }.get(signal, 0)

    def _incident_id(self, event: str, affected_services: list[str], root_cause: str) -> str:
        readable = self._slug("_".join([event, *affected_services]))[:72]
        digest = hashlib.sha1(root_cause.encode("utf-8")).hexdigest()[:8]
        return f"inc_{readable}_{digest}"

    def _slug(self, value: str) -> str:
        return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.lower())).strip("_")

    def _evidence_kind(self, signal: str) -> str:
        if signal == "application_errors":
            return "log"
        return "metric"

    def _priority(self, status: Severity) -> str:
        if status == Severity.CRITICAL:
            return "high"
        if status == Severity.WARNING:
            return "medium"
        return "low"
