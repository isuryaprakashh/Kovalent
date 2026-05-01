from app.models import AgentFinding, PodMetric, Severity


class StorageAgent:
    name = "Storage/PVC Agent"

    def analyze(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for metric in metrics:
            latency = metric.pvc_latency_ms
            if metric.pvc_name and latency is not None and latency >= 120:
                findings.append(
                    AgentFinding(
                        agent=self.name,
                        status=Severity.WARNING if latency < 250 else Severity.CRITICAL,
                        pod=metric.pod,
                        service=metric.service,
                        signal="pvc_latency",
                        message=f"PVC {metric.pvc_name} latency is {latency:.0f} ms.",
                        value=latency,
                        threshold=120,
                    )
                )
        return findings

