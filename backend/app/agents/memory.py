from app.models import AgentFinding, PodMetric, Severity


class MemoryAgent:
    name = "Memory Agent"

    def analyze(self, metrics: list[PodMetric]) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for metric in metrics:
            if metric.memory_ratio >= 0.85:
                findings.append(
                    AgentFinding(
                        agent=self.name,
                        status=Severity.WARNING if metric.memory_ratio < 0.95 else Severity.CRITICAL,
                        pod=metric.pod,
                        service=metric.service,
                        signal="memory_pressure",
                        message=f"{metric.pod} is using {metric.memory_ratio:.0%} of its memory limit.",
                        value=metric.memory_ratio,
                        threshold=0.85,
                    )
                )
        return findings

