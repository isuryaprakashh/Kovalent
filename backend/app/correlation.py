from __future__ import annotations

from collections import defaultdict

from app.models import AgentFinding, Insight, Severity


class MasterCorrelationEngine:
    """Turns resource-specific findings into root-cause hypotheses."""

    dependency_map: dict[str, list[str]] = {
        "frontend": ["checkout-api", "auth-api"],
        "checkout-api": ["orders-db"],
        "auth-api": [],
        "orders-db": [],
    }

    def correlate(self, findings: list[AgentFinding]) -> list[Insight]:
        by_service: dict[str, list[AgentFinding]] = defaultdict(list)
        for finding in findings:
            by_service[finding.service].append(finding)

        insights: list[Insight] = []
        for service, service_findings in by_service.items():
            signals = {finding.signal for finding in service_findings}
            if {"cpu_saturation", "pvc_latency"} <= signals:
                insights.append(self._storage_wait_saturation(service, service_findings))
            elif "memory_pressure" in signals:
                insights.append(self._memory_pressure(service, service_findings))
            elif "application_errors" in signals:
                insights.append(self._application_errors(service, service_findings))
            elif "cpu_saturation" in signals:
                insights.append(self._cpu_saturation(service, service_findings))

        frontend_errors = by_service.get("frontend", [])
        db_storage = by_service.get("orders-db", [])
        if self._has_signal(frontend_errors, "application_errors") and self._has_signal(db_storage, "pvc_latency"):
            insights.insert(0, self._cascading_latency(frontend_errors + db_storage))

        return self._deduplicate(insights)

    def _storage_wait_saturation(self, service: str, evidence: list[AgentFinding]) -> Insight:
        return Insight(
            status=self._max_status(evidence),
            event="Storage-Wait Saturation",
            root_cause=f"{service} is CPU-active while its persistent storage is responding slowly.",
            correlation="CPU pressure and PVC latency were observed in the same workload window.",
            recommendation="Inspect storage provisioner IOPS, node disk pressure, and database query patterns.",
            affected_services=self._affected_services(service),
            evidence=evidence,
        )

    def _memory_pressure(self, service: str, evidence: list[AgentFinding]) -> Insight:
        return Insight(
            status=self._max_status(evidence),
            event="Memory Pressure Risk",
            root_cause=f"{service} is approaching its configured memory limit.",
            correlation="Memory utilization crossed the risk threshold and may lead to OOM kills.",
            recommendation="Review heap sizing, cache growth, and Kubernetes memory requests/limits.",
            affected_services=self._affected_services(service),
            evidence=evidence,
        )

    def _application_errors(self, service: str, evidence: list[AgentFinding]) -> Insight:
        return Insight(
            status=self._max_status(evidence),
            event="Application Error Spike",
            root_cause=f"{service} is returning elevated application errors.",
            correlation="Log-derived error rate exceeded the service baseline.",
            recommendation="Inspect recent deploys, dependency health, and error logs for this service.",
            affected_services=self._affected_services(service),
            evidence=evidence,
        )

    def _cpu_saturation(self, service: str, evidence: list[AgentFinding]) -> Insight:
        return Insight(
            status=self._max_status(evidence),
            event="CPU Saturation",
            root_cause=f"{service} is using a high share of its CPU limit.",
            correlation="CPU usage exceeded the configured saturation threshold.",
            recommendation="Check request volume, throttling, and limit sizing for the workload.",
            affected_services=self._affected_services(service),
            evidence=evidence,
        )

    def _cascading_latency(self, evidence: list[AgentFinding]) -> Insight:
        return Insight(
            status=Severity.WARNING,
            event="Cascading Latency Detected",
            root_cause="PVC orders-data on orders-db is experiencing I/O wait saturation.",
            correlation="Frontend errors coincide with high storage latency in its downstream order database.",
            recommendation="Check storage provisioner IOPS limits or migrate the database pod to faster disk.",
            affected_services=["frontend", "checkout-api", "orders-db"],
            evidence=evidence,
        )

    def _affected_services(self, service: str) -> list[str]:
        affected = {service}
        for upstream, downstream in self.dependency_map.items():
            if service in downstream:
                affected.add(upstream)
        return sorted(affected)

    def _has_signal(self, findings: list[AgentFinding], signal: str) -> bool:
        return any(finding.signal == signal for finding in findings)

    def _max_status(self, evidence: list[AgentFinding]) -> Severity:
        rank = {Severity.OK: 0, Severity.INFO: 1, Severity.WARNING: 2, Severity.CRITICAL: 3}
        return max((finding.status for finding in evidence), key=lambda status: rank[status], default=Severity.OK)

    def _deduplicate(self, insights: list[Insight]) -> list[Insight]:
        seen: set[tuple[str, str]] = set()
        unique: list[Insight] = []
        for insight in insights:
            key = (insight.event, ",".join(insight.affected_services))
            if key not in seen:
                seen.add(key)
                unique.append(insight)
        return unique

